"""Evaluación cuantitativa: tópicos del gestor SIN FUSIÓN vs escenas GT de MovieNet.

Para cada película (npz + json de extract_movienet_signals):
  - manage() con las señales pedidas -> cortes predichos (cambio de label)
  - GT: cortes de escena (cambio de invideo_scene_id)
  - matching con tolerancia ±tol_shots -> precision / recall / F1 por película
  - ablation: transcript-only · visual-only · ambas

Grid opcional (--grid) sobre percentile × link_quorum × tolerance_bins.
Salida: results/movienet_topics/eval_<tag>.json + .md
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topicagg.multimodal_manager import manage  # noqa: E402


def boundary_f1(pred_cuts, gt_cuts, tol):
    pred = list(pred_cuts)
    gt = list(gt_cuts)
    matched_p = 0
    used = set()
    for p in pred:
        for gi, g in enumerate(gt):
            if gi not in used and abs(p - g) <= tol:
                matched_p += 1
                used.add(gi)
                break
    precision = matched_p / len(pred) if pred else 0.0
    recall = matched_p / len(gt) if gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def predict_cuts(labels):
    return [int(i) for i in range(1, len(labels)) if labels[i] != labels[i - 1]]


def run_movie(npz_path, meta, signals, percentile, link_quorum, tolerance_bins,
              tol_shots):
    d = np.load(npz_path)
    n = min(meta["n_shots"], len(d["visual"]))
    sigs = {}
    if "transcript" in signals:
        sigs["transcript"] = np.asarray(d["tfidf"][:n], dtype=np.float32)
    if "visual" in signals:
        sigs["visual"] = np.asarray(d["visual"][:n], dtype=np.float32)
    if not sigs:
        raise ValueError("sin señales pedidas")
    plan = manage(sigs, n_segments=n, percentile=percentile,
                  link_quorum=link_quorum, tolerance_bins=tolerance_bins)
    pred = predict_cuts(plan.labels)
    gt = meta["gt_scene_cuts"]
    precision, recall, f1 = boundary_f1(pred, gt, tol_shots)
    return {"n_shots": n, "n_pred": len(pred), "n_gt": len(gt),
            "precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    ap.add_argument("--signals", default="both",
                    choices=("both", "transcript", "visual"))
    ap.add_argument("--percentile", type=int, default=80)
    ap.add_argument("--link-quorum", type=int, default=2)
    ap.add_argument("--tolerance-bins", type=int, default=1)
    ap.add_argument("--tol-shots", type=float, default=1.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--grid", action="store_true",
                    help="barrido percentile × quorum × tolerance")
    args = ap.parse_args()

    sig_sets = {
        "both": ["transcript", "visual"],
        "transcript": ["transcript"],
        "visual": ["visual"],
    }[args.signals]

    corpus = Path(args.corpus)
    movies = []
    for jp in sorted(corpus.glob("*.json")):
        npz = jp.with_suffix(".npz")
        if not npz.exists():
            continue
        meta = json.loads(jp.read_text())
        if args.limit and len(movies) >= args.limit:
            break
        movies.append((jp.with_suffix(".npz"), meta))
    if not movies:
        sys.exit("corpus vacío")

    if args.grid:
        grid = list(__import__("itertools").product((70, 80, 90), (1, 2), (0, 1)))
    else:
        grid = [(args.percentile, args.link_quorum, args.tolerance_bins)]

    all_runs = {}
    for p, q, tb in grid:
        runs = []
        for npz, meta in movies:
            try:
                runs.append(run_movie(npz, meta, sig_sets, p, q, tb,
                                      args.tol_shots))
            except Exception as e:  # película con insumos rotos: se reporta
                runs.append({"error": str(e)[:80]})
        ok = [r for r in runs if "error" not in r]
        agg = {
            "n_movies": len(ok),
            "n_failed": len(runs) - len(ok),
            "precision_mean": round(float(np.mean([r["precision"] for r in ok])), 4),
            "recall_mean": round(float(np.mean([r["recall"] for r in ok])), 4),
            "f1_mean": round(float(np.mean([r["f1"] for r in ok])), 4),
            "f1_std": round(float(np.std([r["f1"] for r in ok])), 4),
        }
        all_runs[f"p{p}_q{q}_t{tb}"] = agg
        print(f"[eval] p{p} q{q} t{tb}: P={agg['precision_mean']} "
              f"R={agg['recall_mean']} F1={agg['f1_mean']} ± {agg['f1_std']} "
              f"({agg['n_movies']} pelis)", flush=True)

    tag = args.tag or (f"{args.signals}_p{args.percentile}_q{args.link_quorum}"
                       f"_t{args.tolerance_bins}")
    out = {"protocol": "movienet_topic_boundary_eval",
           "gt": "escenas narrativas humanas (invideo_scene_id)",
           "signals": sig_sets, "tol_shots": args.tol_shots,
           "grid": all_runs}
    (corpus / f"eval_{tag}.json").write_text(json.dumps(out, indent=1))

    lines = ["| config | P | R | F1 | F1 sd | pelis |",
             "|---|---|---|---|---|---|"]
    for k, a in all_runs.items():
        lines.append(f"| {k} | {a['precision_mean']} | {a['recall_mean']} "
                     f"| {a['f1_mean']} | {a['f1_std']} | {a['n_movies']} |")
    (corpus / f"eval_{tag}.md").write_text(
        f"# Evaluación tópicos MovieNet ({args.signals})\n\n" + "\n".join(lines) + "\n")
    print(f"[out] {corpus}/eval_{tag}.json + .md")


if __name__ == "__main__":
    main()
