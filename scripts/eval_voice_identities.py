"""EXP-022: identidades por voz frente a hablantes reales (AMI).

Por reunión: clustering aglomerativo (enlace promedio, coseno) de las unidades
con evidencia, K ∈ {2..8} por silueta máxima (sin GT). Se hace con `voice` y,
como comparación, con `visual`. Contra el hablante dominante GT:
  ARI          acuerdo identidades ↔ hablantes
  especificidad  por identidad: lift del hablante principal vs grupo al azar
                 del mismo tamaño (1 sorteo por identidad, semilla fija)
"""
import argparse
import json
import random
from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from scipy.stats import binomtest
from sklearn.metrics import adjusted_rand_score, silhouette_score

D = Path("data/ami")


def identities(x, method="average", fixed_k=None):
    ok = np.where(np.linalg.norm(x, axis=1) > 0)[0]
    xn = x[ok] / np.linalg.norm(x[ok], axis=1, keepdims=True)
    Z = linkage(xn, method="ward") if method == "ward" else linkage(pdist(xn, "cosine"), method="average")
    best, lab_best = -2, None
    for k in ([fixed_k] if fixed_k else range(2, 9)):
        lab = fcluster(Z, t=k, criterion="maxclust")
        if len(set(lab)) < 2:
            continue
        s = silhouette_score(xn, lab, metric="cosine")
        if s > best or fixed_k:
            best, lab_best = s, lab
    out = np.full(len(x), -1)
    out[ok] = lab_best
    return out


def dominant(units, speech):
    dom = []
    for u0, u1 in units:
        ov = {}
        for s, a, b in speech:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0) + o
        tot = sum(ov.values())
        sp = max(ov, key=ov.get) if ov else None
        dom.append(sp if ov and ov[sp] >= 0.6 * tot and tot > 3 else None)
    return dom


def lift_of(group, dom, base):
    cnt = {}
    for i in group:
        cnt[dom[i]] = cnt.get(dom[i], 0) + 1
    return max((cnt[s] / len(group)) / base[s] for s in cnt)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meetings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--linkage", choices=["average", "ward"], default="average", help="EXP-022b: ward")
    ap.add_argument("--known-k", action="store_true",
                    help="EXP-022c (descriptivo): K = nº real de hablantes de la reunión (prior)")
    args = ap.parse_args()
    rng = random.Random(22)
    rows, wins, total = {}, 0, 0
    for m in Path(args.meetings).read_text().split():
        fj, fz = D / "signals" / f"{m}.json", D / "signals" / f"{m}.npz"
        if not (fj.exists() and fz.exists()):
            continue
        units = json.loads(fj.read_text())["unit_times"]
        z = np.load(fz)
        dom = dominant(units, json.loads((D / "gt" / f"{m}.json").read_text())["speech"])
        r = {}
        k_true = len({d for d in dom if d}) if args.known_k else None
        for name in ("voice", "visual"):
            lab = identities(np.asarray(z[name], np.float32), args.linkage, k_true)
            idx = [i for i in range(len(units)) if dom[i] and lab[i] >= 0]
            r[f"ari_{name}"] = float(adjusted_rand_score([dom[i] for i in idx], [lab[i] for i in idx]))
            r[f"k_{name}"] = int(len(set(lab[lab >= 0].tolist())))
            if name == "voice":
                base = {}
                for i in idx:
                    base[dom[i]] = base.get(dom[i], 0) + 1 / len(idx)
                for c in set(lab[idx].tolist()):
                    g = [i for i in idx if lab[i] == c]
                    if len(g) < 3:
                        continue
                    rand = rng.sample(idx, len(g))
                    total += 1
                    wins += lift_of(g, dom, base) > lift_of(rand, dom, base)
        r["n_speakers"] = len({d for d in dom if d})
        rows[m] = r
    d = np.array([r["ari_voice"] - r["ari_visual"] for r in rows.values()])
    v = np.array([r["ari_voice"] for r in rows.values()])
    rep = {"n": len(rows),
           "ari_voice_mean": round(float(v.mean()), 4), "ari_visual_mean": round(float(np.mean([r["ari_visual"] for r in rows.values()])), 4),
           "1_voice_minus_visual": {"mean": round(float(d.mean()), 4), "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4)},
           "2_voice_ari_gt0": {"mean": round(float(v.mean()), 4), "se": round(float(v.std(ddof=1) / np.sqrt(len(v))), 4)},
           "3_specificity": {"wins": wins, "total": total, "rate": round(wins / max(total, 1), 4),
                             "binom_p": round(float(binomtest(wins, total, 0.5, alternative="greater").pvalue), 6) if total else None},
           "k_voice_median": float(np.median([r["k_voice"] for r in rows.values()])),
           "per_meeting": rows}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_meeting"}, indent=1))


if __name__ == "__main__":
    main()
