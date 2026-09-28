"""Distribución nula del veto relativo: ¿supera el VJudge a jueces aleatorios?

Estadístico por película: beat F1 de (orden SegLoop saltando la mitad inferior
del juez) menos la media de ese mismo F1 con vetos aleatorios del 50 %
(`--ctrl-draws` sorteos). Media entre películas = estadístico. Se compara el
juez real contra `--null` jueces uniformes aleatorios: p empírico.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_hierarchy import f1_at, load_film  # noqa: E402


def beat_f1(pred, g):
    st, (lo, hi) = g["shot_times"], g["beat_span"]
    return f1_at([st[c][0] for c in pred if lo < c < hi], [st[b][0] for b in g["beat"]], 60.0)


def stat(judge, films, K, rng, ctrl_draws):
    vals = []
    for tt, (g, cuts, seg) in films.items():
        order = sorted(cuts, key=lambda c: -seg[c])
        p = judge[tt]
        med = np.median([p[c] for c in cuts])
        real = beat_f1(sorted([c for c in order if p[c] >= med][:K]), g)
        n_veto = sum(1 for c in cuts if p[c] < med)
        ctrl = np.mean([beat_f1(sorted([c for c in order if c not in set(
            rng.choice(cuts, n_veto, replace=False).tolist())][:K]), g)
            for _ in range(ctrl_draws)])
        vals.append(real - ctrl)
    return float(np.mean(vals))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inp", default="data/vjudge_relational")
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--ks", type=int, nargs="+", default=[12, 24, 36])
    ap.add_argument("--null", type=int, default=200)
    ap.add_argument("--ctrl-draws", type=int, default=20)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rng = np.random.default_rng(0)
    films, real = {}, {}
    for tt in Path(args.films_file).read_text().split():
        rows = json.loads((Path(args.inp) / f"{tt}.mm.json").read_text())
        g = load_film(tt, Path(args.corpus))
        films[tt] = (g, [r["cut"] for r in rows], {r["cut"]: r["seg_score"] for r in rows})
        real[tt] = {r["cut"]: r["p_new"] for r in rows}
    res = {}
    for K in args.ks:
        s_real = stat(real, films, K, rng, args.ctrl_draws)
        null = [stat({tt: {c: rng.random() for c in films[tt][1]} for tt in films},
                     films, K, rng, args.ctrl_draws) for _ in range(args.null)]
        p = (1 + sum(x >= s_real for x in null)) / (1 + len(null))
        res[K] = {"stat": round(s_real, 4), "null_mean": round(float(np.mean(null)), 4),
                  "null_p95": round(float(np.percentile(null, 95)), 4), "p_emp": round(p, 4)}
        print(f"K={K}: real {s_real:+.4f} | null media {np.mean(null):+.4f} "
              f"p95 {np.percentile(null, 95):+.4f} | p empírico {p:.4f}", flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps({"n_films": len(films), "null": args.null,
                                              "results": res}, indent=1))


if __name__ == "__main__":
    main()
