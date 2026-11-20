"""EXP-043-DIA: evaluación pre-registrada (VoxConverse test).

C = producto CAVA sobre las cachés de EXP-028 (xvec WavLM por unidad, gate = VAD oráculo):
    single_speaker (EXP-029) → todo 1; si no, identities(ward, BIC).
P = pyannote community-1: etiqueta por unidad = hablante con más tiempo en la unidad.
Protocolo de unidades, hablante dominante y K_true idéntico a scripts/eval_speaker_embed.py.
Criterios: (1) ARI P−C > 2 SE; (2) kerr C−P > 2 SE; (3) K_true = 1: [K_eff=1] P−C > 2 SE.
Secundarias: DER/JER (collar 0,25 s, con solapamientos) de P y de C (unidad ∩ VAD oráculo).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, "/data/tesis-cava/CAVA_minimo")
from topicagg.speaker import single_speaker  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--gt", default="/data/tesis-cava/data_vox/voxconverse-master/test")
ap.add_argument("--xvec", default="/data/tesis-cava/data_vox/xvec/test")
ap.add_argument("--pyannote", default="/data/tesis-cava/data_vox/out_test")
ap.add_argument("--exp028", default="/data/tesis-cava/exp036/dia/ref/exp028_voxconverse_test.json")
ap.add_argument("--out", default="/data/tesis-cava/exp036/dia/exp043_voxconverse_test.json")
ap.add_argument("--no-der", action="store_true")
args = ap.parse_args()


def voice_ids(x, gate=None, k1=False):  # copia literal de scripts/eval_bbc.py (EXP-028)
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


def k_eff(vid, speech, thr=0.05):  # copia literal de scripts/eval_bbc.py
    v = vid[speech & (vid >= 0)]
    if not len(v):
        return 0
    _, c = np.unique(v, return_counts=True)
    return int((c / len(v) >= thr).sum())


def rttm(path):
    segs = []
    for line in Path(path).read_text().splitlines():
        p = line.split()
        if p and p[0] == "SPEAKER":
            segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
    return segs


def unit_gt(units, segs):  # copia literal de eval_speaker_embed.py
    dom, gate = [], []
    for u0, u1 in units:
        ov = {}
        for a, b, s in segs:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0.0) + o
        tot = sum(ov.values())
        sp = max(ov, key=ov.get) if ov else None
        dom.append(sp if sp and ov[sp] >= 0.6 * tot and ov[sp] >= 1.5 else None)
        gate.append(min(tot, u1 - u0) >= 0.5 * (u1 - u0))
    return dom, np.array(gate)


def unit_major(units, segs):
    lab = []
    for u0, u1 in units:
        ov = {}
        for a, b, s in segs:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0.0) + o
        lab.append(max(ov, key=ov.get) if ov else None)
    return lab


def ari(dom, vid):
    idx = [i for i in range(len(dom)) if dom[i] and vid[i] >= 0]
    return float(adjusted_rand_score([dom[i] for i in idx], vid[idx])) if len(idx) > 5 else None


if not args.no_der:
    from pyannote.core import Annotation, Segment
    from pyannote.metrics.diarization import DiarizationErrorRate, JaccardErrorRate

    def ann(segs):
        a = Annotation()
        for s0, s1, spk in segs:
            a[Segment(s0, s1)] = str(spk)
        return a
    der_p, der_c = DiarizationErrorRate(collar=0.25), DiarizationErrorRate(collar=0.25)
    jer_p, jer_c = JaccardErrorRate(collar=0.25), JaccardErrorRate(collar=0.25)

rows = {}
for z in sorted(Path(args.xvec).glob("*.npz")):
    uri = z.stem
    pr = Path(args.pyannote) / f"{uri}.rttm"
    if not pr.exists():
        continue
    d = np.load(z, allow_pickle=True)
    x, units = d["x"].astype(np.float32), d["units"].astype(float).tolist()
    gt = rttm(Path(args.gt) / f"{uri}.rttm")
    dom, gate = unit_gt(units, gt)
    assert (gate == d["gate"]).all(), uri
    lab = [s for s in dom if s]
    _, cnt = np.unique(lab, return_counts=True) if lab else ([], [])
    k_true = int((np.asarray(cnt) / max(1, len(lab)) >= 0.05).sum())

    c28 = voice_ids(x, gate)
    cvid = np.full(len(units), -1)
    if single_speaker(x, gate):
        cvid[gate & (np.linalg.norm(x, axis=1) > 0)] = 1
    else:
        cvid = voice_ids(x, gate)
    psegs = rttm(pr)
    pm = unit_major(units, psegs)
    names = {s: i + 1 for i, s in enumerate(sorted({s for s in pm if s}))}
    pvid = np.array([names[s] if (s and gate[i]) else -1 for i, s in enumerate(pm)])

    r = {"k_true": k_true, "n_units": len(units),
         "ari_c28": ari(dom, c28), "ari_C": ari(dom, cvid), "ari_P": ari(dom, pvid),
         "kerr_c28": abs(k_eff(c28, gate) - k_true), "kerr_C": abs(k_eff(cvid, gate) - k_true),
         "kerr_P": abs(k_eff(pvid, gate) - k_true),
         "k1_C": int(k_eff(cvid, gate) == 1), "k1_P": int(k_eff(pvid, gate) == 1),
         "n_spk_P_raw": len({s for _, _, s in psegs})}
    if not args.no_der:
        ref = ann(gt)
        vad = ann([(a, b, "s") for a, b, _ in gt]).get_timeline().support()
        csegs = []
        for (u0, u1), v in zip(units, cvid):
            if v >= 0:
                for s in vad.crop(Segment(u0, u1)):
                    csegs.append((s.start, s.end, int(v)))
        r["der_P"] = der_p(ref, ann(psegs))
        r["der_C"] = der_c(ref, ann(csegs))
        r["jer_P"] = jer_p(ref, ann(psegs))
        r["jer_C"] = jer_c(ref, ann(csegs))
    rows[uri] = r


def paired(a, b, sub=None):
    vals = [v for v in rows.values() if v[a] is not None and v[b] is not None and (sub is None or sub(v))]
    dd = np.array([v[a] - v[b] for v in vals], float)
    if len(dd) < 2:
        return {"n": len(dd)}
    se = dd.std(ddof=1) / np.sqrt(len(dd))
    return {"mean": round(float(dd.mean()), 4), "se": round(float(se), 4), "n": len(dd),
            "z": round(float(dd.mean() / se), 2) if se > 0 else None, "pass": bool(dd.mean() > 2 * se)}


def mean(k, sub=None):
    v = [r[k] for r in rows.values() if r[k] is not None and (sub is None or sub(r))]
    return round(float(np.mean(v)), 4) if v else None


k1 = lambda r: r["k_true"] == 1  # noqa: E731
ref28 = json.load(open(args.exp028))["per_file"]
same = [u for u in rows if u in ref28 and ref28[u]["ari_xvec"] is not None and rows[u]["ari_c28"] is not None]
rep = {"n_files": len(rows), "n_k1": sum(k1(r) for r in rows.values()),
       "sanity_exp028_ari_xvec": {"exp028": round(float(np.mean([ref28[u]["ari_xvec"] for u in same])), 4),
                                  "recomputed": round(float(np.mean([rows[u]["ari_c28"] for u in same])), 4),
                                  "n": len(same)},
       "means": {k: mean(k) for k in ("ari_C", "ari_P", "kerr_C", "kerr_P", "k_true")},
       "means_k1": {"k1_C": mean("k1_C", k1), "k1_P": mean("k1_P", k1)},
       "criteria": {"1_ari_P_minus_C": paired("ari_P", "ari_C"),
                    "2_kerr_C_minus_P": paired("kerr_C", "kerr_P"),
                    "3_k1_P_minus_C": paired("k1_P", "k1_C", k1)}}
if not args.no_der:
    rep["secondary"] = {"DER_P": round(abs(der_p), 4), "DER_C": round(abs(der_c), 4),
                        "JER_P": round(abs(jer_p), 4), "JER_C": round(abs(jer_c), 4)}
rep["per_file"] = rows
Path(args.out).write_text(json.dumps(rep, indent=1, default=float))
print(json.dumps({k: v for k, v in rep.items() if k != "per_file"}, indent=1, default=float))
