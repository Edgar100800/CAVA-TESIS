"""EXP-032: estructura de tópicos CAVA frente a los capítulos del autor (VidChapters blind40).

cava_doc = el mapa del PRODUCTO (topic_map.json, nivel default, perfil documentary) tal cual lo escribió el
pipeline v1. Las demás variantes se recalculan desde la caché de señales de esa misma corrida.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import f1_b, local_pairs, m_local  # noqa: E402
from eval_topic_map import l2  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402
from topicagg.topic_map import snap_boundaries  # noqa: E402

VC = Path("/home/edgar.chambilla/Tesis/SegLoop/data/vidchapters")
RUNS = Path("data/cava_runs_v1")
KW = dict(min_gap=2, tolerance_bins=1, link_quorum=2)
AB = KW | dict(link_mode="average", abstain=True, return_percentile=90)


def chapters():
    ch = {}
    for f in ("chapters_sml1k_train.json", "chapters_sml300_val.json"):
        ch.update(json.loads((VC / "chapters" / f).read_text()))
    return ch


def product_labels(doc, n):
    lab = np.full(n, -1)
    for t in doc["levels"]["default"]["topics"]:
        lab[[u for u in t["shots"] if u < n]] = t["topic_id"]
    return lab


def uniform(n, k):
    return (np.arange(n) * k // n).astype(int)


def main():
    ch = chapters()
    ids = json.loads((VC / "blind40" / "selection.json").read_text())["video_ids"]
    bge = BgeEmbedder()
    rows = {}
    for vid in ids:
        run = RUNS / vid
        w = run / "work"
        if not (run / "topic_map.json").exists():
            print(f"[vc] {vid}: sin corrida", flush=True)
            continue
        doc = json.loads((run / "topic_map.json").read_text())
        st, z = json.loads((w / "state.json").read_text()), np.load(w / "signals.npz")
        sums = json.loads((w / "summaries.json").read_text())
        units = doc["unit_times"]
        n = len(units)
        starts = sorted(float(t) for t in ch[vid]["chapters"])
        gt = np.array([int(np.searchsorted(starts, (a + b) / 2, side="right") - 1) for a, b in units])
        gts = [gt]
        e = bge([s["summary"] for s in sums])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for s, v in zip(sums, e):
            vj[s["lo"]:min(s["hi"], n)] = v
        sig = {"voice": np.asarray(z["voice"][:n], np.float32), "visual": np.asarray(z["visual"][:n], np.float32),
               "transcript": bge(st["asr"][:n]), "vjudge": vj}
        ends = np.array([b for _, b in units], float)
        ref = {q: np.asarray(manage({"visual": sig["visual"]}, percentile=q, **(AB | {"link_quorum": 1})).labels)
               for q in (80, 90)}
        fused = np.concatenate([l2(v) for v in sig.values()], 1)
        cand = {"cava_doc": product_labels(doc, n),
                "cava_film": snap_boundaries(np.asarray(manage(sig, percentile=80, **AB).labels), ref[80], ends, 30.0),
                "contiguous_p80": np.asarray(manage(sig, percentile=80, **KW).labels),
                "contiguous_p90": np.asarray(manage(sig, percentile=90, **KW).labels),
                "fused_p90": np.asarray(manage({"fused": fused}, percentile=90, return_percentile=90,
                                               **(KW | {"link_quorum": 1})).labels)}
        runs = int(1 + (cand["cava_doc"][1:] != cand["cava_doc"][:-1]).sum())
        cand["uniform_same_count"] = uniform(n, runs)
        cand["uniform_gt_count"] = uniform(n, len(starts))   # oráculo de nº de capítulos: solo referencia
        I, J = local_pairs(n)
        r = {"n_units": n, "n_chapters": len(starts), "cava_doc_runs": runs,
             "cava_doc_topics": doc["levels"]["default"]["n_topics"]}
        for k, lab in cand.items():
            r[f"m_local_{k}"] = m_local(lab, gts, I, J)
            r[f"f1b_{k}"] = f1_b(lab, gts)
            r[f"f1b3_{k}"] = f1_b(lab, gts, tol=3)
        rows[vid] = r
        print(f"[vc] {vid}: cap {len(starts)} runs {runs} | " + " ".join(
            f"{k}={r['m_local_' + k]:.3f}" for k in cand), flush=True)

    def paired(a, b):
        d = np.array([x[f"m_local_{a}"] - x[f"m_local_{b}"] for x in rows.values()])
        se = d.std(ddof=1) / np.sqrt(len(d))
        return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d), "z": round(float(d.mean() / se), 2)}
    best_contig = {v: max(x["m_local_contiguous_p80"], x["m_local_contiguous_p90"]) for v, x in rows.items()}
    d2 = np.array([rows[v]["m_local_cava_doc"] - best_contig[v] for v in rows])
    keys = [k for k in next(iter(rows.values())) if k.startswith(("m_local_", "f1b_", "f1b3_", "cava_doc_", "n_chap"))]
    rep = {"n_videos": len(rows),
           "criteria": {"c1_vs_uniform_same_count": paired("cava_doc", "uniform_same_count"),
                        "c2_vs_best_contiguous": {"mean": round(float(d2.mean()), 4),
                                                  "se": round(float(d2.std(ddof=1) / np.sqrt(len(d2))), 4),
                                                  "z": round(float(d2.mean() / (d2.std(ddof=1) / np.sqrt(len(d2)))), 2)},
                        "c3_vs_fused_p90": paired("cava_doc", "fused_p90")},
           "secondary": {"film_vs_doc": paired("cava_film", "cava_doc"),
                         "means": {k: round(float(np.mean([x[k] for x in rows.values()])), 4) for k in keys}},
           "per_video": rows}
    Path("results/exp032_vidchapters.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_video"}, indent=1))


if __name__ == "__main__":
    main()
