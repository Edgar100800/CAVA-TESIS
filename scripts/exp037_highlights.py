"""EXP-037: highlights por importancia con una regla fija sobre el mapa (ver pre-registro en EXPERIMENT_LOG).

--mode dev   TVSum (data/cava_runs_v1): elige H* de H1–H3 por recompensa media → results/exp037_dev.json
--mode conf  SumMe (data/cava_runs_v1_summe): criterios 1–3 con H* congelado → results/exp037_conf.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from highlight_common import (budget_units, load_run, paired, random_spans, reward, summe_z, tvsum_z,  # noqa: E402
                              uniform_spans, unit_spans)

RULES = ("H1", "H2", "H3")


def _cos(a, b):
    return (a @ b) / (np.linalg.norm(a, axis=-1) * np.linalg.norm(b) + 1e-9)


def longest_span_units(units, topic):
    a, b = max(topic["spans"], key=lambda s: s[1] - s[0])
    return [i for i, (u0, u1) in enumerate(units) if a - 1e-6 <= (u0 + u1) / 2 <= b + 1e-6]


def allocate(m, topics, caps):
    """Resto mayor proporcional a la duración, con tope por tópico; lo que sobra pasa al siguiente en el orden del resto."""
    d = np.array([t["duration_s"] for t in topics], float)
    q = m * d / d.sum()
    a = np.minimum(np.floor(q).astype(int), caps)
    order = sorted(range(len(topics)), key=lambda i: (-(q[i] - np.floor(q[i])), topics[i]["spans"][0][0]))
    while a.sum() < m and (a < caps).any():
        for i in order:
            if a.sum() >= m:
                break
            if a[i] < caps[i]:
                a[i] += 1
    return a


def rule_units(r, rule):
    units, vis, topics = r["units"], r["visual"], r["topics"]
    m = budget_units(r["D"])
    spans = [longest_span_units(units, t) for t in topics]
    alloc = allocate(m, topics, np.array([len(s) for s in spans]))
    vmean = vis.mean(0)
    chosen = []
    for t, s, k in zip(topics, spans, alloc):
        if k == 0 or not s:
            continue
        if rule == "H1":
            c = s[len(s) // 2]
        elif rule == "H2":
            tm = vis[[u for u in t["shots"] if u < len(vis)]].mean(0)
            c = s[int(np.argmax(_cos(vis[s], tm)))]
        else:
            c = s[int(np.argmax(1 - _cos(vis[s], vmean)))]
        start = min(max(c - k // 2, s[0]), s[-1] - k + 1)
        chosen.append(list(range(start, start + k)))
    return chosen


def evaluate(runs_dir, zfun, rules, rng):
    rows = {}
    for run in sorted(Path(runs_dir).iterdir()):
        if not (run / "clips.jsonl").exists():
            continue
        r = load_run(run)
        z = zfun(r["vid"], r["D"])
        if z is None:
            continue
        row = {"D": r["D"], "m": budget_units(r["D"]), "H0": reward(z, r["h0"])}
        for rule in rules:
            spans = [s for w in rule_units(r, rule) for s in unit_spans(r["units"], w)]
            durs = [b - a for a, b in spans]
            row[rule] = reward(z, spans)
            row[f"{rule}_uniform"] = reward(z, uniform_spans(durs, r["D"]))
            row[f"{rule}_random"] = float(np.nanmean([reward(z, random_spans(durs, r["D"], rng)) for _ in range(1000)]))
            row[f"{rule}_seconds"] = round(sum(durs), 1)
        rows[r["vid"]] = row
        print(r["vid"], " ".join(f"{k}={row[k]:.3f}" for k in ("H0",) + tuple(rules)), flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dev", "conf"], required=True)
    mode = ap.parse_args().mode
    rng = np.random.default_rng(0)
    if mode == "dev":
        rows = evaluate("data/cava_runs_v1", tvsum_z(), RULES, rng)
        means = {k: round(float(np.mean([x[k] for x in rows.values()])), 4)
                 for k in ("H0",) + RULES + tuple(f"{q}_{b}" for q in RULES for b in ("uniform", "random"))}
        best = max(RULES, key=lambda k: means[k])
        rep = {"n": len(rows), "means": means, "H_star": best,
               "dev_vs_uniform": paired([x[best] - x[f"{best}_uniform"] for x in rows.values()]),
               "dev_vs_H0": paired([x[best] - x["H0"] for x in rows.values()]), "per_video": rows}
        Path("results/exp037_dev.json").write_text(json.dumps(rep, indent=1))
    else:
        best = json.loads(Path("results/exp037_dev.json").read_text())["H_star"]
        rows = evaluate("data/cava_runs_v1_summe", summe_z(), (best,), rng)
        rep = {"H_star": best, "n": len(rows),
               "c1_vs_uniform": paired([x[best] - x[f"{best}_uniform"] for x in rows.values()]),
               "c2_vs_H0": paired([x[best] - x["H0"] for x in rows.values()]),
               "c3_vs_random": paired([x[best] - x[f"{best}_random"] for x in rows.values()]),
               "means": {k: round(float(np.mean([x[k] for x in rows.values()])), 4)
                         for k in ("H0", best, f"{best}_uniform", f"{best}_random")}, "per_video": rows}
        for c in ("c1_vs_uniform", "c2_vs_H0", "c3_vs_random"):
            rep[c]["pass"] = bool(rep[c]["z"] is not None and rep[c]["z"] > 2)
        rep["adopt"] = rep["c1_vs_uniform"]["pass"] and rep["c2_vs_H0"]["pass"]
        Path("results/exp037_conf.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_video"}, indent=1))


if __name__ == "__main__":
    main()
