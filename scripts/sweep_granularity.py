"""Ticket 002 (wayfinder): barrido de granularidad con registro cuantitativo.

Grid: percentile {70,80,90} × link_quorum {1,2} × tolerance_bins {0,1}
sobre los 3 videos piloto. Los embeddings (transcript TF-IDF + visual
SigLIP/BaSSL) se calculan UNA vez por video; el grid solo re-instancia
manage(). Métricas por configuración y video:

  - n_groups, tamaños min/med/max, needs_review, no_topic
  - coherencia intra por señal (coseno al centroide del grupo)
  - separación inter (1 − coseno entre centroides de grupos contiguos)
  - provenance media (soporte multi-señal)
  - tasa de cortes confirmados (consenso / candidatos por señal)

Salida: results/granularidad/sweep.json + sweep.md (tabla).
"""
import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from topicagg.multimodal_manager import manage  # noqa: E402
from topicagg.signals.core import TranscriptSignal  # noqa: E402
from topicagg.signals.core import TranscriptSignal  # noqa: E402


def tfidf_embeddings(bins_text):
    vocab = {}
    docs = []
    for txt in bins_text:
        toks = [w for w in "".join(c if c.isalnum() else " " for c in txt.lower()).split()
                if len(w) > 2]
        docs.append(toks)
        for w in set(toks):
            vocab.setdefault(w, len(vocab))
    n_docs = len(docs)
    df = np.zeros(len(vocab))
    for toks in docs:
        for w in set(toks):
            df[vocab[w]] += 1
    idf = np.log((1 + n_docs) / (1 + df)) + 1.0
    rows = []
    for toks in docs:
        v = np.zeros(len(vocab), dtype=np.float32)
        for w in toks:
            v[vocab[w]] += 1.0
        for w in set(toks):
            v[vocab[w]] *= idf[vocab[w]]
        n = np.linalg.norm(v)
        rows.append(v / n if n > 0 else v)
    return np.asarray(rows, dtype=np.float32)


