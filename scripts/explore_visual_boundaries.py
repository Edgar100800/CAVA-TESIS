"""EXP-027 (desarrollo, BBC 01–11): ¿se pueden tomar las fronteras de la señal visual sin perder el agrupamiento CAVA?
Candidatos: snap_r = mover cada frontera de cava p90 a la frontera visual más cercana a ≤ r unidades
(las unidades entre ambas pasan al tópico del otro lado); wvis_x = peso de voto visual x en manage()."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import f1_b, local_pairs, m_local, scenes_per_unit  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402

AB = dict(min_gap=2, tolerance_bins=1, link_quorum=2, link_mode="average", abstain=True, return_percentile=90)


def snap(lab, vis_lab, r):
    lab = lab.copy()
    vb = np.where(vis_lab[1:] != vis_lab[:-1])[0]
    if not len(vb):
        return lab
    for b in np.where(lab[1:] != lab[:-1])[0]:
        d = vb - b
        k = vb[np.argmin(np.abs(d))]
        if 0 < abs(k - b) <= r:
            if k > b:   # la frontera se mueve a la derecha: unidades b+1..k toman la etiqueta de la izquierda
                lab[b + 1:k + 1] = lab[b]
            else:       # a la izquierda: unidades k+1..b toman la etiqueta de la derecha
                lab[k + 1:b + 1] = lab[b + 1]
    return lab


def random_like(vis_lab, seed):
    """Control: mismas nº de fronteras que la visual, en posiciones al azar."""
    nb = int((vis_lab[1:] != vis_lab[:-1]).sum())
    rng = np.random.default_rng(seed)
    cuts = np.zeros(len(vis_lab), int)
    cuts[np.sort(rng.choice(np.arange(1, len(vis_lab)), nb, replace=False))] = 1
    return np.cumsum(cuts)


def smooth(lab, r):
    """Control: rachas más cortas que r unidades pasan a la etiqueta de la racha anterior."""
    lab = lab.copy()
    starts = np.r_[0, np.where(lab[1:] != lab[:-1])[0] + 1, len(lab)]
    for a, b in zip(starts[:-1], starts[1:]):
        if b - a < r and a > 0:
            lab[a:b] = lab[a - 1]
    return lab


def load(ep, bge, runs="data/cava_runs"):
    w = Path(runs) / f"bbc_{ep:02d}" / "work"
    st, z = json.loads((w / "state.json").read_text()), np.load(w / "signals.npz")
    sums = json.loads((w / "summaries.json").read_text())
    n = min(len(st["units"]), len(z["voice"]), len(z["visual"]))
    e = bge([s["summary"] for s in sums])
    vj = np.zeros((n, e.shape[1]), np.float32)
    for s, v in zip(sums, e):
        vj[s["lo"]:min(s["hi"], n)] = v
    return st["units"][:n], {"voice": np.asarray(z["voice"][:n], np.float32),
                             "visual": np.asarray(z["visual"][:n], np.float32),
                             "transcript": bge(st["asr"][:n]), "vjudge": vj}


if __name__ == "__main__":
    bge = BgeEmbedder()
    rows = {}
    for ep in range(1, 12):
        units, sig = load(ep, bge)
        gts = scenes_per_unit(ep, units)
        I, J = local_pairs(len(units))
        base = np.asarray(manage(sig, percentile=90, **AB).labels)
        vis = np.asarray(manage({"visual": sig["visual"]}, percentile=80, **(AB | {"link_quorum": 1})).labels)
        cand = {"cava_p90": base, "visual_p80": vis}
        for r in (2, 4, 6, 8):
            cand[f"snap_{r}"] = snap(base, vis, r)
            cand[f"rand_{r}"] = np.mean([0], dtype=float)  # marcador; se calcula abajo
            cand[f"smooth_{r}"] = smooth(base, r)
        rows[ep] = {}
        for k, v in cand.items():
            if k.startswith("rand_"):
                r = int(k.split("_")[1])
                sc = [(m_local(x, gts, I, J), f1_b(x, gts)) for x in
                      (snap(base, random_like(vis, s), r) for s in range(5))]
                rows[ep][k] = tuple(np.mean(sc, 0))
            else:
                rows[ep][k] = (m_local(v, gts, I, J), f1_b(v, gts))
        print(ep, " ".join(f"{k}={a:.3f}/{b:.3f}" for k, (a, b) in rows[ep].items()), flush=True)
    for k in rows[1]:
        a = np.array([rows[e][k] for e in rows])
        d = a - np.array([rows[e]["cava_p90"] for e in rows])
        print(f"{k:11s} M {a[:, 0].mean():.3f} F1 {a[:, 1].mean():.3f} | ΔM {d[:, 0].mean():+.3f}±{d[:, 0].std(ddof=1)/np.sqrt(len(d)):.3f}"
              f" ΔF1 {d[:, 1].mean():+.3f}±{d[:, 1].std(ddof=1)/np.sqrt(len(d)):.3f}")
