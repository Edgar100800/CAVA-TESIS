"""EXP-039: detectores de "¿hay una segunda voz?" con habla filtrada (ver pre-registro en EXPERIMENT_LOG).

Candidatos D0 spread, D1 q15, D2 minor, D3 bic12, D4 nme sobre las x-vectors de las unidades S&W / I&W.
Desarrollo: docmix dev + domix dev (S&W e I&W agrupados) → candidato y umbral. Confirmación: docmix conf (1–2),
domix conf (3), AMI 40 (4), frente a W con spread τ 0.976. Secundaria: BBC 01–11.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp029_single_speaker import features  # noqa: E402
from exp034_eval import gates, paired  # noqa: E402
from exp034_items import G, all_items  # noqa: E402
from topicagg.speaker import SINGLE_TAU, single_speaker  # noqa: E402

CANDS = ["S&W", "I&W"]
DETS = ["spread", "q15", "minor", "bic12", "nme"]
GRIDS = {"spread": [round(0.960 + 0.001 * k, 3) for k in range(31)],
         "q15": [round(0.500 + 0.005 * k, 3) for k in range(99)],
         "minor": [round(0.500 + 0.005 * k, 3) for k in range(99)]}
MINOR_MASS = 0.10
MAX_FALSE = 0.02


def nme_k(xn, kmax=8):
    """Número de hablantes por eigengap normalizado (Park et al. 2019): p vecinos binarizados, laplaciano."""
    a = xn @ xn.T
    n = len(a)
    kmax = min(kmax, n - 1)
    best = None
    for p in range(2, max(2, n // 4) + 1):
        b = np.zeros_like(a)
        top = np.argsort(-a, axis=1)[:, :p]
        np.put_along_axis(b, top, 1.0, axis=1)
        b = (b + b.T) / 2
        lam = np.linalg.eigvalsh(np.diag(b.sum(1)) - b)
        gaps = np.diff(lam[:kmax + 1])
        g = gaps.max() / (lam.max() + 1e-10)
        r = p / (g + 1e-10)
        if best is None or r < best[0]:
            best = (r, int(np.argmax(gaps)) + 1)
    return best[1]


def stats(x, gate):
    ok = gate & (np.linalg.norm(x, axis=1) > 0)
    if ok.sum() < 10:
        return None
    xn = x[ok] / np.linalg.norm(x[ok], axis=1, keepdims=True)
    mu = xn.mean(0)
    c = xn @ (mu / np.linalg.norm(mu))
    core = xn[c >= np.median(c)].mean(0)
    s = xn @ (core / np.linalg.norm(core))
    return {"spread": float(np.median(c)), "q15": float(np.quantile(c, 0.15)), "minor_s": s,
            "bic12": features(x, gate)["bic12"], "nme": nme_k(xn)}


def single(st, det, t):
    if st is None:
        return False
    if det in ("spread", "q15"):
        return st[det] >= t
    if det == "minor":
        return float(np.mean(st["minor_s"] < t)) <= MINOR_MASS
    if det == "bic12":
        return st[det] < t
    return st["nme"] == 1


def items(sub, split):
    out = []
    for it in all_items([sub]):
        if it["split"] != split:
            continue
        g, _ = gates(it)
        x = np.load(G / "cache" / sub / f"{it['id']}.xall.npy").astype(np.float32)
        m = json.loads(Path(it["wav"]).with_suffix(".json").read_text()) if sub in ("docmix", "domix") else {}
        out.append({"id": it["id"], "dom": sub, "k_true": m.get("k_true"), "cond": m.get("cond"),
                    "top": m.get("top_share_src"), "g": g, "x": x,
                    "st": {k: stats(x, g[k]) for k in CANDS}})
    return out


def rates(rows, det, t, keys=CANDS):
    one = [single(r["st"][k], det, t) for r in rows for k in keys if r["k_true"] == 1]
    many = [single(r["st"][k], det, t) for r in rows for k in keys if r["k_true"] >= 2]
    return float(np.mean(one)) if one else None, float(np.mean(many)) if many else None


def pick(dev, det):
    grid = GRIDS.get(det)
    if det == "bic12":
        v = [r["st"][k]["bic12"] for r in dev for k in CANDS if r["st"][k] is not None]
        grid = list(np.linspace(min(v), max(v), 200))
    if grid is None:  # nme: sin umbral
        o, f = rates(dev, det, None)
        return None, {"single_k1": o, "false_k2": f}
    tab = {t: dict(zip(("single_k1", "false_k2"), rates(dev, det, t))) for t in grid}
    strict = (lambda t: -t) if det == "bic12" else (lambda t: t)  # más estricto = menos "un hablante"
    ok = [t for t in grid if tab[t]["false_k2"] <= MAX_FALSE]
    if ok:
        t = max(ok, key=lambda t: (round(tab[t]["single_k1"] - tab[t]["false_k2"], 9), strict(t)))
    else:
        t = max(grid, key=lambda t: (-tab[t]["false_k2"], tab[t]["single_k1"], strict(t)))
    return float(t), tab[t]


def main():
    dev = items("docmix", "dev") + items("domix", "dev")
    rep = {"dev": {"n": {"k1": sum(r["k_true"] == 1 for r in dev), "k2": sum(r["k_true"] >= 2 for r in dev)}}}
    sel = {}
    for det in DETS:
        t, m = pick(dev, det)
        sel[det] = {"tau": t, **m, "objective": m["single_k1"] - m["false_k2"], "meets": m["false_k2"] <= MAX_FALSE}
        print(f"[dev] {det}: τ {t} {m}", flush=True)
    rep["dev"]["candidates"] = sel
    ok = [d for d in DETS if sel[d]["meets"]]
    chosen = max(ok, key=lambda d: (round(sel[d]["objective"], 9), -DETS.index(d))) if ok else None
    rep["chosen"] = chosen
    print(f"[dev] elegido: {chosen}", flush=True)

    conf = items("docmix", "conf")
    domix = items("domix", "conf")
    ami = items("ami", "conf")
    bbc = items("bbc", "sec")
    w = {r["id"]: single_speaker(r["x"], r["g"]["W"], SINGLE_TAU) for r in conf + domix + bbc}
    w_false = float(np.mean([w[r["id"]] for r in conf if r["k_true"] >= 2]))
    w_false_do = float(np.mean([w[r["id"]] for r in domix]))
    rep["W"] = {"single_k1": float(np.mean([w[r["id"]] for r in conf if r["k_true"] == 1])),
                "false_docmix": w_false, "false_domix": w_false_do, "bbc_single": int(sum(w[r["id"]] for r in bbc))}

    def block(det, t):
        out = {}
        for k in CANDS:
            s = {r["id"]: single(r["st"][k], det, t) for r in conf + domix + ami + bbc}
            d = [int(s[r["id"]]) - int(w[r["id"]]) for r in conf if r["k_true"] == 1]
            c1 = paired(d)
            f2 = [r for r in conf if r["k_true"] >= 2 and s[r["id"]]]
            f3 = [r for r in domix if s[r["id"]]]
            a4 = [r["id"] for r in ami if s[r["id"]]]
            o = {"c1_single_minus_W": c1, "c1_pass": bool(c1["z"] is not None and c1["z"] > 2),
                 "single_k1": float(np.mean([s[r["id"]] for r in conf if r["k_true"] == 1])),
                 "single_k1_by_cond": {c: float(np.mean([s[r["id"]] for r in conf if r["k_true"] == 1 and r["cond"] == c]))
                                       for c in ("music", "noise")},
                 "c2_false": len(f2) / sum(r["k_true"] >= 2 for r in conf), "c2_false_ids": [r["id"] for r in f2],
                 "c3_false": len(f3) / len(domix), "c3_false_ids": [(r["id"], r["top"]) for r in f3],
                 "c4_ami_single": a4,
                 "bbc_single": [r["id"] for r in bbc if s[r["id"]]]}
            o["c2_pass"] = o["c2_false"] <= w_false + 0.05
            o["c3_pass"] = o["c3_false"] <= w_false_do + 0.05
            o["c4_pass"] = len(a4) <= 1
            o["pass_039"] = bool(o["c1_pass"] and o["c2_pass"] and o["c3_pass"] and o["c4_pass"])
            out[k] = o
        return out

    rep["n_conf"] = {"docmix_k1": sum(r["k_true"] == 1 for r in conf), "docmix_k2": sum(r["k_true"] >= 2 for r in conf),
                     "domix": len(domix), "ami": len(ami), "bbc": len(bbc)}
    rep["secondary_all"] = {d: block(d, sel[d]["tau"]) for d in DETS}
    if chosen:
        rep["confirm"] = rep["secondary_all"][chosen]
    Path("results/exp039.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("secondary_all",)}, indent=1))
    for d in DETS:
        for k in CANDS:
            b = rep["secondary_all"][d][k]
            print(f"{d:7s} {k:4s} K1 {b['single_k1']:.3f} (z {b['c1_single_minus_W']['z']}) "
                  f"falsos docmix {b['c2_false']:.3f} domix {b['c3_false']:.3f} ami {len(b['c4_ami_single'])} "
                  f"bbc {len(b['bbc_single'])}/11 pass {b['pass_039']}")


if __name__ == "__main__":
    main()