def cosine(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na > 0 and nb > 0 else 0.0


def group_metrics(groups, signals):
    """Coherencia intra por señal + separación inter + soporte medio."""
    intra = {name: [] for name in signals}
    for g in groups:
        idx = g.segment_indices
        if getattr(g, "no_topic", False) or len(idx) < 2:
            continue
        for name, embs in signals.items():
            x = embs[idx]
            c = x.mean(axis=0)
            nc = np.linalg.norm(c)
            cn = c / nc if nc > 0 else c
            xn = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-8)
            intra[name].append(float((xn @ cn).mean()))
    intra_mean = {k: round(float(np.mean(v)), 4) if v else None for k, v in intra.items()}

    # separación inter: 1 − coseno entre centroides de grupos contiguos
    big = [g for g in groups
           if not getattr(g, "no_topic", False) and len(g.segment_indices) >= 1]
    seps = []
    for a, b in zip(big, big[1:]):
        ca = signals["visual"][a.segment_indices].mean(axis=0)
        cb = signals["visual"][b.segment_indices].mean(axis=0)
        seps.append(1.0 - cosine(ca, cb))
    inter_sep = round(float(np.mean(seps)), 4) if seps else None

    supports = [round(float(np.mean(list(g.signal_support.values()))), 3)
                for g in groups if g.signal_support]
    return {"intra_coherence": intra_mean, "inter_separation": inter_sep,
            "mean_support": round(float(np.mean(supports)), 3) if supports else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--fusion-dir", required=True)
    ap.add_argument("--asr-device", default="cpu")
    ap.add_argument("--out", default="results/granularidad")
    args = ap.parse_args()

    from segloop.io import video_loader, asr_whisper

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    grid = list(itertools.product((70, 80, 90), (1, 2), (0, 1)))
    per_video = {}

    for video in args.videos:
        vid = Path(video).stem
        print(f"\n===== {vid} =====", flush=True)

        segs = asr_whisper.transcribe(video, model_size="tiny",
                                      device=args.asr_device, compute_type="int8")
        sentences = [s.text for s in segs]
        times = [[float(s.start), float(s.end)] for s in segs]

        from segloop.io import video_loader
        meta = video_loader.read_meta(video)
        dur = meta.num_frames / meta.fps
        n_bins = int(dur // 2)
        bins_text = []
        for b in range(n_bins):
            t0, t1 = b * 2, (b + 1) * 2
            bins_text.append(" ".join(s for s, (a, bb) in zip(sentences, times)
                                      if a < t1 and bb > t0))
        transcript = tfidf_embeddings(bins_text)
        speech_times = times

        npz = Path(args.fusion_dir) / f"{vid}.npz"
        fdata = np.load(npz)
        visual = fdata["tokens"].astype(np.float32)
        n = min(len(transcript), len(visual))
        signals = {"transcript": transcript[:n], "visual": visual[:n]}
        st = [t for t in times if t[0] / 2 < n]
        speech_t = [[a, min(b, n * 2)] for a, b in speech_times if a / 2 < n]

        vid_results = {}
        for percentile, link_quorum, tolerance_bins in grid:
            plan = manage({"transcript": signals["transcript"],
                           "visual": signals["visual"]},
                          speech_times=speech_t, n_segments=n,
                          percentile=percentile, link_quorum=link_quorum,
                          tolerance_bins=tolerance_bins)
            sizes = [len(g.segment_indices) for g in plan.groups]
            gm = group_metrics(plan.groups, signals)
            n_cand = sum(len(c) for c in plan.per_signal_cuts.values())
            vid_results[f"p{percentile}_q{link_quorum}_t{tolerance_bins}"] = {
                "n_groups": len(plan.groups),
                "sizes_min_med_max": [int(min(sizes)), int(np.median(sizes)),
                                      int(max(sizes))] if sizes else [],
                "needs_review": sum(1 for g in plan.groups
                                    if getattr(g, "needs_review", False)),
                "no_topic": sum(1 for g in plan.groups
                                if getattr(g, "no_topic", False)),
                "consensus_cuts": len(plan.consensus_cuts),
                "candidate_cuts": n_cand,
                "confirm_rate": round(len(plan.consensus_cuts) / n_cand, 3)
                                if n_cand else None,
                **gm,
            }
        per_video[vid] = vid_results
        print(f"[sweep] {vid}: {len(grid)} configuraciones registradas", flush=True)

    # agregado por configuración (media entre videos)
    keys = list(next(iter(per_video.values())).keys())
    aggregate = {}
    for k in keys:
        runs = [per_video[vid][k] for vid in per_video if k in per_video[vid]]
        agg = {"n_videos": len(runs)}
        for field in ("n_groups", "needs_review", "no_topic",
                      "precision_at_k" if False else "confirm_rate"):
            vals = [r[field] for r in runs if r.get(field) is not None]
            if vals:
                agg[field + "_mean"] = round(float(np.mean(vals)), 4)
        for field in ("intra_coherence",):
            per_sig = {}
            for name in ("transcript", "visual"):
                vals = [r[field][name] for r in runs
                        if r.get(field) and r[field].get(name) is not None]
                if vals:
                    per_sig[name] = round(float(np.mean(vals)), 4)
            agg[field] = per_sig
        sizes_max = [r["sizes_min_med_max"][2] for r in runs
                     if r.get("sizes_min_med_max")]
        if sizes_max:
            agg["max_group_mean"] = round(float(np.mean(sizes_max)), 1)
        aggregate[k] = agg

    sweep = {
        "protocol": "granularity_sweep_v1_quant",
        "grid": {"percentile": [70, 80, 90], "link_quorum": [1, 2],
                 "tolerance_bins": [0, 1]},
        "videos": list(per_video.keys()),
        "per_video": per_video,
        "aggregate": aggregate,
    }
    (out / "sweep.json").write_text(json.dumps(sweep, indent=1))

    lines = ["| config | grupos | needs_review | no_topic | confirm_rate | "
             "intra transcript | intra visual |", "|---|---|---|---|---|---|---|"]
    for k in keys:
        a = aggregate[k]
        lines.append(f"| {k} | {a.get('n_groups_mean', a.get('n_groups'))} "
                     f"| {a.get('needs_review_mean','-')} "
                     f"| {a.get('no_topic_mean','-')} "
                     f"| {a.get('confirm_rate_mean','-')} "
                     f"| {a.get('intra_coherence',{}).get('transcript','-')} "
                     f"| {a.get('intra_coherence',{}).get('visual','-')} |")
    table = "\n".join(lines)
    (out / "sweep.md").write_text(
        "# Barrido de granularidad (quant)\n\n" + table + "\n")
    print(table)


if __name__ == "__main__":
    main()
