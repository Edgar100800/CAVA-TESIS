"""EXP-020 (AMI): (a) identidad del hablante por voz; (b) mapa de tópicos CAVA.

Unidades de 10 s. GT (scripts/ami_gt.py), solo para evaluar:
  hablante dominante de una unidad = el que tiene ≥ 60 % de su habla (y > 3 s)
  tópico de una unidad = etiqueta del tópico GT que contiene su punto medio
(a) pares a ≥ 6 unidades con hablante dominante: AUC mismo vs distinto
    hablante para voice, visual, transcript (bge del ASR), vjudge (bge resumen).
(b) pares a ≥ 18 unidades con tópico: MCC de "mismo tópico predicho" vs misma
    etiqueta GT. Sistemas: cava_voice (voice+visual+transcript+vjudge),
    cava_novoice, fused, contiguous, señales solas; G-coherencia de cava_voice.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_topic_map import coherence_margin, l2, mcc  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402

D = Path("data/ami")
KW = dict(percentile=80, tolerance_bins=1, link_quorum=2)


def auc(scores, y):
    s, y = np.asarray(scores), np.asarray(y, bool)
    pos, neg = s[y], s[~y]
    if not len(pos) or not len(neg):
        return None
    order = np.argsort(np.concatenate([pos, neg]))
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    return float((ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def paired(rows, a, b):
    d = np.array([r[a] - r[b] for r in rows.values() if r.get(a) is not None and r.get(b) is not None])
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": int(len(d)),
            "z": round(float(d.mean() / se), 2) if se > 0 else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meetings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--percentile", type=float, default=80, help="EXP-021c: perfil de contenido")
    ap.add_argument("--return-percentile", type=float, default=90)
    ap.add_argument("--compare-film-profile", action="store_true",
                    help="EXP-021c: añade cava_voice con el perfil film (p80/r90)")
    args = ap.parse_args()
    KW["percentile"] = args.percentile
    bge = BgeEmbedder()
    ra, rb = {}, {}
    for m in Path(args.meetings).read_text().split():
        fj, fz, fv = D / "signals" / f"{m}.json", D / "signals" / f"{m}.npz", D / "vjudge" / f"{m}.summaries.json"
        if not (fj.exists() and fz.exists() and fv.exists()):
            continue
        meta, z, sums = json.loads(fj.read_text()), np.load(fz), json.loads(fv.read_text())
        gt = json.loads((D / "gt" / f"{m}.json").read_text())
        units = meta["unit_times"]
        n = min(len(units), len(z["voice"]), len(z["visual"]), len(sums))
        units = units[:n]
        asr = bge([t or "" for t in meta["asr_text"][:n]])
        vj = bge([s["summary"] for s in sums[:n]])
        sig = {"voice": z["voice"][:n], "visual": z["visual"][:n], "transcript": asr, "vjudge": vj}
        dom, top = [], []
        for u0, u1 in units:
            ov = {}
            for s, a, b in gt["speech"]:
                o = max(0.0, min(u1, b) - max(u0, a))
                if o > 0:
                    ov[s] = ov.get(s, 0) + o
            tot = sum(ov.values())
            sp = max(ov, key=ov.get) if ov else None
            dom.append(sp if ov and ov[sp] >= 0.6 * tot and tot > 3 else None)
            mid = (u0 + u1) / 2
            top.append(next((t["label"] for t in gt["topics"] if t["t0"] <= mid <= t["t1"]), None))
        # (a) identidad del hablante
        I, J = np.triu_indices(n, 6)
        keep = [(i, j) for i, j in zip(I, J) if dom[i] and dom[j]]
        r = {"n_units": n}
        if keep:
            y = [dom[i] == dom[j] for i, j in keep]
            for k, x in sig.items():
                xn = l2(np.asarray(x, np.float32))
                ok = [(i, j) for i, j in keep if np.linalg.norm(x[i]) > 0 and np.linalg.norm(x[j]) > 0]
                yy = [dom[i] == dom[j] for i, j in ok]
                r[f"auc_{k}"] = auc([float(xn[i] @ xn[j]) for i, j in ok], yy) if ok else None
            r["n_pairs_a"], r["same_rate_a"] = len(keep), float(np.mean(y))
        ra[m] = r
        # (b) mapa de tópicos
        I, J = np.triu_indices(n, 18)
        keep = [(i, j) for i, j in zip(I, J) if top[i] and top[j]]
        y = np.array([top[i] == top[j] for i, j in keep])
        if len(keep) < 20 or y.all() or (~y).all():
            continue
        AB = KW | {"link_mode": "average", "abstain": True}
        fused = np.concatenate([l2(np.asarray(v, np.float32)) for v in sig.values()], 1)
        R = args.return_percentile
        plans = {"cava_voice": manage(sig, return_percentile=R, **AB),
                 "cava_novoice": manage({k: v for k, v in sig.items() if k != "voice"}, return_percentile=R, **AB),
                 "fused": manage({"fused": fused}, return_percentile=R, **(KW | {"link_quorum": 1})),
                 "contiguous": manage(sig, **KW)}
        for k in sig:
            plans[k] = manage({k: sig[k]}, return_percentile=R, **(KW | {"link_quorum": 1}))
        if args.compare_film_profile:
            plans["cava_film"] = manage(sig, return_percentile=90, **(AB | {"percentile": 80}))
        rr = {"n_pairs_b": len(keep), "pos_rate_b": float(y.mean())}
        for name, p in plans.items():
            pred = np.array([p.labels[i] == p.labels[j] for i, j in keep])
            rr[f"mcc_{name}"] = mcc(pred, y)
            rr[f"n_topics_{name}"] = len(set(p.labels.tolist()))
        for k in sig:
            rr[f"coh_cava_voice_{k}"] = coherence_margin(plans["cava_voice"].labels, np.asarray(sig[k], np.float32))
        rb[m] = rr
        print(f"[ami] {m}: (a) AUC voice {r.get('auc_voice')} visual {r.get('auc_visual')} | "
              f"(b) MCC cava_voice {rr['mcc_cava_voice']:+.3f} fused {rr['mcc_fused']:+.3f}", flush=True)
    crit_a = {f"auc_{k}_minus_visual": paired(ra, f"auc_{k}", "auc_visual") for k in ("voice", "transcript", "vjudge")}
    d = np.array([r["auc_voice"] - 0.5 for r in ra.values() if r.get("auc_voice") is not None])
    crit_a["auc_voice_minus_0.5"] = {"mean": round(float(d.mean()), 4),
                                     "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4), "n": int(len(d))}
    crit_b = {f"cava_voice_vs_{b}": paired(rb, "mcc_cava_voice", f"mcc_{b}")
              for b in ("fused", "contiguous", "cava_novoice", "voice", "visual", "transcript", "vjudge", "cava_film")
              if any(f"mcc_{b}" in r for r in rb.values())}
    coh = {k: {"mean": round(float(np.mean(v)), 4), "frac_positive": round(float(np.mean(np.array(v) > 0)), 3)}
           for k in ("voice", "visual", "transcript", "vjudge")
           if (v := [r[f"coh_cava_voice_{k}"] for r in rb.values() if r.get(f"coh_cava_voice_{k}") is not None])}
    means_a = {k: round(float(np.mean([r[k] for r in ra.values() if r.get(k) is not None])), 4)
               for k in ("auc_voice", "auc_visual", "auc_transcript", "auc_vjudge")}
    means_b = {k: round(float(np.mean([r[k] for r in rb.values()])), 4)
               for k in rb[next(iter(rb))] if k.startswith("mcc_")} if rb else {}
    rep = {"protocol": "exp020_ami_v1", "meetings": args.meetings, "n_a": len(ra), "n_b": len(rb),
           "a_means": means_a, "a_criteria": crit_a, "b_means": means_b, "b_criteria": crit_b,
           "b_coherence": coh, "per_meeting_a": ra, "per_meeting_b": rb}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if not k.startswith("per_")}, indent=1))


if __name__ == "__main__":
    main()
