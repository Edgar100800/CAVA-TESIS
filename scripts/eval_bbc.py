"""EXP-025 / EXP-026: CAVA en documentales (BBC Planet Earth, 11 episodios, 5 anotadores de escenas).

EXP-025 (estructura): las unidades del pipeline (perfil film, 5 s) se mapean a
la escena GT de cada anotador (unidad → shot GT por el tiempo medio → escena).
  M_local  MCC de "misma escena" sobre pares de unidades a distancia 1..60
           (≤ 5 min), promedio sobre los 5 anotadores.
  F1_b     F1 de fronteras (cambio de etiqueta entre unidades contiguas),
           tolerancia ±1 unidad, promedio sobre anotadores (secundaria).
  techo    cada anotador como predictor frente a los otros 4 (mismo M_local).
Sistemas: cava p{70,80,90,95} (r90, average, abstain, quorum 2), cava_fine
(quorum = todas las señales), contiguous v2.1 (p80), fused, señales solas.

EXP-026 (voz con un solo narrador): identidades de voz ward + K por BIC,
  base   K en 2..8 sobre todas las unidades con voz (EXP-022d)
  k1     K en 1..8 (K = 1 permitido)
  gate   solo unidades con habla ASR (≥ 50 % de la unidad cubierta por
         segmentos ASR); el resto queda en −1
  k1gate ambas
  métrica: K_eff = nº de identidades con ≥ 5 % de las unidades con habla ASR
  (GT: 1 narrador); err = |K_eff − 1|.
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

GT = Path("/home/edgar.chambilla/Tesis/SegLoop/data/bbc/gt")
NAMES = {1: "01_From_Pole_to_Pole", 2: "02_Mountains", 3: "03_Ice Worlds", 4: "04_Great Plains",
         5: "05_Jungles", 6: "06_Seasonal_Forests", 7: "07_Fresh_Water", 8: "08_Ocean_Deep",
         9: "09_Shallow_Seas", 10: "10_Caves", 11: "11_Deserts"}
FPS = 25.0
WIN = 60
KW = dict(min_gap=2, tolerance_bins=1, link_quorum=2)


def scenes_per_unit(ep, units):
    shots = [tuple(map(int, l.split())) for l in (GT / "shots" / f"{NAMES[ep]}.txt").read_text().split("\n") if l.strip()]
    starts = np.array([s for s, _ in shots])
    out = []
    for a in range(5):
        sc = sorted({int(x) for x in (GT / "scenes" / f"annotator_{a}" / f"{NAMES[ep]}.txt").read_text()
                     .replace("\n", ",").split(",") if x.strip()})
        lab = []
        for u0, u1 in units:
            shot = int(np.searchsorted(starts, (u0 + u1) / 2 * FPS, side="right") - 1)
            lab.append(int(np.searchsorted(sc, max(shot, 0), side="right") - 1))
        out.append(np.array(lab))
    return out


def local_pairs(n):
    I, J = [], []
    for d in range(1, WIN + 1):
        I.append(np.arange(n - d))
        J.append(np.arange(d, n))
    return np.concatenate(I), np.concatenate(J)


def m_local(lab, gts, I, J):
    return float(np.mean([mcc(lab[I] == lab[J], g[I] == g[J]) for g in gts]))


def f1_b(lab, gts, tol=1):
    p = np.where(lab[1:] != lab[:-1])[0]
    fs = []
    for g in gts:
        t = np.where(g[1:] != g[:-1])[0]
        if not len(p) or not len(t):
            fs.append(0.0)
            continue
        prec = np.mean([np.abs(t - x).min() <= tol for x in p])
        rec = np.mean([np.abs(p - x).min() <= tol for x in t])
        fs.append(0.0 if prec + rec == 0 else 2 * prec * rec / (prec + rec))
    return float(np.mean(fs))


def speech_gate(units, segs, frac=0.5):
    g = np.zeros(len(units), bool)
    for k, (u0, u1) in enumerate(units):
        cov = sum(max(0.0, min(u1, s[1]) - max(u0, s[0])) for s in segs)
        g[k] = cov >= frac * (u1 - u0)
    return g


def voice_ids(x, gate=None, k1=False):
    from scipy.cluster.hierarchy import fcluster, linkage
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    ok = np.linalg.norm(x, axis=1) > 0
    if gate is not None:
        ok &= gate
    idx = np.where(ok)[0]
    out = np.full(len(x), -1)
    if len(idx) < 10:
        return out
    xn = x[idx] / np.linalg.norm(x[idx], axis=1, keepdims=True)
    xp = PCA(n_components=min(16, len(xn) - 1), random_state=0).fit_transform(xn)
    bic = {k: GaussianMixture(k, covariance_type="diag", random_state=0).fit(xp).bic(xp)
           for k in range(1 if k1 else 2, 9)}
    k = min(bic, key=bic.get)
    out[idx] = fcluster(linkage(xn, method="ward"), t=k, criterion="maxclust") if k > 1 else 1
    return out


def k_eff(vid, speech, thr=0.05):
    v = vid[speech & (vid >= 0)]
    if not len(v):
        return 0
    _, c = np.unique(v, return_counts=True)
    return int((c / len(v) >= thr).sum())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episodes", nargs="+", type=int, required=True)
    ap.add_argument("--runs", default="data/cava_runs")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    bge = BgeEmbedder()
    rows = {}
    for ep in args.episodes:
        w = Path(args.runs) / f"bbc_{ep:02d}" / "work"
        if not (w / "signals.npz").exists() or not (w / "summaries.json").exists():
            print(f"[bbc] {ep:02d}: sin señales", flush=True)
            continue
        st, z = json.loads((w / "state.json").read_text()), np.load(w / "signals.npz")
        sums = json.loads((w / "summaries.json").read_text())
        units = st["units"]
        n = min(len(units), len(z["voice"]), len(z["visual"]))
        units = units[:n]
        e = bge([s["summary"] for s in sums])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for s, v in zip(sums, e):
            vj[s["lo"]:min(s["hi"], n)] = v
        sig = {"voice": np.asarray(z["voice"][:n], np.float32), "visual": np.asarray(z["visual"][:n], np.float32),
               "transcript": bge(st["asr"][:n]), "vjudge": vj}
        gts = scenes_per_unit(ep, units)
        I, J = local_pairs(n)
        r = {"n_units": n, "gt_scenes": [int(len(set(g.tolist()))) for g in gts]}
        r["ceiling_m_local"] = float(np.mean([m_local(gts[a], [g for b, g in enumerate(gts) if b != a], I, J)
                                              for a in range(5)]))
        r["ceiling_f1_b"] = float(np.mean([f1_b(gts[a], [g for b, g in enumerate(gts) if b != a])
                                           for a in range(5)]))
        AB = KW | {"link_mode": "average", "abstain": True}
        fused = np.concatenate([l2(v) for v in sig.values()], 1)
        plans = {f"cava_p{p}": manage(sig, percentile=p, return_percentile=90, **AB) for p in (70, 80, 90, 95)}
        plans["cava_fine"] = manage(sig, percentile=80, return_percentile=90, **(AB | {"link_quorum": len(sig)}))
        plans["contiguous"] = manage(sig, percentile=80, **KW)
        plans["fused"] = manage({"fused": fused}, percentile=80, return_percentile=90, **(KW | {"link_quorum": 1}))
        for k in sig:
            plans[k] = manage({k: sig[k]}, percentile=80, return_percentile=90, **(KW | {"link_quorum": 1}))
        for name, p in plans.items():
            lab = np.asarray(p.labels)
            r[f"m_local_{name}"] = m_local(lab, gts, I, J)
            r[f"f1b_{name}"] = f1_b(lab, gts)
            r[f"n_topics_{name}"] = len(set(lab.tolist()))
            r[f"n_runs_{name}"] = int(1 + (lab[1:] != lab[:-1]).sum())
        for k in sig:
            r[f"coh_cava_p80_{k}"] = coherence_margin(np.asarray(plans["cava_p80"].labels), sig[k])
        speech = speech_gate(units, st["asr_segments"])
        r["speech_frac"] = float(speech.mean())
        for name, kw in (("base", {}), ("k1", {"k1": True}), ("gate", {"gate": speech}),
                         ("k1gate", {"k1": True, "gate": speech})):
            vid = voice_ids(sig["voice"], **kw)
            r[f"keff_{name}"] = k_eff(vid, speech)
            r[f"err_{name}"] = abs(r[f"keff_{name}"] - 1)
        rows[f"bbc_{ep:02d}"] = r
        print(f"[bbc] {ep:02d}: GT escenas {r['gt_scenes']} | techo {r['ceiling_m_local']:.3f} | "
              + " ".join(f"{k}={r['m_local_' + k]:.3f}/{r['n_runs_' + k]}" for k in
                         ("cava_p70", "cava_p80", "cava_p90", "cava_p95", "cava_fine", "contiguous", "fused"))
              + f" | habla {r['speech_frac']:.2f} K_eff " + " ".join(f"{k}={r['keff_' + k]}" for k in
                                                                    ("base", "k1", "gate", "k1gate")), flush=True)

    def paired(a, b):
        d = np.array([r[a] - r[b] for r in rows.values()])
        if len(d) < 2:
            return None
        se = d.std(ddof=1) / np.sqrt(len(d))
        return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d),
                "z": round(float(d.mean() / se), 2) if se > 0 else None}
    keys = [k for k in next(iter(rows.values())) if k.startswith(("m_local_", "f1b_", "keff_", "err_", "ceiling_",
                                                                     "n_runs_", "speech"))] if rows else []
    rep = {"episodes": sorted(rows), "means": {k: round(float(np.mean([r[k] for r in rows.values()])), 4) for k in keys},
           "criteria_025": {f"{a}_vs_{b}": paired(f"m_local_{a}", f"m_local_{b}") for a, b in
                            (("cava_p80", "contiguous"), ("cava_p80", "fused"), ("cava_p90", "cava_p80"),
                             ("cava_p95", "cava_p80"), ("cava_p70", "cava_p80"))},
           "criteria_026": {f"{b}_minus_{a}": paired(f"err_{b}", f"err_{a}") for a, b in
                            (("k1gate", "base"), ("k1", "base"), ("gate", "base"))},
           "per_episode": rows}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_episode"}, indent=1))


if __name__ == "__main__":
    main()
