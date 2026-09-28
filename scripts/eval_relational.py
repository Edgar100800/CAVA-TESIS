"""EXP-011 paso 2 (CPU): ¿el VJudge relacional añade señal de trama sobre SegLoop?

Sobre los mismos candidatos (top-100 SegLoop por película):
  1) AP sin umbral para "candidato = transición de trama" (beat GT a ±60 s,
     dentro del tramo anotado) y "= corte de escena" (±1 shot). Compara
     score SegLoop vs p_new (mm) vs p_new (frames). Diferencia PAREADA por
     película con error estándar.
  2) Selección de K cortes por película (K ∈ 12, 24, 36), sin fusión de scores:
       segloop   top-K por score SegLoop
       vjudge    top-K por p_new
       veto      orden SegLoop saltando candidatos con p_new < 0.5 (voto del VJudge)
       veto_random  control: veto aleatorio con la misma tasa de veto por película
       veto_rel     veto con umbral = mediana del juez en la película (voto relativo);
                    control veto_rel_random con tasa 50 %
     con métricas de eval_hierarchy y azar del mismo K.
Pre-registro (EXPERIMENT_LOG, antes de ver resultados):
  primario    ΔAP_beat(mm − SegLoop) > 0 por más de 2 SE
  secundario  AP_beat(mm) > AP_beat(frames); veto_mm − veto_random en beat F1 a K=24
              > 2 SE pareado (no contra segloop: un veto aleatorio ya mejora al
              espaciar cortes)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_hierarchy import MN, load_film, metrics, random_metrics  # noqa: E402
from narrative_eval import average_precision  # noqa: E402

KS = (12, 24, 36)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inp", default="data/vjudge_relational")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--out", default="results/exp011_step2_relational.json")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--films-file", default=None,
                    help="evalúa solo estas películas (p. ej. la replicación pre-registrada)")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    inp, corpus = Path(args.inp), Path(args.corpus)
    films = sorted({f.name.split(".")[0] for f in inp.glob("*.mm.json")})
    if args.films_file:
        keep = set(Path(args.films_file).read_text().split())
        films = [t for t in films if t in keep]
    ap_rows, sel_rows = {}, {}
    for tt in films:
        conds = {}
        for cond in ("mm", "frames"):
            f = inp / f"{tt}.{cond}.json"
            if f.exists():
                rows = json.loads(f.read_text())
                if rows and all(r["p_new"] is not None for r in rows):
                    conds[cond] = {r["cut"]: r for r in rows}
        if "mm" not in conds or not (MN / "annotation" / f"{tt}.json").exists():
            continue
        g = load_film(tt, corpus)
        if not g or len(g["beat"]) < 2:
            continue
        st, (lo, hi) = g["shot_times"], g["beat_span"]
        cuts = sorted(conds["mm"])
        beat_t = np.asarray([st[b][0] for b in g["beat"]])
        scene = np.asarray(g["scene"])
        inside = [c for c in cuts if lo < c < hi]
        y_beat = np.asarray([np.min(np.abs(beat_t - st[c][0])) <= 60 for c in inside], int)
        y_scene = np.asarray([np.min(np.abs(scene - c)) <= 1 for c in cuts], int)
        seg = {c: conds["mm"][c]["seg_score"] for c in cuts}
        scorers = {"segloop": seg} | {f"vjudge_{k}": {c: v[c]["p_new"] for c in cuts}
                                      for k, v in conds.items()}
        r = {"n_cands": len(cuts), "beat_pos_rate": float(y_beat.mean()) if len(y_beat) else None,
             "scene_pos_rate": float(y_scene.mean())}
        for name, sc in scorers.items():
            r[f"ap_beat_{name}"] = average_precision([sc[c] for c in inside], y_beat) \
                if y_beat.sum() else None
            r[f"ap_scene_{name}"] = average_precision([sc[c] for c in cuts], y_scene)
        ap_rows[tt] = r

        sel_rows[tt] = {}
        for K in KS:
            picks = {
                "segloop": sorted(cuts, key=lambda c: -seg[c])[:K],
                "vjudge_mm": sorted(cuts, key=lambda c: -scorers["vjudge_mm"][c])[:K],
                "veto_mm": [c for c in sorted(cuts, key=lambda c: -seg[c])
                            if scorers["vjudge_mm"][c] >= 0.5][:K],
                # veto relativo: el juez vota "nueva trama" si supera SU mediana en la
                # película (corrige el sesgo ~80 % "B" sin GT ni ajuste)
                "veto_rel_mm": [c for c in sorted(cuts, key=lambda c: -seg[c])
                                if scorers["vjudge_mm"][c] >= np.median(
                                    [scorers["vjudge_mm"][x] for x in cuts])][:K],
            }
            for name, pred in picks.items():
                pred = sorted(pred)
                m = metrics(pred, g)
                rm = random_metrics(len(pred), g, rng)
                sel_rows[tt][f"K{K}_{name}"] = m | {f"rand_{k}": v for k, v in rm.items()}
            # control: veto ALEATORIO con la misma tasa que cada veto real (saltar
            # candidatos ya espacia los cortes por sí solo)
            med = float(np.median([scorers["vjudge_mm"][c] for c in cuts]))
            for tag, n_veto in (("", sum(1 for c in cuts if scorers["vjudge_mm"][c] < 0.5)),
                                ("_rel", sum(1 for c in cuts if scorers["vjudge_mm"][c] < med))):
                draws = []
                for _ in range(20):
                    vetoed = set(rng.choice(cuts, n_veto, replace=False).tolist()) if n_veto else set()
                    pred = sorted([c for c in sorted(cuts, key=lambda c: -seg[c])
                                   if c not in vetoed][:K])
                    draws.append(metrics(pred, g) | {f"rand_{k}": v for k, v in
                                                     random_metrics(len(pred), g, rng, draws=10).items()})
                sel_rows[tt][f"K{K}_veto{tag}_random"] = {
                    k: (float(np.mean([d[k] for d in draws if d[k] is not None]))
                        if any(d[k] is not None for d in draws) else None) for k in draws[0]}

    def paired(a, b):
        d = [ap_rows[t][a] - ap_rows[t][b] for t in ap_rows
             if ap_rows[t].get(a) is not None and ap_rows[t].get(b) is not None]
        return (round(float(np.mean(d)), 4), round(float(np.std(d, ddof=1) / np.sqrt(len(d))), 4),
                len(d)) if len(d) > 1 else (None, None, len(d))

    keys = sorted({k for r in ap_rows.values() for k in r if k.startswith("ap_")})
    ap_mean = {k: round(float(np.mean(v)), 4) for k in keys
               if (v := [r[k] for r in ap_rows.values() if r.get(k) is not None])}
    for lvl in ("beat", "scene"):
        ap_mean[f"rand_{lvl}"] = round(float(np.mean([r[f"{lvl}_pos_rate"] for r in ap_rows.values()
                                                      if r[f"{lvl}_pos_rate"] is not None])), 4)
    diffs = {f"{lvl}:{a}-{b}": paired(f"ap_{lvl}_{a}", f"ap_{lvl}_{b}")
             for lvl in ("beat", "scene")
             for a, b in (("vjudge_mm", "segloop"), ("vjudge_frames", "segloop"),
                          ("vjudge_mm", "vjudge_frames"))}
    sel_agg = {}
    for s in next(iter(sel_rows.values())):
        rows = [sel_rows[t][s] for t in sel_rows]
        sel_agg[s] = {}
        for m in ("scene_f1", "beat_f1", "beat_pk", "scene_prec"):
            d = [r[m] - r["rand_" + m] for r in rows if r[m] is not None]
            sel_agg[s][f"d_{m}"] = round(float(np.mean(d)), 4)
            sel_agg[s][f"d_{m}_se"] = round(float(np.std(d, ddof=1) / np.sqrt(len(d))), 4)
        sel_agg[s]["n_topics"] = round(float(np.mean([r["n_topics"] for r in rows])), 1)

    veto_paired = {}
    for K in KS:
        for m in ("beat_f1", "beat_pk", "scene_f1"):
            for real, ctrl in (("veto_mm", "veto_random"), ("veto_rel_mm", "veto_rel_random")):
                d = [sel_rows[t][f"K{K}_{real}"][m] - sel_rows[t][f"K{K}_{ctrl}"][m]
                     for t in sel_rows if sel_rows[t][f"K{K}_{real}"][m] is not None
                     and sel_rows[t][f"K{K}_{ctrl}"][m] is not None]
                veto_paired[f"K{K}:{real}:{m}"] = (round(float(np.mean(d)), 4),
                                                   round(float(np.std(d, ddof=1) / np.sqrt(len(d))), 4))
    report = {"protocol": "exp011_step2_relational_v1", "veto_vs_random_paired": veto_paired, "n_films": len(ap_rows),
              "ap_mean": ap_mean, "ap_paired_diff": diffs, "selection": sel_agg,
              "per_film_ap": ap_rows, "per_film_selection": sel_rows}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print(f"{len(ap_rows)} películas · AP media sobre candidatos: {ap_mean}")
    print("diferencias pareadas (media, SE, n):")
    for k, v in diffs.items():
        print(f"  {k}: {v}")
    print("\n| selección | tópicos | Δ escena F1 | Δ beat F1 | Δ beat Pk | Δ scene_prec |")
    print("|---|---|---|---|---|---|")
    for s, a in sel_agg.items():
        print(f"| {s} | {a['n_topics']:.0f} | {a['d_scene_f1']:+.3f}±{a['d_scene_f1_se']:.3f} "
              f"| {a['d_beat_f1']:+.3f}±{a['d_beat_f1_se']:.3f} "
              f"| {a['d_beat_pk']:+.3f}±{a['d_beat_pk_se']:.3f} "
              f"| {a['d_scene_prec']:+.3f} |")
    print("veto_mm − veto_random (pareado, media, SE):")
    for k, v in veto_paired.items():
        print(f"  {k}: {v}")
    print(f"[out] {out}")


if __name__ == "__main__":
    main()
