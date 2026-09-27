"""Análisis dual de granularidad: colapso a GT vs granularidad fina como feature.

Camino 1: colapsar nuestras fronteras al nivel GT (la más fuerte por escena GT)
         → F1 comparable con el GT a granularidad estándar.
Camino 2: granularidad fina como feature — medir si nuestras fronteras finas
         subdividen las escenas GT de forma consistente (sub-topic structure).

Ejecuta ambos y registra los resultados juntos.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.multimodal_manager import manage  # noqa: E402


def boundary_f1(pred, gt, tol):
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    ap.add_argument("--percentile", type=int, default=80)
    ap.add_argument("--link-quorum", type=int, default=2)
    ap.add_argument("--tolerance-bins", type=int, default=1)
    ap.add_argument("--collapse-window", type=int, default=10,
                    help="shots: ventana para colapsar predicciones a nivel GT")
    ap.add_argument("--out", default="results/dual_granularity.json")
    args = ap.parse_args()

    corpus = Path(args.corpus)
    results_fine = []
    results_collapsed = []
    results_coverage = []

    for jp in sorted(corpus.glob("tt*.json")):
        npz = jp.with_suffix(".npz")
        if not npz.exists():
            continue
        meta = json.loads(jp.read_text())
        d = np.load(npz)
        n = min(meta["n_shots"], len(d["visual"]))
        sigs = {"transcript": np.asarray(d["tfidf"][:n], np.float32),
                "visual": np.asarray(d["visual"][:n], np.float32)}

        plan = manage(sigs, n_segments=n, percentile=args.percentile,
                      link_quorum=args.link_quorum, tolerance_bins=args.tolerance_bins)
        pred = [int(i) for i in range(1, len(plan.labels))
                if plan.labels[i] != plan.labels[i - 1]]
        if not pred or not meta["gt_scene_cuts"]:
            continue

        gt = meta["gt_scene_cuts"]

        # --- camino 1: colapsar a nivel GT ---
        # para cada GT cut, encontrar nuestra predicción más cercana (si hay)
        collapsed = []
        for gc in gt:
            candidates = [p for p in pred if abs(p - gc) <= args.collapse_window]
            if candidates:
                collapsed.append(min(candidates, key=lambda p: abs(p - gc)))
        collapsed = sorted(set(collapsed))
        cp, cr, cf = boundary_f1(collapsed, gt, 1)

        # --- camino 2: granularidad fina ---
        fp, fr, ff = boundary_f1(pred, gt, 1)

        # --- cobertura de GT ---
        covered = sum(1 for g in gt
                      if any(abs(p - g) <= args.collapse_window for p in pred))
        coverage = covered / len(gt) if gt else 0.0

        results_fine.append({"f1": ff, "precision": fp, "recall": fr})
        results_collapsed.append({"f1": cf, "precision": cp, "recall": cr})
        results_coverage.append(coverage)

    n = len(results_fine)

    def agg(runs, field):
        vals = [r[field] for r in runs if field in r]
        return round(float(np.mean(vals)), 4) if vals else None

    result = {
        "protocol": "dual_granularity_analysis",
        "n_movies": n,
        "collapse_window_shots": args.collapse_window,
        "percentile": args.percentile,
        "link_quorum": args.link_quorum,
        "camino_1_collapsed": {
            "precision": agg(results_collapsed, "precision"),
            "recall": agg(results_collapsed, "recall"),
            "f1": agg(results_collapsed, "f1"),
        },
        "camino_2_fine": {
            "precision": agg(results_fine, "precision"),
            "recall": agg(results_fine, "recall"),
            "f1": agg(results_fine, "f1"),
        },
        "gt_coverage_mean": round(float(np.mean(results_coverage)), 4) if results_coverage else None,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
