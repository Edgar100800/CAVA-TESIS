"""Multi-tolerancia: F1 de fronteras temáticas vs GT a distintas escalas.

Si el mismatch es de GRANULARIDAD (nuestros tópicos son más gruesos que las
escenas GT), el F1 debe subir con tolerancias amplias y las predicciones deben
caer dentro de rangos GT amplios. Si es de CONTENIDO (fallamos en detectar),
el F1 se mantiene bajo a cualquier tolerancia.
"""
import argparse
import json
from pathlib import Path

import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.multimodal_manager import manage  # noqa: E402


def run_movie(npz_path, meta, signals, percentile, link_quorum,
              tolerance_bins, tolerances):
    d = np.load(npz_path)
    n = min(meta["n_shots"], len(d["visual"]))
    sigs = {}
    if "transcript" in signals:
        sigs["transcript"] = np.asarray(d["tfidf"][:n], dtype=np.float32)
    if "visual" in signals:
        sigs["visual"] = np.asarray(d["visual"][:n], dtype=np.float32)
    if not sigs:
        return None

    plan = manage(sigs, n_segments=n, percentile=percentile,
                  link_quorum=link_quorum, tolerance_bins=tolerance_bins)
    pred = [int(i) for i in range(1, len(plan.labels))
            if plan.labels[i] != plan.labels[i - 1]]
    gt = meta["gt_scene_cuts"]
    n_shots = meta["n_shots"]

    out = {"n_shots": n, "n_pred": len(pred), "n_gt": len(gt)}
    for tol in tolerances:
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
        out[f"precision@{tol}"] = round(precision, 4)
        out[f"recall@{tol}"] = round(recall, 4)
        out[f"f1@{tol}"] = round(f1, 4)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus",
                    default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    ap.add_argument("--signals", default="both")
    ap.add_argument("--percentile", type=int, default=80)
    ap.add_argument("--link-quorum", type=int, default=2)
    ap.add_argument("--tolerance-bins", type=int, default=1)
    ap.add_argument("--tolerances", nargs="+", type=int,
                    default=[1, 2, 5, 10, 20])
    ap.add_argument("--tag", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    sig_sets = {
        "both": ["transcript", "visual"],
        "transcript": ["transcript"],
        "visual": ["visual"],
    }[args.signals]

    corpus = Path(args.corpus)
    movies = []
    for jp in sorted(corpus.glob("tt*.json")):
        npz = jp.with_suffix(".npz")
        if not npz.exists():
            continue
        meta = json.loads(jp.read_text())
        movies.append((npz, meta))
    if not movies:
        sys.exit("corpus vacío")

    all_runs = []
    for npz, meta in movies:
        try:
            r = run_movie(npz, meta, sig_sets, args.percentile,
                          args.link_quorum, args.tolerance_bins, args.tolerances)
            if r:
                all_runs.append(r)
        except Exception:
            pass

    agg = {"n_movies": len(all_runs), "tolerances": args.tolerances}
    for tol in args.tolerances:
        for m in ("precision", "recall", "f1"):
            key = f"{m}@{tol}"
            vals = [r[key] for r in all_runs if key in r]
            agg[key + "_mean"] = round(float(np.mean(vals)), 4) if vals else None

    # baseline azar a cada tolerancia (media de densidad GT × ventana)
    densities = []
    for npz, meta in movies:
        n_shots = meta["n_shots"]
        gt = meta["gt_scene_cuts"]
        if n_shots > 0:
            densities.append(len(gt) / n_shots)
    agg["random_baseline_mean"] = round(
        float(np.mean(densities)) * 2 * max(args.tolerances), 4) if densities else None

    tag = args.tag or (f"{args.signals}_p{args.percentile}_q{args.link_quorum}"
                       f"_t{args.tolerance_bins}")
    out_path = Path(args.out or str(corpus)) / f"multitolerance_{tag}.json"
    out_path.write_text(json.dumps({"config": {
        "signals": sig_sets, "percentile": args.percentile,
        "link_quorum": args.link_quorum, "tolerance_bins": args.tolerance_bins,
    }, **agg, "per_movie": all_runs}, indent=1))
    md = (Path(args.out or str(corpus)) / f"multitolerance_{tag}.md")
    lines = ["| tolerancia | P | R | F1 | azar |", "|---|---|---|---|---|"]
    for tol in args.tolerances:
        lines.append(f"| ±{tol} shots | {agg.get(f'precision@{tol}_mean','-')} "
                     f"| {agg.get(f'recall@{tol}_mean','-')} "
                     f"| {agg.get(f'f1@{tol}_mean','-')} "
                     f"| {agg.get('random_baseline_mean','-')} |")
    md.write_text(f"# Multi-tolerancia ({args.signals}, "
                  f"p{args.percentile} q{args.link_quorum})\n\n"
                  + "\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n[out] {out_path}")


if __name__ == "__main__":
    main()
