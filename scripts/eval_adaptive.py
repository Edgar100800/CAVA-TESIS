"""EXP-011 paso 1: agregador adaptativo vs percentiles fijos, a nivel escena y beat.

Votantes (cada uno decide por su cuenta, sin fusión):
  embeddings  visual (SigLIP) · transcript (TF-IDF) · dialogue (bge-base)
  fronteras   segloop (ensemble frozen, umbral frozen) · speech (|Δ fracción de
              habla|, umbral = su percentil 80)
Propuesta inicial: los cortes del 30 % superior de scores SegLoop.

Sistemas (todos con azar de mismo nº de cortes, métricas de eval_hierarchy):
  segloop_frozen         SegLoop solo a su umbral (detector de escenas supervisado)
  segloop_topk_matched   control: SegLoop solo con el mismo nº de cortes que el
                         agregador en cada película (¿la integración suma algo
                         sobre engrosar el mejor componente?)
  proposal               la propuesta inicial sin agregar
  adaptive_rho{ρ}        agregador con todos los votantes, ρ ∈ {0.8, 0.9, 1.0}
  adaptive_-{votante}    ablación leave-one-out a ρ=0.9
  fixed_p{p}_q{q}        manage() visual+transcript (baseline del paso 0)
Pre-registro: ρ=0.9 es el valor por defecto elegido antes de ver resultados.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_hierarchy import MN, load_film, load_split, metrics, random_metrics  # noqa: E402
from topicagg.adaptive_aggregator import aggregate  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402

RHOS = (0.8, 0.9, 1.0)
EMB = ("visual", "transcript", "dialogue")
BND = ("segloop", "speech")


def voters_for(g, v):
    n = g["n"]
    emb = {"visual": g["signals"]["visual"], "transcript": g["signals"]["transcript"],
           "dialogue": np.asarray(v["dialogue"][:n], np.float32)}
    speech = np.asarray(v["speech"][:n], np.float32)
    sp = np.abs(np.diff(speech))
    sp_thr = float(np.percentile(sp, 80)) if sp.any() else 1.0
    seg = np.asarray(v["segloop"][:n - 1], np.float32)
    bnd = {"segloop": (seg, float(v["seg_thr"])), "speech": (sp, max(sp_thr, 1e-6))}
    return emb, bnd, seg


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="val")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--voters", default="data/movienet_voters")
    ap.add_argument("--proposal-top", type=float, default=0.30)
    ap.add_argument("--out", default="results/exp011_adaptive.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    corpus, vdir = Path(args.corpus), Path(args.voters)
    per_film, levels_diag = {}, {}
    for tt in sorted(load_split(args.split)):
        if not ((corpus / f"{tt}.json").exists() and (vdir / f"{tt}.npz").exists()
                and (MN / "annotation" / f"{tt}.json").exists()):
            continue
        g = load_film(tt, corpus)
        if not g or len(g["beat"]) < 2:
            continue
        v = np.load(vdir / f"{tt}.npz")
        emb, bnd, seg = voters_for(g, v)
        n = g["n"]
        k = max(1, int(round(args.proposal_top * (n - 1))))
        proposal = sorted(int(i) + 1 for i in np.argsort(-seg)[:k])

        systems = {"segloop_frozen": [i + 1 for i in range(n - 1) if seg[i] > float(v["seg_thr"])],
                   "proposal": proposal}
        for rho in RHOS:
            plan = aggregate(emb, bnd, proposal, n, rho=rho)
            systems[f"adaptive_rho{rho:g}"] = plan.cuts
            if rho == 0.9:
                levels_diag[tt] = [metrics(lv, g) | {"n_cuts": len(lv)} for lv in plan.levels]
        # control: SegLoop solo, con tantos cortes como el agregador (top-K por película)
        for rho in RHOS:
            kk = len(systems[f"adaptive_rho{rho:g}"])
            systems[f"segloop_topk_matched_rho{rho:g}"] = sorted(
                int(i) + 1 for i in np.argsort(-seg)[:kk]) if kk else []
        for drop in EMB + BND:
            e = {kk: x for kk, x in emb.items() if kk != drop}
            b = {kk: x for kk, x in bnd.items() if kk != drop}
            systems[f"adaptive_-{drop}"] = aggregate(e, b, proposal, n, rho=0.9).cuts
        for p in (80, 90, 95):
            for q in (1, 2):
                plan = manage(g["signals"], n_segments=n, percentile=p, link_quorum=q,
                              tolerance_bins=1)
                systems[f"fixed_p{p}_q{q}"] = [i for i in range(1, n)
                                               if plan.labels[i] != plan.labels[i - 1]]
        per_film[tt] = {}
        for name, pred in systems.items():
            per_film[tt][name] = metrics(pred, g) | {
                f"rand_{kk}": vv for kk, vv in random_metrics(len(pred), g, rng).items()}
        per_film[tt]["_gt"] = {"n_scenes": len(g["scene"]) + 1, "n_beats": len(g["beat"]) + 1}
        a = per_film[tt]["adaptive_rho0.9"]
        print(f"[adapt] {tt}: escenas {len(g['scene']) + 1} beats {len(g['beat']) + 1} | "
              f"adaptive {a['n_topics']} tópicos, rondas {len(levels_diag[tt])}", flush=True)

    names = [k for k in next(iter(per_film.values())) if k != "_gt"]
    agg = {}
    for s in names:
        rows = [per_film[t][s] for t in per_film]
        agg[s] = {k: round(float(np.mean([r[k] for r in rows if r[k] is not None])), 4)
                  for k in rows[0]}
        for m in ("scene_f1", "beat_f1", "scene_pk", "beat_pk", "scene_prec"):
            d = [r[m] - r["rand_" + m] for r in rows if r[m] is not None]
            agg[s][f"d_{m}"] = round(float(np.mean(d)), 4)
            agg[s][f"d_{m}_se"] = round(float(np.std(d, ddof=1) / np.sqrt(len(d))), 4)
    report = {"protocol": "exp011_step1_adaptive_v1", "n_films": len(per_film),
              "proposal_top": args.proposal_top, "aggregate": agg,
              "per_film": per_film, "levels_rho0.9": levels_diag}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print(f"\n{len(per_film)} películas · Δ = sistema − azar (± error estándar)")
    print("| sistema | tópicos | Δ escena F1 | Δ escena Pk | Δ beat F1 | Δ beat Pk | scene_prec |")
    print("|---|---|---|---|---|---|---|")
    for s, a in agg.items():
        print(f"| {s} | {a['n_topics']:.0f} | {a['d_scene_f1']:+.3f}±{a['d_scene_f1_se']:.3f} "
              f"| {a['d_scene_pk']:+.3f}±{a['d_scene_pk_se']:.3f} "
              f"| {a['d_beat_f1']:+.3f}±{a['d_beat_f1_se']:.3f} "
              f"| {a['d_beat_pk']:+.3f}±{a['d_beat_pk_se']:.3f} | {a['scene_prec']:.3f} |")
    print(f"[out] {out}")


if __name__ == "__main__":
    main()
