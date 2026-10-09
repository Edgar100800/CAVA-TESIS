"""Estadísticas descriptivas de una ejecución, sin métricas contra ground truth."""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching


def describe(x):
    x = np.asarray(x, dtype=float)
    return {"count": len(x), "mean": float(x.mean()), "median": float(np.median(x)),
            "std_population": float(x.std()), "min": float(x.min()),
            "p25": float(np.percentile(x, 25)), "p75": float(np.percentile(x, 75)),
            "p90": float(np.percentile(x, 90)), "max": float(x.max())}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("result_dir", type=Path)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    root = args.result_dir
    result = json.loads((root / "topics.json").read_text())
    windows = result["windows"]
    groups = result["groups"]
    duration = result["protocol"]["analyzed_seconds"]
    bin_s = result["protocol"]["bin_seconds"]
    cuts = np.array(result["cut_seconds"], dtype=float)
    lengths = np.diff(np.r_[0, cuts, duration])
    window_lengths = np.array([w["end"] - w["start"] for w in windows])
    assert np.isclose(lengths.sum(), duration)
    assert sorted(i for g in groups for i in g["segment_indices"]) == list(range(len(windows)))
    group_rows = []
    for g in groups:
        idx = g["segment_indices"]
        runs = []
        for i in idx:
            if runs and i == runs[-1][-1] + 1:
                runs[-1].append(i)
            else:
                runs.append([i])
        group_rows.append({"topic_id": g["topic_id"], "windows": len(idx),
                           "duration_seconds": float(window_lengths[idx].sum()),
                           "runs": len(runs), "no_topic": g["no_topic"],
                           "needs_review": g["needs_review"],
                           "intervals": [[windows[r[0]]["start"], windows[r[-1]]["end"]] for r in runs]})
    def subset_stats(predicate):
        selected = [g for g in group_rows if predicate(g)]
        seconds = sum(g["duration_seconds"] for g in selected)
        return {"groups": len(selected), "windows": sum(g["windows"] for g in selected),
                "duration_seconds": seconds, "video_percent": seconds / duration * 100}
    ranked = sorted(group_rows, key=lambda g: g["duration_seconds"], reverse=True)
    transcript = np.array(result["per_signal_cuts"]["transcript"])
    visual = np.array(result["per_signal_cuts"]["visual"])
    agreement = []
    for tol in [0, 1, 2]:
        mask = abs(transcript[:, None] - visual[None, :]) <= tol
        matches = int((maximum_bipartite_matching(csr_matrix(mask), perm_type="column") >= 0).sum())
        agreement.append({"tolerance_seconds": tol * bin_s, "matched_pairs": matches,
                          "transcript_percent_matched": 100 * matches / len(transcript),
                          "visual_percent_matched": 100 * matches / len(visual),
                          "symmetric_agreement": 2 * matches / (len(transcript) + len(visual))})
    blocks = []
    for start in np.arange(0, duration, 1800):
        end = min(start + 1800, duration)
        count = int(((cuts >= start) & (cuts < end)).sum())
        blocks.append({"start_seconds": float(start), "end_seconds": float(end),
                       "cuts": count, "cuts_per_minute": count / ((end - start) / 60)})
    cues = json.loads((root / "transcript.json").read_text())
    spans = sorted((max(0, c["start"]), min(duration, c["end"])) for c in cues)
    union = 0.0
    previous_end = 0.0
    for a, b in spans:
        union += max(0.0, b - max(a, previous_end))
        previous_end = max(previous_end, b)
    stats = {"duration_seconds": duration, "windows": len(windows),
             "segments_between_cuts_seconds": describe(lengths),
             "segment_duration_bins": {"less_than_30s": int((lengths < 30).sum()),
                                       "30_to_60s": int(((lengths >= 30) & (lengths < 60)).sum()),
                                       "60_to_180s": int(((lengths >= 60) & (lengths < 180)).sum()),
                                       "180_to_300s": int(((lengths >= 180) & (lengths < 300)).sum()),
                                       "at_least_300s": int((lengths >= 300).sum())},
             "consensus_cuts": len(cuts), "consensus_cuts_per_minute": len(cuts) / (duration / 60),
             "group_windows": describe([g["windows"] for g in group_rows]),
             "group_durations_seconds": describe([g["duration_seconds"] for g in group_rows]),
             "no_topic": subset_stats(lambda g: g["no_topic"]),
             "needs_review": subset_stats(lambda g: g["needs_review"]),
             "supported_without_review": subset_stats(lambda g: not g["no_topic"] and not g["needs_review"]),
             "noncontiguous": subset_stats(lambda g: g["runs"] > 1),
             "top5_video_percent": sum(g["duration_seconds"] for g in ranked[:5]) / duration * 100,
             "largest_groups": ranked[:10], "signal_cut_counts": {"transcript": len(transcript), "visual": len(visual)},
             "signal_cut_agreement_one_to_one": agreement, "half_hour_blocks": blocks,
             "transcription": {"segments": len(cues), "segment_duration_seconds": describe([c["end"]-c["start"] for c in cues]),
                               "words": sum(len(c["text"].split()) for c in cues),
                               "window_text_coverage_percent": 100 * result["text_windows"] / len(windows),
                               "asr_interval_union_seconds": union,
                               "asr_interval_coverage_percent": 100 * union / duration},
             "limitations": ["Un video, sin ground truth: no mide precisión, recall ni calidad semántica.",
                             "Acuerdo simétrico es acuerdo entre señales, no F1 contra etiquetas.",
                             "Duración de grupos suma fragmentos; no es un intervalo continuo.",
                             "Cobertura ASR usa intervalos emitidos, no una medida exacta de tiempo hablado.",
                             "Tolerancia de consenso ±1 ventana por señal permite cortes separados hasta 20s."]}
    (root / "statistics.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in stats.items() if k != "largest_groups"}, ensure_ascii=False, indent=2))
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.6))
        axes[0].hist(lengths / 60, bins=[0, .5, 1, 2, 3, 5, 8, 12], color="#267b9c", edgecolor="white")
        axes[0].set(title="Duración de los 79 tramos", xlabel="Minutos", ylabel="Número de tramos")
        axes[0].axvline(np.median(lengths)/60, color="#c95935", linestyle="--", label="Mediana")
        axes[0].legend()
        colors = ["#c95935" if g["needs_review"] else "#267b9c" for g in ranked[:15]]
        axes[1].bar([str(g["topic_id"]) for g in ranked[:15]], [g["duration_seconds"]/60 for g in ranked[:15]], color=colors)
        axes[1].set(title="15 grupos mayores (rojo: revisar)", xlabel="ID de grupo", ylabel="Minutos acumulados")
        axes[2].bar(np.arange(len(blocks)), [b["cuts"] for b in blocks], color="#267b9c")
        axes[2].set_xticks(np.arange(len(blocks)), ["0–30", "30–60", "60–90", "90–120", "120–150", "150–179"])
        axes[2].set(title="Cortes por bloque temporal", xlabel="Minutos del video", ylabel="Cortes")
        fig.suptitle("CAVA · The Wild Project #384 · Estadísticas descriptivas")
        fig.tight_layout()
        fig.savefig(root / "statistics.png", dpi=180)
        fig.savefig(root / "statistics.pdf")
        plt.close(fig)


if __name__ == "__main__":
    main()
