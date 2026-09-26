"""Demo CPU sobre BLiSS local: segmentación temática + agregación.

Usa transcripts REALES (RoBERTa 768-d por sentencia, ya extraídos) de clips
BLiSS. Sin videos, sin GPU. Muestra: tópicos detectados, grupos que ENLAZAN
sub-segmentos no adyacentes (mecanismo conecta-los-puntos), y distribución de
importancia humana (video_label) por grupo tópico (reporte, no gate).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.signals import TranscriptSignal
from topicagg.topic_segmenter import detect_boundaries, segment_topic_labels, boundary_scores
from topicagg.topic_aggregator import aggregate_by_topic

ROOT = Path("/home/edgar.chambilla/Tesis/GraphVSum/dataset/BLiSS")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clip", default=None, help="clip_id (default: 3 primeros con >=20 sentencias)")
    ap.add_argument("--n-demo", type=int, default=3)
    ap.add_argument("--link-threshold", type=float, default=0.55)
    args = ap.parse_args()

    anno = json.load(open(ROOT / "annotation" / "train.json"))
    feats = np.load(ROOT / "feature" / "text_roberta_train.npy", allow_pickle=True).item()

    clip_ids = [args.clip] if args.clip else [
        c for c in anno
        if c in feats and anno[c]["num_sentence"] >= 20][: args.n_demo]
    if args.clip and args.clip not in feats:
        sys.exit(f"clip {args.clip} sin features roberta")

    for cid in clip_ids:
        a = anno[cid]
        sig = TranscriptSignal(a["sentence"], a["sentence_time"], feats[cid])
        times, embs = sig.segment_embeddings(0.0, float(a["time"][1]), step_s=2.0)
        if len(embs) < 8:
            print(f"[skip] {cid}: {len(embs)} sub-segmentos")
            continue
        cuts = detect_boundaries(embs, w=3, percentile=80.0, min_gap=3)
        labels = segment_topic_labels(embs, cuts)
        groups = aggregate_by_topic(embs, cuts, link_threshold=args.link_threshold)
        print(f"\n=== {cid} | dur {a['time'][1]}s | {len(a['sentence'])} sentencias "
              f"| {len(embs)} sub-seg 2s | {len(cuts)} cortes temáticos ===")
        lab_counts = {int(t): int((labels == t).sum()) for t in np.unique(labels)}
        print(f"  tópicos contiguos: {lab_counts}")
        # importancia humana por grupo tópico (reporte, no gate)
        vlab = np.asarray(a["video_label"], dtype=np.float32)
        step = max(1, len(vlab) // max(1, len(embs)))
        print(f"  {'grupo':>6} {'segs':>5} {'coherencia':>10} {'segno-adyacentes':>16} "
              f"{'%importancia':>12}")
        for g in groups:
            nonadj = sum(1 for i, j in zip(g.segment_indices, g.segment_indices[1:])
                         if j - i > 1)
            idx_v = [min(int(i * step), len(vlab) - 1) for i in g.segment_indices]
            imp = 100.0 * float(vlab[idx_v].mean()) if idx_v else 0.0

            def rep_sentence(i, _a=a, _t=times):
                t_mid = _t[i][0] + (_t[i][1] - _t[i][0]) / 2
                best = max(range(len(_a["sentence_time"])),
                           key=lambda si: min(_a["sentence_time"][si][1], t_mid)
                                           - max(_a["sentence_time"][si][0], t_mid - 9999))
                return _a["sentence"][best]

            ends = ([g.segment_indices[0], g.segment_indices[-1]]
                    if len(g.segment_indices) > 1 else g.segment_indices)
            rep = " | " + " … ".join(rep_sentence(i) for i in ends)
            print(f"  T{g.topic_id:<5} {len(g.segment_indices):>5} {g.coherence:>10.3f} "
                  f"{nonadj:>16} {imp:>11.1f}%  {rep[:90]}")


if __name__ == "__main__":
    main()
