"""EXP-011 paso 1: votantes extra por película (val) para el agregador adaptativo.

Por película del corpus (`data/movienet_topics/<tt>.json`) escribe
`data/movienet_voters/<tt>.npz` con:
  segloop   [n-1]  P(corte entre shot k y k+1) del ensemble SegLoop frozen
                   (logit R2 .45 / R2B .20 / R2BD .35, media de seeds 17 y 42).
                   Scores de val: el split se usó para elegir pesos/umbral del
                   ensemble, no para entrenar.
  seg_thr   []     umbral frozen del ensemble en probabilidad (media de seeds)
  dialogue  [n,768] bge-base del subtítulo del shot (fila 0 = sin diálogo)
  speech    [n]    fracción del shot cubierta por subtítulos (proxy de audio)
Resumible.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrative_eval import BgeEmbedder  # noqa: E402
from narrative_interpreter import parse_srt  # noqa: E402

SEG = Path("/home/edgar.chambilla/Tesis/SegLoop")
MN = SEG / "data" / "movienet"
ENS = SEG / "logs" / "segmenter" / "r2_bassl_ensemble"


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def segloop_val_scores():
    """{tt: {k: p}} con k = shot tras el que cae el corte. Índice reconstruido en
    el orden de `predict()` (anotaciones val, filas con boundary_label ∈ {0,1})."""
    sys.path.insert(0, str(SEG))
    from segloop.segmenter.dataset import load_annotations
    sel = json.loads((ENS / "selection.json").read_text())["selection"]
    ann = load_annotations(MN / "anno" / "anno.val.ndjson")
    idx = [(v, k) for v, rows in ann.items() for k, r in enumerate(rows)
           if int(r.get("boundary_label", -1)) in (0, 1)]
    probs, thrs = [], []
    for seed in ("17", "42"):
        z = 0.0
        labels = None
        for member, w in sel["weights"].items():
            d = np.load(ENS / f"{member}_seed_{seed}.npz")
            labels = d["labels"] if labels is None else labels
            z = z + w * logit(d["scores"])
        want = np.array([int(ann[v][k]["boundary_label"]) for v, k in idx])
        if not np.array_equal(labels, want):
            raise ValueError("orden de scores SegLoop no coincide con las anotaciones")
        probs.append(1 / (1 + np.exp(-z)))
        thrs.append(1 / (1 + np.exp(-sel["thresholds"][seed])))
    p = np.mean(probs, axis=0)
    out = {}
    for (v, k), pk in zip(idx, p):
        out.setdefault(v, {})[k] = float(pk)
    return out, float(np.mean(thrs))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--out", default="data/movienet_voters")
    args = ap.parse_args()

    seg, seg_thr = segloop_val_scores()
    corpus, out = Path(args.corpus), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bge = None
    for tt in sorted(seg):
        f_out = out / f"{tt}.npz"
        cj = corpus / f"{tt}.json"
        if f_out.exists() or not cj.exists():
            continue
        c = json.loads(cj.read_text())
        n, st = c["n_shots"], c["shot_times"]
        s = np.zeros(n - 1, dtype=np.float32)
        for k, pk in seg[tt].items():
            if k < n - 1:
                s[k] = pk
        cues = parse_srt(MN / "subtitle" / f"{tt}.srt")
        texts, speech = [], np.zeros(n, dtype=np.float32)
        for k, (t0, t1) in enumerate(st):
            ov = [(max(a, t0), min(b, t1), tx) for a, b, tx in cues if a < t1 and b > t0]
            texts.append(" ".join(tx for _, _, tx in ov))
            speech[k] = min(1.0, sum(b - a for a, b, _ in ov) / max(t1 - t0, 1e-3))
        bge = bge or BgeEmbedder()
        dialogue = bge(texts).astype(np.float16)
        np.savez_compressed(f_out, segloop=s, seg_thr=np.float32(seg_thr),
                            dialogue=dialogue, speech=speech)
        print(f"[voters] {tt}: n={n} habla={float((speech > 0).mean()):.2f} "
              f"segloop>thr={int((s > seg_thr).sum())}", flush=True)


if __name__ == "__main__":
    main()
