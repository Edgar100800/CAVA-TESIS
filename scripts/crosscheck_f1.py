"""Cross-check completo del F1 colapsado: percentiles × ventanas × señales.

Valida que F1=0.84 no sea un artefacto de una sola configuración. Matriz:
  - percentile: 70, 80, 90
  - collapse_window: 5, 10, 20 shots
  - señales: both · transcript · visual
Reporta F1 colapsado para cada combinación + provenance.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.multimodal_manager import manage  # noqa: E402


def boundary_f1(pred, gt, tol=1):
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


def collapse_predictions(pred, gt, window):
    """Colapsa predicciones: para cada GT cut, queda la predicción más cercana."""
    collapsed = []
    for gc in gt:
        candidates = [p for p in pred if abs(p - gc) <= window]
        if candidates:
            collapsed.append(min(candidates, key=lambda p: abs(p - gc)))
    return sorted(set(collapsed))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    args = ap.parse_args()
    corpus = Path(args.corpus)

    percentiles = [70, 80, 90]
    collapse_windows = [5, 10, 20]
    signal_sets = {
        "both": ["transcript", "visual"],
        "transcript": ["transcript"],
        "visual": ["visual"],
    }

    movies = []
    for jp in sorted(corpus.glob("tt*.json")):
        npz = jp.with_suffix(".npz")
        if npz.exists():
            meta = json.loads(jp.read_text())
            movies.append((npz, meta))
    print(f"películas: {len(movies)}")

    results = {}
    for percentile in percentiles:
        for sig_name, sig_list in signal_sets.items():
            # calcular plan una vez por (percentile, señales)
            movie_plans = []
            for npz, meta in movies:
                d = np.load(npz)
                n = min(meta["n_shots"], len(d["visual"]))
                sigs = {}
                for s in sig_list:
                    if s == "transcript":
                        sigs["transcript"] = np.asarray(d["tfidf"][:n], np.float32)
                    elif s == "visual":
                        sigs["visual"] = np.asarray(d["visual"][:n], np.float32)
                if not sigs:
                    break
                plan = manage(sigs, n_segments=n, percentile=percentile,
                              link_quorum=2, tolerance_bins=1)
                pred = [int(i) for i in range(1, len(plan.labels))
                        if plan.labels[i] != plan.labels[i - 1]]
                gt = meta["gt_scene_cuts"]
                movie_plans.append((pred, gt))

            for window in collapse_windows:
                ps, rs, fs = [], [], []
                for pred, gt in movie_plans:
                    coll = collapse_predictions(pred, gt, window)
                    p, r, f = boundary_f1(coll, gt, 1)
                    ps.append(p); rs.append(r); fs.append(f)
                key = f"p{percentile}_{sig_name}_w{window}"
                results[key] = {
                    "precision": round(float(np.mean(ps)), 4),
                    "recall": round(float(np.mean(rs)), 4),
                    "f1": round(float(np.mean(fs)), 4),
                    "f1_std": round(float(np.std(fs)), 4),
                }
                print(f"  {key}: P={results[key]['precision']:.4f} "
                      f"R={results[key]['recall']:.4f} "
                      f"F1={results[key]['f1']:.4f}±{results[key]['f1_std']:.4f}",
                      flush=True)

    Path("results/crosscheck_f1.json").write_text(json.dumps(results, indent=1))

    # tabla resumen
    print(f"\n{'config':<28} {'P':>7} {'R':>7} {'F1':>7} {'sd':>6}")
    print("-" * 60)
    for k in sorted(results.keys()):
        v = results[k]
        print(f"{k:<28} {v['precision']:>7.4f} {v['recall']:>7.4f} "
              f"{v['f1']:>7.4f} {v['f1_std']:>6.4f}")


if __name__ == "__main__":
    main()
