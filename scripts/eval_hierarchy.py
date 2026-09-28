"""EXP-011 paso 0: baseline jerárquico — escenas (~120) y beats de trama (~11).

MovieNet `annotation/<tt>.json` trae `story`: párrafos de sinopsis alineados a
rangos de shots. Eso da GT en dos niveles sobre el mismo eje de shots:

  escena  cortes de `gt_scene_cuts` (corpus)          tolerancia ±15 s
  beat    inicios de cada párrafo `story` (sin el 1º)  tolerancia ±60 s,
          evaluado solo dentro del tramo anotado [inicio 1er beat, fin último]

Métricas por sistema y película:
  F1 de fronteras por nivel · Pk por nivel (error de segmentación, menor es
  mejor, k = media GT / 2) · scene_prec (fracción de cortes predichos a ±1 shot
  de un corte de escena: ¿el tópico respeta la estructura?) · n_topics.
  Cada métrica con su azar (mismo nº de cortes, 50 sorteos).

Sistemas: manage(visual+transcript), percentil × link_quorum (q1 ≈ cortes
compartidos por ambas señales → grueso; q2 ≈ unión → fino) + consenso de
votos. El baseline "mejor percentil fijo por nivel" usa el GT para elegir; es
el techo que el agregador adaptativo debe superar con UNA sola salida.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.multimodal_manager import manage  # noqa: E402

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")


def load_split(name):
    return {json.loads(l)["video_id"] for l in open(MN / "anno" / f"anno.{name}.ndjson")}


def f1_at(pred_s, gt_s, tol):
    used, matched = set(), 0
    for p in pred_s:
        best = None
        for gi, g in enumerate(gt_s):
            if gi not in used and abs(p - g) <= tol and (
                    best is None or abs(p - g) < abs(p - gt_s[best])):
                best = gi
        if best is not None:
            used.add(best)
            matched += 1
    P = matched / len(pred_s) if pred_s else 0.0
    R = matched / len(gt_s) if gt_s else 0.0
    return (2 * P * R / (P + R)) if P + R else 0.0


def labels_from_cuts(cuts, lo, hi):
    lab = np.zeros(hi - lo, dtype=int)
    for c in sorted(c for c in cuts if lo < c < hi):
        lab[c - lo:] += 1
    return lab


def pk(ref_cuts, hyp_cuts, lo, hi):
    ref, hyp = labels_from_cuts(ref_cuts, lo, hi), labels_from_cuts(hyp_cuts, lo, hi)
    n_seg = ref.max() + 1
    k = max(1, int(round((hi - lo) / n_seg / 2)))
    if hi - lo <= k:
        return None
    a = ref[:-k] == ref[k:]
    b = hyp[:-k] == hyp[k:]
    return float(np.mean(a != b))


def scene_prec(pred, scene_cuts):
    if not pred:
        return 0.0
    sc = np.asarray(scene_cuts)
    return float(np.mean([np.min(np.abs(sc - p)) <= 1 for p in pred]))


def metrics(pred, g):
    st = g["shot_times"]
    t = lambda cuts: [st[c][0] for c in cuts]  # noqa: E731
    lo, hi = g["beat_span"]
    pred_in = [c for c in pred if lo < c < hi]
    return {
        "n_topics": len(pred) + 1,
        "scene_f1": f1_at(t(pred), t(g["scene"]), 15.0),
        "scene_pk": pk(g["scene"], pred, 0, g["n"]),
        "beat_f1": f1_at(t(pred_in), t(g["beat"]), 60.0),
        "beat_pk": pk(g["beat"], pred_in, lo, hi),
        "scene_prec": scene_prec(pred, g["scene"]),
    }


def random_metrics(n_cuts, g, rng, draws=50):
    rows = []
    for _ in range(draws):
        pred = sorted(rng.choice(np.arange(1, g["n"]), min(n_cuts, g["n"] - 1),
                                 replace=False).tolist()) if n_cuts else []
        rows.append(metrics(pred, g))
    return {k: float(np.mean([r[k] for r in rows if r[k] is not None]))
            for k in rows[0] if k != "n_topics"}


def load_film(tt, corpus):
    c = json.loads((corpus / f"{tt}.json").read_text())
    a = json.loads((MN / "annotation" / f"{tt}.json").read_text())
    story = sorted(a.get("story") or [], key=lambda s: s["shot"][0])
    d = np.load(corpus / f"{tt}.npz")
    n = min(c["n_shots"], len(d["visual"]))
    if not story:
        return None
    lo = story[0]["shot"][0]
    hi = min(n, max(s["shot"][1] for s in story) + 1)
    beat = sorted({s["shot"][0] for s in story[1:] if lo < s["shot"][0] < hi})
    return {"tt": tt, "n": n, "shot_times": c["shot_times"][:n],
            "scene": [x for x in c["gt_scene_cuts"] if x < n],
            "beat": beat, "beat_span": [lo, hi],
            "signals": {"visual": np.asarray(d["visual"][:n], np.float32),
                        "transcript": np.asarray(d["tfidf"][:n], np.float32)}}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="val")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--percentiles", type=float, nargs="+",
                    default=[50, 60, 70, 80, 90, 95, 98])
    ap.add_argument("--out", default="results/exp011_hierarchy_baseline.json")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--films", nargs="+", default=None, help="restringe a estos tt")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    corpus = Path(args.corpus)
    pool = sorted(set(args.films) if args.films else load_split(args.split))
    films = [load_film(tt, corpus) for tt in pool
             if (corpus / f"{tt}.json").exists() and (MN / "annotation" / f"{tt}.json").exists()]
    films = [f for f in films if f and len(f["beat"]) >= 2]
    print(f"[hier] {args.split}: {len(films)} películas con escenas + beats", flush=True)

    per_film = {}
    for g in films:
        rows = {}
        for p in args.percentiles:
            for q in (1, 2):
                plan = manage(g["signals"], n_segments=g["n"], percentile=p,
                              link_quorum=q, tolerance_bins=1)
                pred = [i for i in range(1, g["n"]) if plan.labels[i] != plan.labels[i - 1]]
                rows[f"p{p:g}_q{q}_labels"] = pred
            rows[f"p{p:g}_consensus"] = sorted(plan.consensus_cuts)
        per_film[g["tt"]] = {}
        for name, pred in rows.items():
            m = metrics(pred, g)
            r = random_metrics(len(pred), g, rng)
            per_film[g["tt"]][name] = m | {f"rand_{k}": v for k, v in r.items()}
        per_film[g["tt"]]["_gt"] = {"n_scenes": len(g["scene"]) + 1,
                                    "n_beats": len(g["beat"]) + 1,
                                    "beat_span": g["beat_span"], "n_shots": g["n"]}
        print(f"[hier] {g['tt']}: {len(g['scene']) + 1} escenas, {len(g['beat']) + 1} beats",
              flush=True)

    systems = [k for k in next(iter(per_film.values())) if k != "_gt"]
    agg = {}
    for s in systems:
        rows = [per_film[t][s] for t in per_film]
        agg[s] = {k: round(float(np.mean([r[k] for r in rows if r[k] is not None])), 4)
                  for k in rows[0]}
    report = {"protocol": "exp011_step0_hierarchy_v1", "split": args.split,
              "n_films": len(per_film), "tol_s": {"scene": 15, "beat": 60},
              "gt_mean": {k: float(np.mean([per_film[t]["_gt"][k] for t in per_film]))
                          for k in ("n_scenes", "n_beats", "n_shots")},
              "aggregate": agg, "per_film": per_film}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print(f"\nGT medio: {report['gt_mean']}")
    print("| sistema | tópicos | escena F1 (azar) | escena Pk (azar) | beat F1 (azar) "
          "| beat Pk (azar) | scene_prec (azar) |")
    print("|---|---|---|---|---|---|---|")
    for s, a in agg.items():
        print(f"| {s} | {a['n_topics']:.0f} | {a['scene_f1']:.3f} ({a['rand_scene_f1']:.3f}) "
              f"| {a['scene_pk']:.3f} ({a['rand_scene_pk']:.3f}) "
              f"| {a['beat_f1']:.3f} ({a['rand_beat_f1']:.3f}) "
              f"| {a['beat_pk']:.3f} ({a['rand_beat_pk']:.3f}) "
              f"| {a['scene_prec']:.3f} ({a['rand_scene_prec']:.3f}) |")
    print(f"[out] {out}")


if __name__ == "__main__":
    main()
