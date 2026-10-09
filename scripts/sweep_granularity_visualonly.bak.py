"""Sweep de granularidad con registro quant+qual (EXP-010).

Grid: percentile {70,80,90} × link_quorum {1,2} × tolerance_bins {0,1}
Señales: transcript (TF-IDF de ASR) + visual (SigLIP/BaSSL fusión)

Métricas por configuración por video:
  - quant: n_groups, sizes (min/med/max), needs_review, no_topic
  - quant: coherencia intra por señal (coseno medio)
  - qual: provenance (soporte por señal por grupo)

Salida: results/granularity_sweep.json + .md
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/edgar.chambilla/Tesis/CAVA")
sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")
from topicagg.multimodal_manager import manage  # noqa: E402

VIDEOS = ["Hl-__g2gn_A", "AwmHb44_ouw", "98MoyGZKHXc"]
FUSION_DIR = Path("/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/processing/segmenter/siglip_bassl_fusion")
SHOTS_PATH = Path("/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/processing/segmenter/shots.ndjson")


def _l2(x):
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / (n + 1e-8)


def load_video_data(vid, shots_by_video):
    """Carga visual + transcript embeddings para un video."""
    npz = FUSION_DIR / f"{vid}.npz"
    if not npz.exists():
        return None
    d = np.load(npz)
    visual = np.asarray(d["tokens"], np.float32)
    n = len(visual)

    # transcript: shots del manifest (usamos los shots para delimitar)
    shots = sorted([r for r in shots_by_video.get(vid, [])],
                   key=lambda r: int(r["shot_id"]))
    n_shots = min(n, len(shots))

    # visual y transcript deben tener el mismo número de segmentos
    # visual: [n, 2818] del npz de fusión
    # transcript: TF-IDF del ASR — no disponible en el piloto, usamos
    # cero vectors como placeholder (la señal transcript real viene de ASR)
    return {"visual": visual[:n_shots], "n": n_shots, "shots": shots[:n_shots]}


def compute_group_metrics(groups, embs):
    """Métricas por grupo: tamaño, coherencia intra (coseno), etc."""
    sizes = [len(g.segment_indices) for g in groups]
    no_topic = sum(1 for g in groups if getattr(g, "no_topic", False))
    needs_review = sum(1 for g in groups if getattr(g, "needs_review", False))
    return {
        "n_groups": len(groups),
        "mean_size": round(float(np.mean(sizes)), 2) if sizes else 0,
        "size_min": min(sizes) if sizes else 0,
        "size_max": max(sizes) if sizes else 0,
        "needs_review": needs_review,
        "no_topic": no_topic,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="results/granularity_sweep_v2.json")
    ap.add_argument("--limit-videos", type=int, default=0)
    args = ap.parse_args()

    # cargar shots manifest
    shots_by_video = {}
    for line in open(SHOTS_PATH):
        r = json.loads(line)
        shots_by_video.setdefault(r["video_id"], []).append(r)

    # cargar ASR + visual embeddings por video
    videos = VIDEOS[: args.limit_videos] if args.limit_videos else VIDEOS
    video_data = {}
    for vid in videos:
        vd = load_video_data(vid, shots_by_video)
        if vd is not None:
            video_data[vid] = vd
            print(f"[load] {vid}: {vd['n']} shots", flush=True)

    grid = list(itertools.product((70, 80, 90), (1, 2), (0, 1)))

    all_results = {}
    for p, q, tb in grid:
        key = f"p{p}_q{q}_t{tb}"
        vid_metrics = {}
        for vid, vd in video_data.items():
            try:
                plan = manage({"visual": vd["visual"]}, n_segments=vd["n"],
                              percentile=p, link_quorum=q,
                              tolerance_bins=tb, max_group_segments=10)
                m = compute_group_metrics(plan.groups, vd["visual"])
                vid_metrics[vid] = m
            except Exception as e:
                vid_metrics[vid] = {"error": str(e)[:80]}

        # agregar entre videos
        agg = {"config": key, "percentile": p, "link_quorum": q,
               "tolerance_bins": tb}
        for field in ("n_groups", "mean_size", "needs_review", "no_topic"):
            vals = [m[field] for m in vid_metrics.values() if field in m]
            agg[field + "_mean"] = round(float(np.mean(vals)), 3) if vals else None
        all_results[key] = agg
        print(f"[sweep] {key}: grupos={agg['n_groups_mean']:.1f} "
              f"needs_review={agg['needs_review_mean']:.0f} "
              f"no_topic={agg['no_topic_mean']:.0f}", flush=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"grid": grid, "results": all_results}, indent=1))
    print(f"[out] {out}", flush=True)


if __name__ == "__main__":
    import itertools
    main()
