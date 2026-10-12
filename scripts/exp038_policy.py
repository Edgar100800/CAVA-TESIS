"""EXP-038: política de clips aprendida (bandido contextual; ver pre-registro y enmienda en EXPERIMENT_LOG).

Estado por unidad de 5 s (solo salidas del pipeline), política lineal Plackett–Luce, REINFORCE con línea base de la
media de 16 muestras, Adam lr 0.05, 300 épocas, L2 1e-3, semilla 0. Recompensa = z de importancia (EXP-031/037).

--mode loco   TVSum dejando una categoría fuera (criterios 3, 3b) → results/exp038_loco.json
--mode summe  entrena con los 50 de TVSum, prueba en SumMe (criterios 1, 1b, 2) → results/exp038_summe.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp037_highlights import rule_units  # noqa: E402
from highlight_common import (budget_units, load_run, paired, random_units_reward, reward, summe_z,  # noqa: E402
                              tvsum_categories, tvsum_z, uniform_units, unit_spans)
from topicagg.multimodal_manager import signal_boundary  # noqa: E402

SIGNALS = ("voice", "visual", "transcript", "vjudge")
FEATURES = (["pos", "topic_share", "topic_returns", "span_first"] + [f"agree_{s}" for s in SIGNALS]
            + [f"support_{s}" for s in SIGNALS] + ["vis_distinct", "vis_change", "has_asr", "needs_review", "no_topic"])
N_SAMPLES, LR, EPOCHS, L2, SEED = 16, 0.05, 300, 1e-3, 0


def features(r):
    units, vis, D = r["units"], r["visual"], r["D"]
    n = len(units)
    all_topics = r["doc"]["levels"]["default"]["topics"]
    f = np.zeros((n, len(FEATURES)), np.float32)
    for t in all_topics:
        firsts = set()
        for a, b in t["spans"]:
            idx = [i for i, (u0, u1) in enumerate(units) if a - 1e-6 <= (u0 + u1) / 2 <= b + 1e-6]
            if idx:
                firsts.add(idx[0])
        for u in t["shots"]:
            if u >= n:
                continue
            row = [t["duration_s"] / D, float(t["returns"] > 0), float(u in firsts)]
            row += [t["provenance"].get(s, {}).get("agreement") or 0.0 for s in SIGNALS]
            row += [t["provenance"].get(s, {}).get("support") or 0.0 for s in SIGNALS]
            f[u, 1:12] = row
            f[u, 15] = float(t["flags"]["needs_review"])
            f[u, 16] = float(t["flags"]["no_topic"])
    f[:, 0] = [(a + b) / 2 / D for a, b in units]
    vm = vis.mean(0)
    f[:, 12] = 1 - (vis @ vm) / (np.linalg.norm(vis, axis=1) * np.linalg.norm(vm) + 1e-9)
    s = signal_boundary(vis) if n > 1 else np.zeros(0)
    f[1:, 13] = s[:n - 1]
    f[:, 14] = [float(bool(str(a).strip())) for a in r["asr"][:n]]
    sd = f.std(0)
    return np.where(sd > 0, (f - f.mean(0)) / np.where(sd > 0, sd, 1), 0.0).astype(np.float32)


def load_set(runs_dir, zfun):
    out = []
    for run in sorted(Path(runs_dir).iterdir()):
        if not (run / "clips.jsonl").exists():
            continue
        r = load_run(run)
        z = zfun(r["vid"], r["D"])
        if z is None:
            continue
        out.append({"vid": r["vid"], "r": r, "z": z, "X": torch.tensor(features(r)), "m": min(budget_units(r["D"]), len(r["units"]))})
    return out


def pl_sample(scores, m, g):
    gumbel = -torch.log(-torch.log(torch.rand(scores.shape, generator=g).clamp_min(1e-12)))
    order = torch.argsort(scores.detach() + gumbel, descending=True)[:m]
    lp, mask = 0.0, torch.ones_like(scores, dtype=torch.bool)
    for i in order:
        lp = lp + scores[i] - torch.logsumexp(scores[mask], 0)
        mask = mask.clone()
        mask[i] = False
    return order.tolist(), lp


def train(videos):
    torch.manual_seed(SEED)
    g = torch.Generator().manual_seed(SEED)
    w = torch.zeros(len(FEATURES), requires_grad=True)
    opt = torch.optim.Adam([w], lr=LR)
    for ep in range(EPOCHS):
        opt.zero_grad()
        loss, mean_r = 0.0, []
        for v in videos:
            s = v["X"] @ w
            samples = [pl_sample(s, v["m"], g) for _ in range(N_SAMPLES)]
            R = torch.tensor([reward(v["z"], unit_spans(v["r"]["units"], idx)) for idx, _ in samples])
            R = torch.nan_to_num(R)
            adv = R - R.mean()
            loss = loss - sum(a * lp for a, (_, lp) in zip(adv, samples)) / N_SAMPLES
            mean_r.append(float(R.mean()))
        loss = loss / len(videos) + L2 * (w ** 2).sum()
        loss.backward()
        opt.step()
        if ep % 50 == 0 or ep == EPOCHS - 1:
            print(f"  época {ep}: R muestreada {np.mean(mean_r):.4f}", flush=True)
    return w.detach()


def center_units(n, m):
    a = max(0, min(n - m, n // 2 - m // 2))
    return list(range(a, a + m))


def gaps_cv(idx, n):
    p = np.sort(np.asarray(idx))
    gaps = np.diff(np.concatenate([[-0.5], p, [n - 0.5]]))
    return float(gaps.std() / gaps.mean())


def evaluate(videos, w, rng):
    rows = {}
    for v in videos:
        r, z, m = v["r"], v["z"], v["m"]
        n = len(r["units"])
        pick = torch.argsort(v["X"] @ w, descending=True)[:m].tolist()
        h3 = [u for win in rule_units(r, "H3") for u in win]
        uni = uniform_units(n, m)
        rows[v["vid"]] = {
            "policy": reward(z, unit_spans(r["units"], pick)),
            "uniform": reward(z, unit_spans(r["units"], uni)),
            "center": reward(z, unit_spans(r["units"], center_units(n, m))),
            "random": random_units_reward(z, r["units"], m, rng),
            "H3": reward(z, unit_spans(r["units"], h3)),
            "H0": reward(z, r["h0"]),
            "gap_cv_policy": gaps_cv(pick, n), "gap_cv_uniform": gaps_cv(uni, n), "m": m, "n_units": n}
    return rows


def crit(rows, a, b):
    out = paired([x[a] - x[b] for x in rows.values()])
    out["pass"] = bool(out["z"] is not None and out["z"] > 2)
    return out


def summary(rows):
    keys = ("policy", "uniform", "center", "random", "H3", "H0", "gap_cv_policy", "gap_cv_uniform")
    return {k: round(float(np.nanmean([x[k] for x in rows.values()])), 4) for k in keys}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["loco", "summe"], required=True)
    mode = ap.parse_args().mode
    rng = np.random.default_rng(0)
    tv = load_set("data/cava_runs_v1", tvsum_z())
    if mode == "loco":
        cat = tvsum_categories()
        rows, weights = {}, {}
        for c in sorted({cat[v["vid"]] for v in tv}):
            print(f"[loco] categoría fuera: {c}", flush=True)
            w = train([v for v in tv if cat[v["vid"]] != c])
            weights[c] = dict(zip(FEATURES, map(float, w)))
            rows.update(evaluate([v for v in tv if cat[v["vid"]] == c], w, rng))
        rep = {"n": len(rows), "c3_vs_uniform": crit(rows, "policy", "uniform"), "c3b_vs_center": crit(rows, "policy", "center"),
               "secondary_vs_H3": crit(rows, "policy", "H3"), "means": summary(rows), "weights_by_fold": weights, "per_video": rows}
        Path("results/exp038_loco.json").write_text(json.dumps(rep, indent=1))
    else:
        w = train(tv)
        sm = load_set("data/cava_runs_v1_summe", summe_z())
        rows = evaluate(sm, w, rng)
        rep = {"n": len(rows), "c1_vs_uniform": crit(rows, "policy", "uniform"), "c1b_vs_center": crit(rows, "policy", "center"),
               "c2_vs_H3": crit(rows, "policy", "H3"), "secondary_vs_random": crit(rows, "policy", "random"),
               "means": summary(rows), "weights": dict(zip(FEATURES, map(float, w))), "per_video": rows}
        Path("results/exp038_summe.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("per_video", "weights_by_fold")}, indent=1))


if __name__ == "__main__":
    main()
