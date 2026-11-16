"""Análisis del A/B corto EXP-041-L.

Entrada: CSV con una fila por participante y una columna por par:
  id, seq, t, h, control, abierta
  t/h/control: "A", "B" o "Iguales" (los lados se mapean a CAVA/U con --map)
  seq: 1..4 (qué lado ocupó CAVA en cada par, según el diseño)

Uso:
  python scripts/ab_analysis.py --csv juicios.csv --seq-map '{"1":{"t":"A","h":"B"},"2":{"t":"B","h":"A"},"3":{"t":"A","h":"B"},"4":{"t":"B","h":"A"}}' \
      --out results/exp041_l.json

Salida: proporción por par, IC Wilson, binomial exacta, combinada con bootstrap
clusterizado por persona, y tabla markdown para el anexo.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

RNG = np.random.default_rng(0)


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, centre - half, centre + half


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--seq-map", required=True,
                    help='JSON: seq -> {"t": "A"|"B", "h": "A"|"B", "control": "A"|"B"} (lado de CAVA)')
    ap.add_argument("--out", required=True)
    ap.add_argument("--boot", type=int, default=10000)
    args = ap.parse_args()

    seq_map = json.loads(args.seq_map)
    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    res = {"n_people": len(rows), "pairs": {}, "combined": {}, "control": {}}

    def cava_side(seq, pair):
        return seq_map[str(seq)].get(pair)

    votes = []  # (persona, par, 1 si CAVA, 0 si U)
    for r in rows:
        for pair in ("t", "h"):
            ans = (r.get(pair) or "").strip().lower()
            if ans not in ("a", "b"):
                continue
            side = cava_side(r.get("seq"), pair)
            votes.append((r["id"], pair, int(ans == str(side).lower())))

    for pair in ("t", "h"):
        v = [x[2] for x in votes if x[1] == pair]
        if not v:
            continue
        k, n = int(sum(v)), len(v)
        p, lo, hi = wilson(k, n)
        bt = binomtest(k, n, 0.5, alternative="two-sided")
        res["pairs"][pair] = {"k": k, "n": n, "p_hat": p, "wilson": [lo, hi], "p_value": bt.pvalue}

    if votes:
        k, n = int(sum(x[2] for x in votes)), len(votes)
        p, lo, hi = wilson(k, n)
        bt = binomtest(k, n, 0.5, alternative="two-sided")
        by_person = {}
        for pid, _, y in votes:
            by_person.setdefault(pid, []).append(y)
        ids = list(by_person)
        boots = []
        for _ in range(args.boot):
            samp = RNG.choice(ids, size=len(ids), replace=True)
            ys = [y for i in samp for y in by_person[i]]
            boots.append(np.mean(ys) if ys else np.nan)
        boots = np.array([b for b in boots if np.isfinite(b)])
        res["combined"] = {"k": k, "n": n, "p_hat": p, "wilson": [lo, hi],
                           "p_value": bt.pvalue,
                           "boot_ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]}

    ctrl = [(r.get("control") or "").strip().lower() for r in rows]
    ctrl = [c for c in ctrl if c in ("a", "b", "iguales")]
    if ctrl:
        res["control"] = {"n": len(ctrl), "same": sum(c == "iguales" for c in ctrl),
                          "same_rate": sum(c == "iguales" for c in ctrl) / len(ctrl)}

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))

    print(json.dumps(res, ensure_ascii=False, indent=1))
    print("\n| Condición | k/n | Preferencia CAVA | IC 95 % Wilson | p (binomial) |")
    print("|---|---:|---:|---|---:|")
    for name, d in [("T", res["pairs"].get("t")), ("H", res["pairs"].get("h")),
                    ("Combinada", res.get("combined"))]:
        if not d:
            continue
        lo, hi = d.get("wilson", [float("nan")] * 2)
        ci = d.get("boot_ci") or [lo, hi]
        print(f"| {name} | {d['k']}/{d['n']} | {d['p_hat']:.3f} | "
              f"[{ci[0]:.3f}, {ci[1]:.3f}] | {d['p_value']:.4f} |")


if __name__ == "__main__":
    main()
