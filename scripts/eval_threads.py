"""EXP-015: enlace de hilos no contiguos — votantes frozen vs proximidad temporal.

GT (solo evaluación): cast de MovieNet. Par (i, j), |i−j| ≥ 2, ambos anotados:
positivo Jaccard ≥ 0.5, negativo Jaccard 0, resto excluido.
Votantes (similitud entre unidades, cada uno por separado):
  visual, dialogue, summary_old, summary_new (bge), names (Jaccard de nombres
  del campo CHARACTERS). Si un votante no tiene evidencia para un par (sin
  diálogo, sin nombres) se abstiene y recibe su mediana en la película: neutro,
  y todos los votantes se evalúan sobre los mismos pares.
Primario: AP en pares de largo alcance (|i−j| ≥ 10) − AP del prior temporal.
Secundario: consenso (≥ 2 votantes por encima de su mediana) vs mejor votante
solo con el mismo nº de enlaces (precisión).
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrative_eval import BgeEmbedder, average_precision  # noqa: E402

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")
STOP = {"The", "A", "An", "His", "Her", "Their", "Two", "Three", "Several", "Group", "Man",
        "Woman", "Men", "Women", "Boy", "Girl", "People", "Person", "Young", "Old", "Other",
        "Another", "And", "Unknown", "None", "Officer", "Police", "Soldier", "Soldiers",
        "Guard", "Guards", "Crowd", "Family", "Mother", "Father", "Child", "Children",
        "Characters", "Character", "Unnamed", "Driver", "Doctor", "Nurse", "Couple"}
VOTERS = ("visual", "dialogue", "summary_old", "summary_new", "names")


def names_of(summary):
    head = summary.split("|")[0]
    head = head.split(":", 1)[1] if ":" in head else head
    return {w for w in re.findall(r"\b[A-Z][a-z]+\b", head) if w not in STOP}


def centroid(rows):
    rows = rows[np.linalg.norm(rows, axis=1) > 0]
    if len(rows) == 0:
        return None
    c = rows.mean(0)
    n = np.linalg.norm(c)
    return c / n if n > 0 else None


def sim_matrix(vecs):
    n = len(vecs)
    S = np.full((n, n), np.nan)
    ok = [i for i, v in enumerate(vecs) if v is not None]
    if ok:
        M = np.stack([vecs[i] for i in ok])
        sub = M @ M.T
        for a, i in enumerate(ok):
            S[i, ok] = sub[a]
    return S


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--voters-dir", default="data/movienet_voters")
    ap.add_argument("--min-gap", type=int, default=10)
    ap.add_argument("--out", required=True)
    ap.add_argument("--summary-dir", default="data/vjudge_ledger", help="resúmenes old")
    ap.add_argument("--entity-dir", default="data/vjudge_ledger_entity",
                    help="resúmenes entity; si falta el archivo se omiten summary_new/names")
    ap.add_argument("--dialogue-dir", default="data/movienet_voters",
                    help="npz con campo `dialogue` por shot")
    ap.add_argument("--quorum-voters", nargs="+", default=list(VOTERS),
                    help="votantes del consenso ≥2 (EXP-016: visual dialogue summary_old)")
    ap.add_argument("--best-single", default=None,
                    help="votante solo fijado de antemano para comparar el consenso "
                         "(por defecto: el de mayor AP en la película, como en EXP-015)")
    args = ap.parse_args()
    bge = BgeEmbedder()
    rows, cons = {}, {}

    for tt in Path(args.films_file).read_text().split():
        a = json.loads((MN / "annotation" / f"{tt}.json").read_text())
        cast = [c for c in (a.get("cast") or []) if c.get("pid") and c["pid"] != "others"]
        if not cast:
            continue
        old = json.loads((Path(args.summary_dir) / f"{tt}.summaries.json").read_text())
        f_new = Path(args.entity_dir) / f"{tt}.summaries.json"
        new = json.loads(f_new.read_text()) if f_new.exists() else None
        n_units = len(old)
        by_shot = {}
        for c in cast:
            by_shot.setdefault(c["shot_idx"], set()).add(c["pid"])
        gt = [set().union(*[by_shot.get(s, set()) for s in range(u["lo"], u["hi"])]) for u in old]

        vis = np.asarray(np.load(Path(args.corpus) / f"{tt}.npz")["visual"], np.float32)
        dia = np.asarray(np.load(Path(args.dialogue_dir) / f"{tt}.npz")["dialogue"], np.float32)
        span = [(u["lo"], min(u["hi"], len(vis))) for u in old]
        S = {"visual": sim_matrix([centroid(vis[lo:hi]) for lo, hi in span]),
             "dialogue": sim_matrix([centroid(dia[lo:hi]) for lo, hi in span])}
        for key, sums in (("summary_old", old), ("summary_new", new)):
            if sums is None:
                continue
            e = bge([u["summary"] for u in sums])
            S[key] = sim_matrix([v if np.linalg.norm(v) > 0 else None for v in e])
        if new is not None:
            nm = [names_of(u["summary"]) for u in new]
            J = np.full((n_units, n_units), np.nan)
            for i in range(n_units):
                for j in range(n_units):
                    if nm[i] and nm[j]:
                        J[i, j] = len(nm[i] & nm[j]) / len(nm[i] | nm[j])
            S["names"] = J

        pairs, y = [], []
        for i in range(n_units):
            for j in range(i + args.min_gap, n_units):
                if not gt[i] or not gt[j]:
                    continue
                jac = len(gt[i] & gt[j]) / len(gt[i] | gt[j])
                if jac >= 0.5 or jac == 0:
                    pairs.append((i, j))
                    y.append(int(jac >= 0.5))
        y = np.asarray(y)
        if len(pairs) < 20 or y.sum() == 0 or y.sum() == len(y):
            continue
        scores = {}
        for k in [v for v in VOTERS if v in S]:
            v = np.asarray([S[k][i, j] for i, j in pairs], float)
            v[np.isnan(v)] = np.nanmedian(v) if np.isfinite(v).any() else 0.0
            scores[k] = v
        scores["temporal_prior"] = -np.asarray([j - i for i, j in pairs], float)
        r = {"n_pairs": len(pairs), "pos_rate": float(y.mean())}
        for k, v in scores.items():
            r[f"ap_{k}"] = average_precision(v + 1e-9 * np.random.default_rng(0).random(len(v)), y)
        rows[tt] = r

        qv = [k for k in args.quorum_voters if k in scores]
        votes = sum((scores[k] > np.median(scores[k])).astype(int) for k in qv)
        linked = votes >= 2
        n_link = int(linked.sum())
        best = args.best_single or max(qv, key=lambda k: r[f"ap_{k}"])
        top = np.argsort(-scores[best])[:n_link]
        cons[tt] = {"n_links": n_link,
                    "prec_consensus": float(y[linked].mean()) if n_link else None,
                    "prec_best_single": float(y[top].mean()) if n_link else None,
                    "best_single": best}

    def paired(a, b):
        d = np.array([r[a] - r[b] for r in rows.values()])
        return {"mean": round(float(d.mean()), 4), "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4),
                "n": len(d), "z": round(float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))), 2)}

    present = [k for k in VOTERS + ("temporal_prior",) if all(f"ap_{k}" in r for r in rows.values())]
    ap_mean = {k: round(float(np.mean([r[f"ap_{k}"] for r in rows.values()])), 4) for k in present}
    ap_mean["random"] = round(float(np.mean([r["pos_rate"] for r in rows.values()])), 4)
    crit = {f"{k}_vs_temporal": paired(f"ap_{k}", "ap_temporal_prior") for k in present
            if k != "temporal_prior"}
    dc = [c["prec_consensus"] - c["prec_best_single"] for c in cons.values()
          if c["prec_consensus"] is not None]
    crit["consensus_vs_best_single_precision"] = {
        "mean": round(float(np.mean(dc)), 4),
        "se": round(float(np.std(dc, ddof=1) / np.sqrt(len(dc))), 4), "n": len(dc)}
    crit["consensus_prec_mean"] = round(float(np.mean([c["prec_consensus"] for c in cons.values()
                                                       if c["prec_consensus"] is not None])), 4)
    crit["best_single_prec_mean"] = round(float(np.mean([c["prec_best_single"] for c in cons.values()
                                                         if c["prec_best_single"] is not None])), 4)
    rep = {"protocol": "exp015_threads_v1", "quorum_voters": qv if rows else args.quorum_voters,
           "best_single": args.best_single, "films_file": args.films_file, "min_gap": args.min_gap,
           "n_films": len(rows), "ap_mean": ap_mean, "criteria": crit, "per_film": rows,
           "consensus": cons}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(f"{len(rows)} películas · AP (|i−j| ≥ {args.min_gap}): {ap_mean}")
    for k, v in crit.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
