"""Corpus-level TF-IDF + LSA para MovieNet (fix del vocabulario por-película).

En lugar de TF-IDF per-movie (vocab privado → dimensiones distintas),
construye un vocabulario GLOBAL compartido sobre los 314 srt y aplica LSA
(truncated SVD) para producir embeddings densos comparables entre películas.

Salida: <out>/<tt>.lsa.npz con {lsa: [n_shots, k] float32}
"""
import argparse
import json
import re
from pathlib import Path

import numpy as np

RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
SEG = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")


def parse_srt(path):
    cues, s, e, txt = [], None, None, []
    for line in Path(path).read_text(errors="ignore").splitlines():
        m = RE.search(line)
        if m:
            g = [int(x) for x in m.groups()]
            if txt and s is not None:
                cues.append((s, e, " ".join(txt)))
            s = g[0]*3600+g[1]*60+g[2]+g[3]/1000
            e = g[4]*3600+g[5]*60+g[6]+g[7]/1000
            txt = []
        elif line.strip() and s is not None:
            txt.append(line.strip())
    if txt and s is not None:
        cues.append((s, e, " ".join(txt)))
    return cues


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    ap.add_argument("--n-components", type=int, default=64)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    info = json.load(open(SEG / "official" / "video_info.json"))
    anno_dir = SEG / "anno"
    anno = {}
    for f in ("anno.train.ndjson", "anno.val.ndjson", "anno.test.ndjson"):
        for line in open(anno_dir / f):
            r = json.loads(line)
            anno.setdefault(r["video_id"], []).append(r)

    # 1) recolectar TODO el texto por shot para vocab global
    movies = {}
    for tt in sorted(anno):
        srt = SEG / "subtitle" / f"{tt}.srt"
        shot_f = SEG / "scene318" / "shot_movie318" / f"{tt}.txt"
        if not srt.exists() or not shot_f.exists():
            continue
        cues = parse_srt(srt)
        shots = [[int(x) for x in l.split()]
                 for l in shot_f.read_text().splitlines() if l.strip()]
        rows = anno.get(tt)
        if not rows:
            continue
        rows = sorted(rows, key=lambda r: int(r["shot_id"]))
        n = min(len(shots), len(rows))
        fps = float(info.get(tt, {}).get("fps", 25.0))

        shot_text = []
        for k in range(n):
            t0 = shots[k][0] / fps
            t1 = (shots[k][1] + 1) / fps
            txt = " ".join(tx for a, b, tx in cues if a < t1 and b > t0)
            shot_text.append(txt)

        movies[tt] = {"n": n, "fps": fps, "shot_text": shot_text,
                      "shot_times": [[t0, t1] for t0, t1 in
                                     [(shots[k][0]/fps, (shots[k][1]+1)/fps)
                                      for k in range(n)]]}

    print(f"películas con texto: {len(movies)}", flush=True)

    # vocabulario global
    global_vocab = {}
    for tt, m in movies.items():
        for txt in m["shot_text"]:
            for w in txt.lower().split():
                if len(w) > 2:
                    global_vocab[w] = global_vocab.get(w, 0) + 1
    vocab = sorted(w for w, c in global_vocab.items() if c >= 3)  # min df=3
    vocab_idx = {w: i for i, w in enumerate(vocab)}
    print(f"vocab global: {len(vocab)} términos (df>=3)", flush=True)

    # 2) TF-IDF global
    N = sum(m["n"] for m in movies.values())
    df = np.zeros(len(vocab))
    for tt, m in movies.items():
        seen = set()
        for txt in m["shot_text"]:
            for w in txt.lower().split():
                if w in vocab_idx:
                    seen.add(w)
        for w in seen:
            df[vocab_idx[w]] += 1
    idf = np.log((1 + N) / (1 + df)) + 1.0

    # 3) TF-IDF por película (usando vocab global)
    tfidf_per_movie = {}
    for tt, m in movies.items():
        rows = np.zeros((m["n"], len(vocab)), dtype=np.float32)
        for i, txt in enumerate(m["shot_text"]):
            toks = [w for w in txt.lower().split() if w in vocab_idx]
            for w in toks:
                rows[i, vocab_idx[w]] += 1.0
            for w in set(toks):
                rows[i, vocab_idx[w]] *= idf[vocab_idx[w]]
        nrm = np.linalg.norm(rows, axis=1, keepdims=True)
        rows = rows / (nrm + 1e-8)
        tfidf_per_movie[tt] = rows

    # 4) LSA global (SVD sobre la matriz completa)
    X = np.vstack(list(tfidf_per_movie.values()))
    print(f"LSA: SVD sobre {X.shape}", flush=True)
    k = min(args.n_components, min(X.shape) - 1)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    X_lsa = U[:, :k] @ np.diag(S[:k])

    # 5) guardar por película
    offset = 0
    for tt, m in movies.items():
        n_i = m["n"]
        np.savez_compressed(out / f"{tt}.lsa.npz",
                            lsa=X_lsa[offset:offset + n_i].astype(np.float32))
        offset += n_i
    print(f"LSA guardado para {len(movies)} películas, k={k}", flush=True)


if __name__ == "__main__":
    main()
