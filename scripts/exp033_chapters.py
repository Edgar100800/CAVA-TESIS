"""EXP-033: nivel de capítulo. --mode dev (raw_ext: elige L) | --mode conf (blind40: criterios con L congelado)."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import f1_b, local_pairs, m_local  # noqa: E402
from eval_vidchapters import VC, chapters as load_chapters, product_labels  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from topicagg.chapters import chapters, labels_from_boundaries, top_n_boundaries  # noqa: E402
from topicagg.multimodal_manager import signal_boundary  # noqa: E402

LS = (90, 120, 150, 180, 240, 300)


def load(run, bge):
    w = run / "work"
    doc = json.loads((run / "topic_map.json").read_text())
    st, z = json.loads((w / "state.json").read_text()), np.load(w / "signals.npz")
    sums = json.loads((w / "summaries.json").read_text())
    units = doc["unit_times"]
    n = len(units)
    e = bge([s["summary"] for s in sums])
    vj = np.zeros((n, e.shape[1]), np.float32)
    for s, v in zip(sums, e):
        vj[s["lo"]:min(s["hi"], n)] = v
    sig = {"voice": np.asarray(z["voice"][:n], np.float32), "visual": np.asarray(z["visual"][:n], np.float32),
           "transcript": bge(st["asr"][:n]), "vjudge": vj}
    return doc, units, sig, float(st["duration"])


def evaluate(runs_dir, ids, bge, Ls):
    ch = load_chapters()
    rows = {}
    for vid in ids:
        run = Path(runs_dir) / vid
        if not (run / "topic_map.json").exists() or vid not in ch:
            continue
        doc, units, sig, D = load(run, bge)
        n = len(units)
        starts = sorted(float(t) for t in ch[vid]["chapters"])
        gt = np.array([int(np.searchsorted(starts, (a + b) / 2, side="right") - 1) for a, b in units])
        I, J = local_pairs(n)
        mapl = product_labels(doc, n)
        r = {"n_chapters_gt": len(starts)}
        for L in Ls:
            N = max(0, int(round(D / L)) - 1)
            cand = {"chapters": chapters(mapl, sig, D, L), "uniform": (np.arange(n) * (N + 1) // n).astype(int)}
            for k in ("visual", "transcript"):
                s = signal_boundary(sig[k])
                cand[f"top_{k}"] = labels_from_boundaries(n, top_n_boundaries(np.arange(n - 1), s, N))
            for k, lab in cand.items():
                r[f"L{L}_{k}_m"] = m_local(lab, [gt], I, J)
                r[f"L{L}_{k}_f3"] = f1_b(lab, [gt], tol=3)
        rows[vid] = r
        print(vid, " ".join(f"L{L}={r[f'L{L}_chapters_m']:.3f}" for L in Ls), flush=True)
    return rows


def paired(rows, a, b):
    d = np.array([x[a] - x[b] for x in rows.values()])
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d), "z": round(float(d.mean() / se), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dev", "conf"], required=True)
    mode = ap.parse_args().mode
    bge = BgeEmbedder()
    if mode == "dev":
        ids = sorted(p.name for p in Path("data/cava_runs_v1_dev").iterdir() if p.is_dir())
        rows = evaluate("data/cava_runs_v1_dev", ids, bge, LS)
        means = {L: round(float(np.mean([x[f"L{L}_chapters_m"] for x in rows.values()])), 4) for L in LS}
        best = max(means, key=means.get)
        rep = {"n": len(rows), "means_chapters_m": means, "L": best,
               "means_uniform_m": {L: round(float(np.mean([x[f"L{L}_uniform_m"] for x in rows.values()])), 4) for L in LS},
               "dev_vs_uniform_at_L": paired(rows, f"L{best}_chapters_m", f"L{best}_uniform_m"), "per_video": rows}
        Path("results/exp033_dev.json").write_text(json.dumps(rep, indent=1))
    else:
        L = json.loads(Path("results/exp033_dev.json").read_text())["L"]
        ids = json.loads((VC / "blind40" / "selection.json").read_text())["video_ids"]
        rows = evaluate("data/cava_runs_v1", ids, bge, (L,))
        for x in rows.values():
            x["best_single_m"] = max(x[f"L{L}_top_visual_m"], x[f"L{L}_top_transcript_m"])
        rep = {"L": L, "n": len(rows),
               "c1_m_vs_uniform": paired(rows, f"L{L}_chapters_m", f"L{L}_uniform_m"),
               "c2_f3_vs_uniform": paired(rows, f"L{L}_chapters_f3", f"L{L}_uniform_f3"),
               "c3_m_vs_best_single": paired(rows, f"L{L}_chapters_m", "best_single_m"),
               "means": {k: round(float(np.mean([x[k] for x in rows.values()])), 4) for k in next(iter(rows.values()))},
               "per_video": rows}
        Path("results/exp033_conf.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_video"}, indent=1))


if __name__ == "__main__":
    main()
