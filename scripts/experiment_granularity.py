"""Experimentación: offset, embeddings semánticos, y gestión sin fusión vs GT.

Tres experimentos sobre las mismas 97 películas:
  E1 — Offset sweep: desplazar cortes predichos ±N shots y medir F1.
       Pregunta: ¿hay offset sistemático corregible?
  E2 — Corpus-level TF-IDF + LSA: embeddings semánticos densos (no léxicos).
       Pregunta: ¿el vocabulario compartido mejora la señal?
  E3 — Ablation: transcript / visual / ambas, con y sin offset.

Métrica: F1 de fronteras vs GT escenas (±tol_shots).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.multimodal_manager import manage  # noqa: E402
from topicagg.signals.core import TranscriptSignal  # noqa: E402


def boundary_f1(pred, gt, tol=1):
    pred, gt = list(pred), list(gt)
    matched = 0
    used = set()
    for p in pred:
        for gi, g in enumerate(gt):
            if gi not in used and abs(p - g) <= tol:
                matched += 1
                used.add(gi)
                break
    prec = matched / len(pred) if pred else 0.0
    rec = matched / len(gt) if gt else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return prec, rec, f1


def load_corpus(corpus_dir):
    movies = []
    for jp in sorted(Path(corpus_dir).glob("tt*.json")):
        npz = jp.with_suffix(".npz")
        if not npz.exists():
            continue
        meta = json.loads(jp.read_text())
        d = np.load(npz)
        n = min(meta["n_shots"], len(d["visual"]))
        movies.append((str(npz), meta, {
            "visual": np.asarray(d["visual"][:n], np.float32),
            "tfidf": np.asarray(d["tfidf"][:n], np.float32),
        }))
    return movies


def corpus_tfidf_lsa(movies, n_components=64):
    """TF-IDF global (vocabulario compartido) + LSA para densificar."""
    # recolectar todo el texto TF-IDF (aproximación: concatenar filas)
    all_rows = []
    for _, _, sigs in movies:
        all_rows.append(sigs["tfidf"])
    X = np.vstack(all_rows)  # [N_total, V_global]

    # SVD truncado (LSA)
    from scipy.sparse.linalg import svds
    k = min(n_components, min(X.shape) - 1)
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    X_lsa = X[:, :k] @ np.diag(S[:k])  # [N, k]

    # devolver por película
    offset = 0
    per_movie = []
    for _, _, sigs in movies:
        n_i = sigs.shape[0]
        per_movie.append(X_lsa[offset:offset + n_i])
        offset += n_i
    return per_movie


def run_config(sigs, speech_times, n, percentile, link_quorum, tol_bins,
               offset=0):
    plan = manage(sigs, speech_times=speech_times, n_segments=n,
                  percentile=percentile, link_quorum=link_quorum,
                  tolerance_bins=tol_bins)
    pred = [int(i) for i in range(1, len(plan.labels))
            if plan.labels[i] != plan.labels[i - 1]]
    # offset: desplazar cortes
    if offset != 0:
        pred = [max(0, min(n - 1, p + offset)) for p in pred]
    return pred, plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    ap.add_argument("--limit", type=int, default=35)
    ap.add_argument("--tol-shots", type=float, default=1.0)
    args = ap.parse_args()

    movies = load_corpus(args.corpus)[: args.limit] if args.limit else load_corpus(args.corpus)
    print(f"películas: {len(movies)}", flush=True)

    results = {"E1_offset": {}, "E2_semantic": {}, "E3_ablation": {}}

    # ================= E1: OFFSET SWEEP =================
    print("\n--- E1: offset sweep (p80_q2_t1) ---", flush=True)
    for offset in range(-10, 11, 2):
        f1s = []
        for npz, meta, sigs in movies:
            n = meta["n_shots"]
            try:
                pred, plan = run_config(
                    {"transcript": sigs["tfidf"], "visual": sigs["visual"]},
                    None, n, 80, 2, 1, offset=offset)
                _, _, f1 = boundary_f1(pred, meta["gt_scene_cuts"], args.tol_shots)
                f1s.append(f1)
            except Exception:
                pass
        f1m = np.mean(f1s) if f1s else 0
        results["E1_offset"][offset] = round(float(f1m), 4)
        print(f"  offset {offset:+3d}: F1 = {f1m:.4f}", flush=True)

    # ================= E2: corpus TF-IDF + LSA =================
    print("\n--- E2: corpus TF-IDF + LSA ---", flush=True)
    try:
        lsa_per_movie = corpus_tfidf_lsa(movies, n_components=64)
        for offset in (0, -5, 5):
            f1s = []
            for (npz, meta, sigs), lsa in zip(movies, lsa_per_movie):
                n = meta["n_shots"]
                try:
                    plan = manage({"transcript": lsa, "visual": sigs["visual"]},
                                  n_segments=n, percentile=80, link_quorum=2,
                                  tolerance_bins=1)
                    pred = [int(i) for i in range(1, len(plan.labels))
                            if plan.labels[i] != plan.labels[i - 1]]
                    pred = [max(0, min(n - 1, p + offset)) for p in pred]
                    _, _, f1 = boundary_f1(pred, meta["gt_scene_cuts"],
                                           args.tol_shots)
                    f1s.append(f1)
                except Exception:
                    pass
            f1m = np.mean(f1s) if f1s else 0
            key = f"lsa_offset{offset:+d}"
            results["E2_semantic"][key] = round(float(f1m), 4)
            print(f"  {key}: F1 = {f1m:.4f}", flush=True)
    except Exception as e:
        print(f"[E2] error: {e}", flush=True)
        results["E2_semantic"] = {"error": str(e)}

    # ================= E3: ablation con offset óptimo =================
    print("\n--- E3: ablation (offset mejor de E1) ---", flush=True)
    best_offset = max(results["E1_offset"], key=results["E1_offset"].get)
    for sig_name in ("transcript", "visual", "both"):
        f1s = []
        for npz, meta, sigs in movies:
            n = meta["n_shots"]
            try:
                if sig_name == "transcript":
                    sigs = {"transcript": sigs["tfidf"]}
                elif sig_name == "visual":
                    sigs = {"visual": sigs["visual"]}
                else:
                    sigs = {"transcript": sigs["tfidf"], "visual": sigs["visual"]}
                plan = manage(sigs, n_segments=n, percentile=80,
                              link_quorum=2, tolerance_bins=1)
                pred = [int(i) for i in range(1, len(plan.labels))
                        if plan.labels[i] != plan.labels[i - 1]]
                pred = [max(0, min(n - 1, p + best_offset)) for p in pred]
                _, _, f1 = boundary_f1(pred, meta["gt_scene_cuts"], args.tol_shots)
                f1s.append(f1)
            except Exception:
                pass
        f1m = np.mean(f1s) if f1s else 0
        results["E3_ablation"][sig_name] = round(float(f1m), 4)
        print(f"  {sig_name}: F1 = {f1m:.4f}", flush=True)

    results["best_offset_E1"] = best_offset
    out = Path(args.corpus).parent / "results" / "experiment_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1))
    print(f"\n[out] {out}")


if __name__ == "__main__":
    main()
