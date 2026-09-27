"""TF-IDF con vocabulario GLOBAL para MovieNet (sin LSA — directo).

Construye vocab global sobre 314 srt → TF-IDF L2 por shot → npz por película.
Más rápido que LSA: no requiere SVD, y el gestor usa coseno que funciona en
alta dimensión.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

SEG = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")
RE = __import__("re").compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


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
    ap.add_argument("--out", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_tfidf_global")
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

    movies = sorted(anno)
    if args.limit:
        movies = movies[: args.limit]

    # 1) parsear todos los srt
    all_movies = {}
    for tt in movies:
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
            shot_text.append(" ".join(tx for a, b, tx in cues if a < t1 and b > t0))
        all_movies[tt] = {"n": n, "fps": fps, "texts": shot_text}

    print(f"películas: {len(all_movies)}", flush=True)

    # 2) vocab global
    vocab = {}
    for tt, m in all_movies.items():
        for txt in m["texts"]:
            for w in txt.lower().split():
                if len(w) > 2:
                    vocab[w] = vocab.get(w, 0) + 1
    vocab_idx = {w: i for i, w in enumerate(sorted(w for w, c in vocab.items() if c >= 3))}
    print(f"vocab: {len(vocab_idx)} términos (df>=3)", flush=True)

    # 3) DF global
    n_docs = len(all_movies)
    df = np.zeros(len(vocab_idx))
    for tt, m in all_movies.items():
        seen = set()
        for txt in m["texts"]:
            for w in txt.lower().split():
                if w in vocab_idx:
                    seen.add(w)
        for w in seen:
            df[vocab_idx[w]] += 1
    idf = np.log((1 + n_docs) / (1 + df)) + 1.0

    # 4) TF-IDF L2 por película (guardo inmediatamente para no acumular memoria)
    import gc
    for i, (tt, m) in enumerate(sorted(all_movies.items())):
        out_f = out / f"{tt}.tfidf.npz"
        if out_f.exists():
            continue
        rows = np.zeros((m["n"], len(vocab_idx)), dtype=np.float32)
        for k, txt in enumerate(m["texts"]):
            for w in txt.lower().split():
                if w in vocab_idx:
                    rows[k, vocab_idx[w]] += 1.0
            for w in set(w for w in txt.lower().split() if w in vocab_idx):
                rows[k, vocab_idx[w]] *= idf[vocab_idx[w]]
        nrm = np.linalg.norm(rows, axis=1, keepdims=True)
        rows = rows / (nrm + 1e-8)
        np.savez_compressed(out_f, tfidf=rows.astype(np.float32))
        del rows
        if (i + 1) % 50 == 0 or i + 1 == len(all_movies):
            gc.collect()
            print(f"[tfidf] {i + 1}/{len(all_movies)} {tt}", flush=True)

    print(f"TFIDF_GLOBAL_DONE {len(all_movies)} películas", flush=True)


if __name__ == "__main__":
    main()
