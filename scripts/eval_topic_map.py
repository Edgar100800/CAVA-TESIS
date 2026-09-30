"""EXP-017: mapa de tópicos CAVA (retornos + quorum) vs fusión / contiguo / señal sola.

Por película, a nivel de shot:
  señales   visual (SigLIP) · dialogue (bge del subtítulo) · vjudge (bge del
            resumen de la unidad que contiene el shot)
  GT        cast por shot; pares anotados con |i−j| ≥ --min-gap: positivo si
            Jaccard ≥ 0.5, negativo si 0 (resto excluido)
  métrica   MCC de "mismo tópico" vs GT (un tópico global = 0)
  G-coherencia  por señal: coseno medio intra-tópico − inter-tópico (todos los pares)
Sistemas: cava, contiguous, fused (A2Summ-X), visual/dialogue/vjudge solos,
sensibilidad cava_r80/cava_r95 y, si hay scores SegLoop, cava+segloop.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from narrative_eval import BgeEmbedder  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")
KW = dict(percentile=80, link_quorum=2, tolerance_bins=1)


def l2(x):
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-8)


def mcc(pred, y):
    tp = float(np.sum(pred & y)); tn = float(np.sum(~pred & ~y))
    fp = float(np.sum(pred & ~y)); fn = float(np.sum(~pred & y))
    den = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return (tp * tn - fp * fn) / den if den > 0 else 0.0


def coherence_margin(labels, x):
    xn = l2(x)
    ok = np.linalg.norm(x, axis=1) > 0
    lab, xn = labels[ok], xn[ok]
    if len(lab) < 3:
        return None
    S = xn @ xn.T
    same = lab[:, None] == lab[None, :]
    iu = np.triu_indices(len(lab), 1)
    same, S = same[iu], S[iu]
    if same.all() or (~same).all():
        return None
    return float(S[same].mean() - S[~same].mean())


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--dialogue-dir", required=True)
    ap.add_argument("--summary-dir", required=True)
    ap.add_argument("--segloop-dir", default=None, help="npz con `segloop` [n-1] (solo val)")
    ap.add_argument("--min-gap", type=int, default=80)
    ap.add_argument("--out", required=True)
    ap.add_argument("--average", action="store_true", help="EXP-017b: añade link_mode=average")
    ap.add_argument("--abstain", action="store_true", help="EXP-018: añade cava_abst (average + abstain)")
    args = ap.parse_args()
    bge = BgeEmbedder()
    rows = {}
    for tt in Path(args.films_file).read_text().split():
        a = json.loads((MN / "annotation" / f"{tt}.json").read_text())
        cast = [c for c in (a.get("cast") or []) if c.get("pid") and c["pid"] != "others"]
        if not cast:
            continue
        vis = np.asarray(np.load(Path(args.corpus) / f"{tt}.npz")["visual"], np.float32)
        dia = np.asarray(np.load(Path(args.dialogue_dir) / f"{tt}.npz")["dialogue"], np.float32)
        sums = json.loads((Path(args.summary_dir) / f"{tt}.summaries.json").read_text())
        n = min(len(vis), len(dia), sums[-1]["hi"])
        e = bge([u["summary"] for u in sums])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for u, v in zip(sums, e):
            vj[u["lo"]:min(u["hi"], n)] = v
        sig = {"visual": vis[:n], "dialogue": dia[:n], "vjudge": vj}

        by_shot = {}
        for c in cast:
            if c["shot_idx"] < n:
                by_shot.setdefault(c["shot_idx"], set()).add(c["pid"])
        shots = np.array(sorted(by_shot))
        I, J = np.triu_indices(len(shots), 1)
        far = (shots[J] - shots[I]) >= args.min_gap
        I, J = I[far], J[far]
        jac = np.array([len(by_shot[shots[i]] & by_shot[shots[j]]) /
                        len(by_shot[shots[i]] | by_shot[shots[j]]) for i, j in zip(I, J)])
        keep = (jac >= 0.5) | (jac == 0)
        I, J, y = I[keep], J[keep], jac[keep] >= 0.5
        if len(y) < 50 or y.all() or (~y).all():
            continue

        fused = np.concatenate([l2(sig["visual"]), l2(sig["dialogue"]), l2(sig["vjudge"])], axis=1)
        plans = {
            "cava": manage(sig, return_percentile=90, **KW),
            "cava_r80": manage(sig, return_percentile=80, **KW),
            "cava_r95": manage(sig, return_percentile=95, **KW),
            "contiguous": manage(sig, **KW),
            "fused": manage({"fused": fused}, return_percentile=90,
                            **(KW | {"link_quorum": 1})),
        }
        if args.average:
            AV = KW | {"link_mode": "average"}
            plans["cava_avg"] = manage(sig, return_percentile=90, **AV)
            plans["cava_avg_r80"] = manage(sig, return_percentile=80, **AV)
            plans["cava_avg_r95"] = manage(sig, return_percentile=95, **AV)
        if args.abstain:
            AB = KW | {"link_mode": "average", "abstain": True}
            plans["cava_abst"] = manage(sig, return_percentile=90, **AB)
            plans["cava_abst_r95"] = manage(sig, return_percentile=95, **AB)
        for k in ("visual", "dialogue", "vjudge"):
            plans[k] = manage({k: sig[k]}, return_percentile=90, **(KW | {"link_quorum": 1}))
        if args.segloop_dir and (Path(args.segloop_dir) / f"{tt}.npz").exists():
            seg = np.asarray(np.load(Path(args.segloop_dir) / f"{tt}.npz")["segloop"][:n - 1],
                             np.float32)
            plans["cava+segloop"] = manage(sig, boundary_signals={"segloop": seg},
                                           return_percentile=90, **KW)
            if args.average:
                plans["cava_avg+segloop"] = manage(sig, boundary_signals={"segloop": seg},
                                                   return_percentile=90, **AV)
        r = {"n_shots": n, "n_pairs": int(len(y)), "pos_rate": float(y.mean())}
        for name, plan in plans.items():
            lab = plan.labels
            pred = lab[shots[I]] == lab[shots[J]]
            r[f"mcc_{name}"] = mcc(pred, y)
            r[f"n_topics_{name}"] = int(len(set(lab.tolist())))
            r[f"link_rate_{name}"] = float(pred.mean())
            r[f"prec_{name}"] = float((pred & y).sum() / pred.sum()) if pred.sum() else float(y.mean())
            r[f"rec_{name}"] = float((pred & y).sum() / y.sum())
        for name in [x for x in ("cava", "cava_avg", "cava_abst", "fused", "contiguous") if x in plans]:
            for k in ("visual", "dialogue", "vjudge"):
                r[f"coh_{name}_{k}"] = coherence_margin(plans[name].labels, sig[k])
        rows[tt] = r
        print(f"[topicmap] {tt}: pares {len(y)} | MCC cava {r['mcc_cava']:+.3f} fused "
              f"{r['mcc_fused']:+.3f} contig {r['mcc_contiguous']:+.3f}"
              + (f" avg {r['mcc_cava_avg']:+.3f} ({r['n_topics_cava_avg']} tópicos)"
                 if "mcc_cava_avg" in r else ""), flush=True)

    def paired(a, b):
        d = np.array([r[a] - r[b] for r in rows.values() if a in r and b in r])
        return {"mean": round(float(d.mean()), 4), "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4),
                "n": len(d), "z": round(float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))), 2)}

    systems = sorted({k[4:] for r in rows.values() for k in r if k.startswith("mcc_")})
    summary = {s: {m: round(float(np.mean([r[f"{m}_{s}"] for r in rows.values()
                                            if f"{m}_{s}" in r])), 4)
                   for m in ("mcc", "n_topics", "link_rate")} for s in systems}
    coh = {f"{name}_{k}": {"mean": round(float(np.mean(v)), 4), "min_film": round(float(np.min(v)), 4),
                           "frac_positive": round(float(np.mean(np.array(v) > 0)), 3)}
           for name in ("cava", "cava_avg", "cava_abst", "fused", "contiguous")
           for k in ("visual", "dialogue", "vjudge")
           if (v := [r[f"coh_{name}_{k}"] for r in rows.values()
                     if r.get(f"coh_{name}_{k}") is not None])}
    crit = {"cava_vs_fused": paired("mcc_cava", "mcc_fused"),
            "cava_vs_contiguous": paired("mcc_cava", "mcc_contiguous"),
            "cava_vs_visual": paired("mcc_cava", "mcc_visual"),
            "cava_vs_dialogue": paired("mcc_cava", "mcc_dialogue"),
            "cava_vs_vjudge": paired("mcc_cava", "mcc_vjudge")}
    if any("mcc_cava_avg" in r for r in rows.values()):
        for b in ("fused", "contiguous", "visual", "dialogue", "vjudge", "cava"):
            crit[f"cava_avg_vs_{b}"] = paired("mcc_cava_avg", f"mcc_{b}")
    if any("mcc_cava_abst" in r for r in rows.values()):
        for b in ("fused", "contiguous", "visual", "dialogue", "vjudge", "cava_avg"):
            crit[f"cava_abst_vs_{b}"] = paired("mcc_cava_abst", f"mcc_{b}")
        crit["prec_minus_base_cava_abst"] = paired("prec_cava_abst", "pos_rate")
        crit["prec_minus_base_fused"] = paired("prec_fused", "pos_rate")
        crit["prec_minus_base_visual"] = paired("prec_visual", "pos_rate")
    if any("mcc_cava_avg+segloop" in r for r in rows.values()):
        crit["cava_avg+segloop_vs_cava_avg"] = paired("mcc_cava_avg+segloop", "mcc_cava_avg")
    if any("mcc_cava+segloop" in r for r in rows.values()):
        crit["cava+segloop_vs_cava"] = paired("mcc_cava+segloop", "mcc_cava")
    rep = {"protocol": "exp017_topic_map_v1", "films_file": args.films_file,
           "min_gap": args.min_gap, "n_films": len(rows), "systems": summary,
           "criteria": crit, "coherence_margin": coh, "per_film": rows}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(f"\n{len(rows)} películas")
    print("| sistema | MCC | tópicos | tasa de enlace |\n|---|---|---|---|")
    for s, v in summary.items():
        print(f"| {s} | {v['mcc']:+.4f} | {v['n_topics']:.0f} | {v['link_rate']:.3f} |")
    for k, v in crit.items():
        print(f"  {k}: {v}")
    print("  G-coherencia (media, mín película, fracción > 0):")
    for k, v in coh.items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
