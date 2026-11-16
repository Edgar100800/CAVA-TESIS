"""EXP-036 F5: evaluación interna de recuperación sobre un conjunto de consultas con intervalo de referencia.

Métricas por consulta (top-k dentro de la película de la consulta):
  R@k     1 si algún resultado del top-k solapa >= 1 s con algún intervalo de referencia
  IoU@k   máximo IoU temporal (unión de spans del resultado vs unión de referencias) en el top-k
  MRR@10  1/rango del primer acierto
  dur@3   duración media de los intervalos devueltos en el top-3 (expone aciertos "baratos" por escenas largas)
  latencia: consulta -> resultados (incluye embebido de la consulta en CPU), modelo ya cargado
Referencias sin sistema: azar sobre escenas F2 (esperanza exacta) y techo de IoU de una sola escena F2.

AVISO: con queries_provisional_v0.json esto es una línea base INTERNA, no el test pre-registrado.

Uso:
  P=CAVA_minimo/.venv/bin/python
  $P -I exp036/f5/f5_eval.py --queries exp036/f5/queries/queries_provisional_v0.json --tag provisional_v0
"""
import argparse
import csv
import json
import sys
import time
from math import comb
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f5_search  # noqa: E402
from f5_common import F5, hit, iou, length, load_json  # noqa: E402

CORE = ["bm25", "bge", "hybrid", "hybrid_rerank", "hybrid_rerank_loc"]
REF035 = ["exp035b", "exp035b_scene", "exp035b_noblock"]
# Variantes secundarias (ablaciones; no forman parte de la comparación principal)
SECONDARY = [("hybrid_rerank_loc", ("scene", "topic"), 3, "hybrid_rerank_loc[scene+topic]"),
             ("hybrid_rerank_loc", ("scene", "topic", "fine"), 3, "hybrid_rerank_loc[scene+topic+fine]"),
             ("hybrid_rerank_loc", ("scene",), 1, "hybrid_rerank_loc[1 evidence line] (post-hoc)")]


def per_query(res, ref):
    ivs = [r["intervals"] for r in res]
    first = next((k for k, iv in enumerate(ivs[:10], 1) if hit(iv, ref)), None)
    return {f"R@{k}": float(any(hit(iv, ref) for iv in ivs[:k])) for k in (1, 3, 5)} | {
        # suplementaria (post-hoc): acierto que además exige IoU >= 0.10; neutraliza intervalos enormes
        "R@3_iou10": float(any(iou(iv, ref) >= 0.10 for iv in ivs[:3])),
        "IoU@1": iou(ivs[0], ref) if ivs else 0.0,
        "IoU@3": max([iou(iv, ref) for iv in ivs[:3]] or [0.0]),
        "MRR@10": 1.0 / first if first else 0.0,
        "dur@3": float(np.mean([length(iv) for iv in ivs[:3]])) if ivs else 0.0}


def boot_ci(x, n=2000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    return [round(float(np.percentile(m, 2.5)), 3), round(float(np.percentile(m, 97.5)), 3)]


def mcnemar_exact(a, b):
    """p bilateral exacto sobre pares discordantes (a=1,b=0) vs (a=0,b=1)."""
    n10 = int(sum(1 for x, y in zip(a, b) if x and not y))
    n01 = int(sum(1 for x, y in zip(a, b) if y and not x))
    n = n10 + n01
    if n == 0:
        return n10, n01, 1.0
    k = min(n10, n01)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)
    return n10, n01, round(p, 4)


