"""EXP-036: τ del detector de un hablante con habla filtrada (ver pre-registro en EXPERIMENT_LOG).

Desarrollo: docmix dev (S&W e I&W agrupados) → τ con mayor (un hablante K = 1 − falsos K ≥ 2), falsos ≤ 0.02.
Confirmación: docmix conf (criterios 1–2 frente a W con τ 0.976) y AMI 40 (criterio 3).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp034_eval import gates, paired  # noqa: E402
from exp034_items import G, all_items  # noqa: E402
from topicagg.speaker import SINGLE_TAU, single_speaker  # noqa: E402

CANDS = ["S&W", "I&W"]
GRID = [round(0.960 + 0.001 * k, 3) for k in range(31)]


def items(sub, split):
    out = []
    for it in all_items([sub]):
        if it["split"] != split:
            continue
        g, _ = gates(it)
        x = np.load(G / "cache" / sub / f"{it['id']}.xall.npy").astype(np.float32)
        m = json.loads(Path(it["wav"]).with_suffix(".json").read_text()) if sub != "ami" else {}
        out.append({"id": it["id"], "k_true": m.get("k_true"), "cond": m.get("cond"), "g": g, "x": x})
    return out


def rates(rows, key, tau):
    one = [single_speaker(r["x"], r["g"][key], tau) for r in rows if r["k_true"] == 1]
    many = [single_speaker(r["x"], r["g"][key], tau) for r in rows if r["k_true"] >= 2]
    return one, many


def main():
    dev = items("docmix", "dev")
    table = {}
    for t in GRID:
        one, many = [], []
        for k in CANDS:
            o, m = rates(dev, k, t)
            one += o
            many += m
        table[t] = {"single_k1": float(np.mean(one)), "false_k2": float(np.mean(many))}
    ok = [t for t in GRID if table[t]["false_k2"] <= 0.02]
    tau = max(ok, key=lambda t: (round(table[t]["single_k1"] - table[t]["false_k2"], 9), t))
    rep = {"dev": {"n": len(dev), "grid": table, "tau": tau,
                   "at_old_tau": {k: dict(zip(("single_k1", "false_k2"), map(lambda v: float(np.mean(v)), rates(dev, k, SINGLE_TAU))))
                                  for k in CANDS}}}
    print(f"[dev] τ elegido {tau}: {table[tau]}", flush=True)

    conf = items("docmix", "conf")
    ami = items("ami", "conf")
    w_one = {r["id"]: single_speaker(r["x"], r["g"]["W"], SINGLE_TAU) for r in conf}
    w_false = float(np.mean([w_one[r["id"]] for r in conf if r["k_true"] >= 2]))
    for k in CANDS:
        d = [int(single_speaker(r["x"], r["g"][k], tau)) - int(w_one[r["id"]]) for r in conf if r["k_true"] == 1]
        c1 = paired(d)
        fs = float(np.mean([single_speaker(r["x"], r["g"][k], tau) for r in conf if r["k_true"] >= 2]))
        false_ids = [r["id"] for r in conf if r["k_true"] >= 2 and single_speaker(r["x"], r["g"][k], tau)]
        ami_single = [r["id"] for r in ami if single_speaker(r["x"], r["g"][k], tau)]
        rep[k] = {"c1_single_minus_W": c1, "c1_pass": bool(c1["z"] is not None and c1["z"] > 2),
                  "single_k1": float(np.mean([single_speaker(r["x"], r["g"][k], tau) for r in conf if r["k_true"] == 1])),
                  "single_k1_W": float(np.mean([w_one[r["id"]] for r in conf if r["k_true"] == 1])),
                  "c2_false_single": fs, "c2_false_single_W": w_false, "c2_false_ids": false_ids,
                  "c2_pass": bool(fs <= w_false + 0.05),
                  "c3_ami_single": ami_single, "c3_pass": len(ami_single) <= 1}
        rep[k]["pass_036"] = bool(rep[k]["c1_pass"] and rep[k]["c2_pass"] and rep[k]["c3_pass"])
    rep["n_conf"] = {"k1": sum(r["k_true"] == 1 for r in conf), "k2": sum(r["k_true"] >= 2 for r in conf), "ami": len(ami)}
    Path("results/exp036.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "dev"} | {"tau": tau}, indent=1))


if __name__ == "__main__":
    main()
