"""EXP-021 (desarrollo): ¿un criterio interno, sin GT, elige una granularidad cercana
a la mejor? Explora un grid de (percentil de corte, percentil de retorno) en
reuniones AMI ya usadas y películas val, y para cada config registra:
  MCC vs GT (pares lejanos)  -- solo para analizar, nunca para elegir
  puntuaciones internas candidatas (sin GT):
    coh      media sobre señales del margen intra − inter (G-coherencia)
    coh_n    coh penalizado por fragmentación: coh × (1 − tópicos / unidades)
    sil      silueta media del etiquetado sobre la unión de señales (por señal, promediada)
Salida: results/exp021_explore_<dominio>.json
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

GRID = [(p, r) for p in (80, 90, 95, 97, 98.5) for r in (80, 90, 95)]


def silhouette(labels, x):
    """Silueta coseno vectorizada: distancia media a cada clúster vía S · one-hot."""
    xn = l2(np.asarray(x, np.float32))
    ok = np.linalg.norm(x, axis=1) > 0
    lab, xn = labels[ok], xn[ok]
    cl, inv = np.unique(lab, return_inverse=True)
    if len(cl) < 2 or len(lab) < 5:
        return None
    D = 1.0 - xn @ xn.T
    H = np.zeros((len(lab), len(cl)), np.float32)
    H[np.arange(len(lab)), inv] = 1.0
    cnt = H.sum(0)
    M = D @ H
    own = cnt[inv] - 1
    a = M[np.arange(len(lab)), inv] / np.maximum(own, 1)
    M_other = M / cnt[None, :]
    M_other[np.arange(len(lab)), inv] = np.inf
    b = M_other.min(1)
    sil = (b - a) / np.maximum(np.maximum(a, b), 1e-9)
    sil = sil[own > 0]
    return float(sil.mean()) if len(sil) else None


def evaluate(sig, pairs, y):
    rows = []
    n = len(next(iter(sig.values())))
    for p, r in GRID:
        plan = manage(sig, percentile=p, return_percentile=r, link_quorum=2, tolerance_bins=1,
                      link_mode="average", abstain=True)
        lab = plan.labels
        pred = np.array([lab[i] == lab[j] for i, j in pairs])
        cohs = [c for k in sig if (c := coherence_margin(lab, np.asarray(sig[k], np.float32))) is not None]
        sils = [s for k in sig if (s := silhouette(lab, sig[k])) is not None]
        nt = len(set(lab.tolist()))
        coh = float(np.mean(cohs)) if cohs else None
        rows.append({"p": p, "r": r, "mcc": mcc(pred, y), "n_topics": nt,
                     "coh": coh, "coh_n": coh * (1 - nt / n) if coh is not None else None,
                     "sil": float(np.mean(sils)) if sils else None})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", choices=["ami", "movies"], required=True)
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    bge = BgeEmbedder()
    out = {}
    for m in Path(args.items).read_text().split():
        if args.domain == "ami":
            D = Path("data/ami")
            meta, z = json.loads((D / "signals" / f"{m}.json").read_text()), np.load(D / "signals" / f"{m}.npz")
            sums = json.loads((D / "vjudge" / f"{m}.summaries.json").read_text())
            gt = json.loads((D / "gt" / f"{m}.json").read_text())
            units = meta["unit_times"]
            n = min(len(units), len(sums))
            sig = {"voice": z["voice"][:n], "visual": z["visual"][:n],
                   "transcript": bge([t or "" for t in meta["asr_text"][:n]]),
                   "vjudge": bge([s["summary"] for s in sums[:n]])}
            top = [next((t["label"] for t in gt["topics"] if t["t0"] <= (a + b) / 2 <= t["t1"]), None)
                   for a, b in units[:n]]
            I, J = np.triu_indices(n, 18)
            pairs = [(i, j) for i, j in zip(I, J) if top[i] and top[j]]
            y = np.array([top[i] == top[j] for i, j in pairs])
        else:
            from eval_topic_map import MN
            vis = np.asarray(np.load(f"data/movienet_topics/{m}.npz")["visual"], np.float32)
            dia = np.asarray(np.load(f"data/movienet_voters/{m}.npz")["dialogue"], np.float32)
            sums = json.loads(Path(f"data/vjudge_ledger/{m}.summaries.json").read_text())
            n = min(len(vis), len(dia), sums[-1]["hi"])
            e = bge([u["summary"] for u in sums])
            vj = np.zeros((n, e.shape[1]), np.float32)
            for u, v in zip(sums, e):
                vj[u["lo"]:min(u["hi"], n)] = v
            sig = {"visual": vis[:n], "dialogue": dia[:n], "vjudge": vj}
            cast = [c for c in (json.loads((MN / "annotation" / f"{m}.json").read_text()).get("cast") or [])
                    if c.get("pid") and c["pid"] != "others"]
            by = {}
            for c in cast:
                if c["shot_idx"] < n:
                    by.setdefault(c["shot_idx"], set()).add(c["pid"])
            sh = np.array(sorted(by))
            if len(sh) < 10:
                continue
            I, J = np.triu_indices(len(sh), 1)
            far = (sh[J] - sh[I]) >= 80
            pairs, y = [], []
            for i, j in zip(I[far], J[far]):
                jac = len(by[sh[i]] & by[sh[j]]) / len(by[sh[i]] | by[sh[j]])
                if jac >= 0.5 or jac == 0:
                    pairs.append((sh[i], sh[j]))
                    y.append(jac >= 0.5)
            y = np.array(y)
        if len(pairs) < 20 or y.all() or (~y).all():
            continue
        out[m] = evaluate(sig, pairs, y)
        best = max(out[m], key=lambda r: r["mcc"])
        print(f"[explore] {m}: best MCC {best['mcc']:+.3f} at p{best['p']} r{best['r']} ({best['n_topics']} topics)", flush=True)
    Path(args.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
