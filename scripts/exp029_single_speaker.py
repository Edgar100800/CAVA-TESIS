"""EXP-029: detector de "un solo hablante" antes de ward + BIC (ver pre-registro en EXPERIMENT_LOG).

--mode dev   elige candidato y τ en VoxConverse dev (+ AMI dev como restricción: 0 reuniones de un hablante)
--mode conf  aplica la elección congelada a VoxConverse test, AMI fresh3 y BBC 01–11
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score, silhouette_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_bbc import k_eff, voice_ids  # noqa: E402

V = Path("data/voxconverse/xvec")
D = Path("data/ami")
DETECTORS = ("spread", "bic12", "sil2")


def unit_norm(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)


def features(x, gate):
    ok = gate & (np.linalg.norm(x, axis=1) > 0)
    xn = unit_norm(x[ok])
    if len(xn) < 10:
        return None
    from scipy.cluster.hierarchy import fcluster, linkage
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    mu = xn.mean(0)
    spread = float(np.median(xn @ (mu / np.linalg.norm(mu))))
    xp = PCA(n_components=min(16, len(xn) - 1), random_state=0).fit_transform(xn)
    b1, b2 = (GaussianMixture(k, covariance_type="diag", random_state=0).fit(xp).bic(xp) for k in (1, 2))
    lab = fcluster(linkage(xn, method="ward"), t=2, criterion="maxclust")
    sil = float(silhouette_score(xn, lab, metric="cosine")) if len(set(lab)) > 1 else 0.0
    return {"spread": spread, "bic12": float(b1 - b2) / len(xn), "sil2": sil}


def is_single(f, det, tau):
    if f is None:
        return False
    return f[det] >= tau if det == "spread" else f[det] < tau


def ids(x, gate, single):
    if single:
        out = np.full(len(x), -1)
        out[gate & (np.linalg.norm(x, axis=1) > 0)] = 1
        return out
    return voice_ids(x, gate=gate)


def k_true_of(dom):
    lab = [d for d in dom if d]
    if not lab:
        return 0
    _, c = np.unique(lab, return_counts=True)
    return int((c / len(lab) >= 0.05).sum())


def load_vox(split):
    for f in sorted((V / split).glob("*.npz")):
        z = np.load(f)
        yield f.stem, z["x"].astype(np.float32), z["gate"], [str(d) for d in z["dom"]]


def load_ami(listfile):
    for m in Path(listfile).read_text().split():
        f = D / "signals" / f"{m}.xvec.npz"
        if f.exists():
            z = np.load(f)
            yield m, z["x"].astype(np.float32), z["gate"], [str(d) for d in z["dom"]]


def dev():
    vox = [(k_true_of(dom), features(x, g)) for _, x, g, dom in load_vox("dev")]
    vox = [(k == 1, f) for k, f in vox if f is not None and k >= 1]
    ami = [features(x, g) for _, x, g, _ in load_ami(D / "meetings_40.txt")]
    ami = [f for f in ami if f is not None]
    res = {}
    for det in DETECTORS:
        vals = sorted({f[det] for _, f in vox} | {f[det] for f in ami})
        best = None
        for tau in vals + [vals[-1] + 1e-6]:
            if any(is_single(f, det, tau) for f in ami):
                continue
            pred = np.array([is_single(f, det, tau) for _, f in vox])
            y = np.array([s for s, _ in vox])
            bacc = 0.5 * (pred[y].mean() + (~pred[~y]).mean())
            if best is None or bacc > best[0]:
                best = (float(bacc), float(tau), float(pred[y].mean()), float((~pred[~y]).mean()))
        res[det] = {"bacc": best[0], "tau": best[1], "tpr_single": best[2], "tnr_multi": best[3]} if best else None
        print(det, res[det], flush=True)
    choice = max((d for d in res if res[d]), key=lambda d: res[d]["bacc"])
    out = {"candidates": res, "choice": choice, "tau": res[choice]["tau"],
           "n_vox_dev": len(vox), "n_single_dev": int(sum(s for s, _ in vox)), "n_ami_dev": len(ami)}
    Path("results/exp029_dev.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def conf():
    sel = json.loads(Path("results/exp029_dev.json").read_text())
    det, tau = sel["choice"], sel["tau"]
    rows = {}
    for fid, x, g, dom in load_vox("test"):
        kt = k_true_of(dom)
        f = features(x, g)
        s = is_single(f, det, tau)
        r = {"k_true": kt, "single_pred": bool(s)}
        for name, single in (("without", False), ("with", s)):
            vid = ids(x, g, single)
            r[f"kerr_{name}"] = abs(k_eff(vid, g) - kt)
            idx = [i for i in range(len(x)) if dom[i] and vid[i] >= 0]
            r[f"ari_{name}"] = float(adjusted_rand_score([dom[i] for i in idx], vid[idx])) if len(idx) > 5 else None
        rows[fid] = r
    d = np.array([r["kerr_without"] - r["kerr_with"] for r in rows.values()])
    multi = [r for r in rows.values() if r["k_true"] >= 2 and r["ari_with"] is not None and r["ari_without"] is not None]
    da = np.array([r["ari_with"] - r["ari_without"] for r in multi])
    y = np.array([r["k_true"] == 1 for r in rows.values()])
    p = np.array([r["single_pred"] for r in rows.values()])
    ami = {m: bool(is_single(features(x, g), det, tau)) for m, x, g, _ in load_ami(D / "meetings_fresh3.txt")}
    bbc = {}
    for ep in range(1, 12):
        w = Path("data/cava_runs_doc") / f"bbc_{ep:02d}" / "work"
        x = np.load(w / "speaker_xvec.npy")
        g = np.linalg.norm(x, axis=1) > 0
        bbc[f"bbc_{ep:02d}"] = bool(is_single(features(x, g), det, tau))
    rep = {"detector": det, "tau": tau,
           "c1_kerr_without_minus_with": {"mean": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d))),
                                          "n": len(d), "z": float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d))))},
           "c2_ari_multi_with_minus_without": {"mean": float(da.mean()), "n": len(da), "non_inferior": bool(da.mean() > -0.02)},
           "c3_ami_fresh3_single": int(sum(ami.values())), "n_ami": len(ami),
           "secondary": {"bacc_test": float(0.5 * (p[y].mean() + (~p[~y]).mean())), "n_single_test": int(y.sum()),
                         "bbc_single": int(sum(bbc.values())), "bbc": bbc,
                         "kerr_single_files": {"without": float(np.mean([r["kerr_without"] for r in rows.values() if r["k_true"] == 1])),
                                               "with": float(np.mean([r["kerr_with"] for r in rows.values() if r["k_true"] == 1]))}},
           "per_file": rows}
    Path("results/exp029_conf.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_file"}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["dev", "conf"], required=True)
    dev() if ap.parse_args().mode == "dev" else conf()