def summarize(rows, keys=("R@1", "R@3", "R@5", "R@3_iou10", "IoU@1", "IoU@3", "MRR@10", "dur@3")):
    out = {k: round(float(np.mean([r[k] for r in rows])), 3) for k in keys}
    lat = np.array([r["latency_s"] for r in rows]) * 1000
    out |= {"lat_mean_ms": round(float(lat.mean()), 1), "lat_p95_ms": round(float(np.percentile(lat, 95)), 1),
            "lat_max_ms": round(float(lat.max()), 1), "n": len(rows),
            "R@3_ci95": boot_ci([r["R@3"] for r in rows]), "IoU@3_ci95": boot_ci([r["IoU@3"] for r in rows])}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(F5 / "queries/queries_provisional_v0.json"))
    ap.add_argument("--tag", default="provisional_v0")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--out", default=str(F5 / "results"))
    ap.add_argument("--index", default=str(F5 / "index"))
    a = ap.parse_args()
    qs = load_json(a.queries)
    queries = qs["queries"]
    t0 = time.perf_counter()
    ix = f5_search.load(device=a.device, threads=a.threads, index_dir=a.index)
    t_load = time.perf_counter() - t0

    configs = [(m, ("scene",), 3, m) for m in CORE] + [(m, ("scene",), 3, m) for m in REF035] + SECONDARY
    _, cold = ix.search("first query after loading", queries[0]["movie"], ("scene",), "hybrid_rerank_loc", 10)
    for m, lv, _, _ in configs[:len(CORE) + len(REF035)]:        # calentamiento (no medido)
        ix.search("warm up query", queries[0]["movie"], lv, m, 10)

    per = {name: [] for *_, name in configs}
    detail = []
    for q in queries:
        ref = q["ref"]
        drow = {"qid": q["qid"], "movie": q["movie"], "type": q["type"], "query": q["query"], "ref": ref}
        for m, lv, nev, name in configs:
            f5_search.LOC_MAX_EV = nev
            res, dt = ix.search(q["query"], q["movie"], lv, m, 10)
            f5_search.LOC_MAX_EV = 3
            r = per_query(res, ref) | {"latency_s": dt}
            per[name].append(r | {"qid": q["qid"], "movie": q["movie"], "type": q["type"]})
            drow[name] = {**r, "top3": [{k: x[k] for k in ("unit", "level", "intervals", "t0_hms", "t1_hms",
                                                          "score", "best_fragment", "evidence_used")}
                                        for x in res[:3]]}
        detail.append(drow)

    # referencias sin sistema sobre escenas F2
    base = {"random_scene_R@3": [], "oracle_scene_IoU": [], "n_scenes_overlapping_ref": []}
    for q in queries:
        sc = [d for d in ix.docs if d["movie"] == q["movie"] and d["level"] == "scene"]
        h = sum(hit(d["spans"], q["ref"]) for d in sc)
        base["random_scene_R@3"].append(1 - comb(len(sc) - h, 3) / comb(len(sc), 3))
        base["oracle_scene_IoU"].append(max(iou(d["spans"], q["ref"]) for d in sc))
        base["n_scenes_overlapping_ref"].append(h)
    baselines = {k: round(float(np.mean(v)), 3) for k, v in base.items()}
    # techo de la unidad escena: si la escena correcta fuese top-1 siempre
    base_long = [max((d["dur"] for d in ix.docs if d["movie"] == q["movie"] and d["level"] == "scene"
                      and hit(d["spans"], q["ref"])), default=0) for q in queries]
    baselines["correct_scene_dur_median_s"] = float(np.median(base_long))
    # de qué nivel de EXP-035 vienen los aciertos top-3 de exp035b (bloque VJudge = fuente de las consultas)
    lvl = {}
    for d in detail:
        for t in d["exp035b"]["top3"]:
            if hit(t["intervals"], d["ref"]):
                lvl[t["level"]] = lvl.get(t["level"], 0) + 1
    baselines["exp035b_hits_in_top3_by_level"] = lvl

    summary = {}
    for name, rows in per.items():
        summary[name] = {"all": summarize(rows)}
        for mov in sorted({r["movie"] for r in rows}):
            summary[name][mov] = summarize([r for r in rows if r["movie"] == mov])
        summary[name]["by_type_R@3"] = {t: round(float(np.mean([r["R@3"] for r in rows if r["type"] == t])), 3)
                                        for t in sorted({r["type"] for r in rows})}
    tests = {}
    for x, y in (("hybrid_rerank_loc", "exp035b"), ("hybrid_rerank_loc", "exp035b_scene"),
                 ("hybrid_rerank_loc[scene+topic]", "exp035b_noblock"), ("hybrid_rerank", "exp035b_noblock"),
                 ("hybrid_rerank", "exp035b"), ("hybrid", "bge"), ("hybrid", "bm25"), ("hybrid_rerank", "hybrid")):
        n10, n01, p = mcnemar_exact([r["R@3"] for r in per[x]], [r["R@3"] for r in per[y]])
        tests[f"{x} vs {y} (R@3)"] = {"x_only": n10, "y_only": n01, "p_exact": p}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = {"tag": a.tag, "queries_file": a.queries, "queries_status": qs.get("status"), "n_queries": len(queries),
           "index_dir": a.index,
           "run": time.strftime("%Y-%m-%d %H:%M:%S"), "device": a.device,
           "torch_threads": __import__("torch").get_num_threads(), "model_load_s": round(t_load, 2),
           "first_query_latency_s": round(cold, 3), "query_pad_tokens": f5_search.QUERY_LEN,
           "rrf_k": f5_search.RRF_K, "rerank_candidates": f5_search.N_CAND, "min_overlap_s": 1.0,
           "baselines_no_system": baselines, "summary": summary, "paired_tests": tests, "per_query": detail}
    (out / f"eval_{a.tag}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    with open(out / f"eval_{a.tag}_per_query.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        names = list(per)
        w.writerow(["qid", "movie", "type", "query", "ref"] + [f"{n}|{k}" for n in names for k in ("R@3", "IoU@3", "top1")])
        for d in detail:
            w.writerow([d["qid"], d["movie"], d["type"], d["query"], json.dumps(d["ref"])] +
                       [v for n in names for v in (d[n]["R@3"], round(d[n]["IoU@3"], 3),
                                                   (f"{d[n]['top3'][0]['unit']} {d[n]['top3'][0]['t0_hms']}-"
                                                    f"{d[n]['top3'][0]['t1_hms']}") if d[n]["top3"] else "")])

    print(f"[F5 eval] {a.tag}: {len(queries)} queries ({qs.get('status')}) load={t_load:.1f}s "
          f"threads={rep['torch_threads']}")
    print(f"first query after load: {cold * 1000:.0f} ms")
    print("| method | R@1 | R@3 (95% CI) | R@5 | R@3[IoU>=.1] | IoU@1 | IoU@3 | MRR@10 | dur@3 s | lat mean/p95 ms |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for name, s in summary.items():
        x = s["all"]
        print(f"| {name} | {x['R@1']:.3f} | {x['R@3']:.3f} {x['R@3_ci95']} | {x['R@5']:.3f} | {x['R@3_iou10']:.3f} | {x['IoU@1']:.3f} | "
              f"{x['IoU@3']:.3f} | {x['MRR@10']:.3f} | {x['dur@3']:.0f} | {x['lat_mean_ms']:.0f}/{x['lat_p95_ms']:.0f} |")
    print("baselines:", baselines)
    print("paired:", json.dumps(tests))


if __name__ == "__main__":
    main()
