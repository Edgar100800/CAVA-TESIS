"""EXP-019d: propaga nombres de personajes por los enlaces de CAVA.

Un tópico cuya etiqueta no nombra a nadie hereda los nombres del tópico
nombrado al que más se enlaza, si DOS señales lo enlazan por su cuenta
(quorum 2, sin fusión): similitud visual de centroides ≥ percentil
--p-visual y similitud vjudge ≥ --p-vjudge, cada una sobre los pares de
tópicos de la película. Nombres = palabras en mayúscula del campo CHARACTERS
de la etiqueta (salida de CAVA); el GT no interviene.

Salida: <out>/<tt>.topic_labels.json (mismo formato que 019b) y
        <out>/<tt>.propagation.json (receptor -> donante, similitudes, nombres)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_threads import names_of  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402


def centroid(x, idx):
    rows = x[[i for i in idx if i < len(x)]]
    rows = rows[np.linalg.norm(rows, axis=1) > 0]
    if not len(rows):
        return None
    c = (rows / np.linalg.norm(rows, axis=1, keepdims=True)).mean(0)
    return c / (np.linalg.norm(c) + 1e-8)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", required=True)
    ap.add_argument("--summary-dir", required=True)
    ap.add_argument("--labels", default="data/topic_labels")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--out", default="data/topic_labels_prop")
    ap.add_argument("--p-visual", type=float, default=90)
    ap.add_argument("--p-vjudge", type=float, default=75)
    ap.add_argument("--min-dur", type=float, default=30.0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bge = BgeEmbedder()
    for f in sorted(Path(args.maps).glob("*.topic_map.json")):
        doc = json.loads(f.read_text())
        tt = doc["video_id"]
        fl = Path(args.labels) / f"{tt}.topic_labels.json"
        if not fl.exists():
            continue
        labels = json.loads(fl.read_text())
        vis = np.asarray(np.load(Path(args.corpus) / f"{tt}.npz")["visual"], np.float32)
        sums = json.loads((Path(args.summary_dir) / f"{tt}.summaries.json").read_text())
        e = bge([u["summary"] for u in sums])
        vj = np.zeros((len(vis), e.shape[1]), np.float32)
        for u, v in zip(sums, e):
            vj[u["lo"]:min(u["hi"], len(vis))] = v
        topics = [t for t in doc["levels"]["default"]["topics"]
                  if t["duration_s"] >= args.min_dur and str(t["topic_id"]) in labels]
        if len(topics) < 3:
            continue
        cv = [centroid(vis, t["shots"]) for t in topics]
        cj = [centroid(vj, t["shots"]) for t in topics]
        ok = [i for i in range(len(topics)) if cv[i] is not None and cj[i] is not None]
        Sv = np.full((len(topics), len(topics)), np.nan)
        Sj = np.full_like(Sv, np.nan)
        for i in ok:
            for j in ok:
                if i != j:
                    Sv[i, j], Sj[i, j] = float(cv[i] @ cv[j]), float(cj[i] @ cj[j])
        tv = np.nanpercentile(Sv, args.p_visual)
        tj = np.nanpercentile(Sj, args.p_vjudge)
        names = [names_of(labels[str(t["topic_id"])]) for t in topics]
        new, prop = dict(labels), []
        for i, t in enumerate(topics):
            if names[i]:
                continue
            donors = [j for j in ok if j != i and names[j] and Sv[i, j] >= tv and Sj[i, j] >= tj]
            if i not in ok or not donors:
                continue
            j = max(donors, key=lambda k: Sv[i, k])
            lab = labels[str(t["topic_id"])]
            topic_part = lab.split("|", 1)[1].strip() if "|" in lab else lab
            inherited = sorted(names[j])
            new[str(t["topic_id"])] = f"CHARACTERS: {', '.join(inherited)} | {topic_part}"
            prop.append({"recipient": t["topic_id"], "donor": topics[j]["topic_id"],
                         "sim_visual": round(float(Sv[i, j]), 4), "sim_vjudge": round(float(Sj[i, j]), 4),
                         "names": inherited})
        (out / f"{tt}.topic_labels.json").write_text(json.dumps(new, ensure_ascii=False))
        (out / f"{tt}.propagation.json").write_text(json.dumps(
            {"thr_visual": round(float(tv), 4), "thr_vjudge": round(float(tj), 4), "propagated": prop},
            indent=1, ensure_ascii=False))
        n_rec = sum(1 for x in names if not x)
        print(f"[propagate] {tt}: receptores {n_rec}, heredan {len(prop)}", flush=True)


if __name__ == "__main__":
    main()
