"""EXP-036 F5 piloto de tramos: evaluación pre-registrada (TRAMO_PILOT_PREREG.md §5-6).

Condiciones (todas `hybrid_rerank_loc`, parámetros congelados):
  B      índice congelado exp036/f5/index, niveles scene,topic   (= candidato congelado)
  P      tramos/index_add,     niveles scene,topic,tramo         (principal)
  P_rep  tramos/index_replace, niveles scene,topic,tramo         (secundaria, descriptiva)
Subconjuntos: L = consultas cuya referencia solapa >= 1 s una escena seleccionada; C = resto.
Salida: exp036/f5/results/eval_tramo_pilot.{json,md} y eval_tramo_pilot_per_query.csv.

Uso: CAVA_minimo/.venv/bin/python -I exp036/f5/tramos/tramo_eval.py
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import f5_search  # noqa: E402
from f5_common import EXP, F5, Bge, hit, load_json  # noqa: E402
from f5_eval import mcnemar_exact, per_query, summarize  # noqa: E402
from tramo_briefs import SELECTED  # noqa: E402

CONDS = [("B", F5 / "index", ("scene", "topic")),
         ("P", HERE / "index_add", ("scene", "topic", "tramo")),
         ("P_rep", HERE / "index_replace", ("scene", "topic", "tramo"))]
METHOD = "hybrid_rerank_loc"


def parse_cond(s):
    """'NAME=dir:lvl1,lvl2' (dir absoluto o relativo a /data/tesis-cava)."""
    name, rest = s.split("=", 1)
    d, lv = rest.rsplit(":", 1)
    p = Path(d) if Path(d).is_absolute() else EXP.parent / d
    return name, p, tuple(lv.split(","))


def criteria_for(x, summary, per, subsets):
    """Criterios del piloto (1-4) + desplazamiento en C, para la condición x frente a B."""
    sX, sB = summary[x], summary["B"]
    hits = lambda n, s: int(round(sum(r["R@3"] for r in per[n] if subsets[s](r))))
    return {
        "1_R@3_L_delta>=0.10": {x: sX["L_long"]["R@3"], "B": sB["L_long"]["R@3"],
                                "net_hits": hits(x, "L_long") - hits("B", "L_long"),
                                "ok": hits(x, "L_long") - hits("B", "L_long") >= 3},
        "2_IoU@3_L>=B": {x: sX["L_long"]["IoU@3"], "B": sB["L_long"]["IoU@3"],
                         "ok": sX["L_long"]["IoU@3"] >= sB["L_long"]["IoU@3"]},
        "3_no_global_regression": {"hits_" + x: hits(x, "all"), "hits_B": hits("B", "all"),
                                   "IoU_" + x: sX["all"]["IoU@3"], "IoU_B": sB["all"]["IoU@3"],
                                   "ok": hits(x, "all") >= hits("B", "all")
                                   and sX["all"]["IoU@3"] >= sB["all"]["IoU@3"] - 0.01},
        "4_latency_p95<2s": {"p95_ms": sX["all"]["lat_p95_ms"], "ok": sX["all"]["lat_p95_ms"] < 2000},
        "C_no_worse_than_B": {"hits_" + x: hits(x, "C_rest"), "hits_B": hits("B", "C_rest"),
                              "IoU_" + x: sX["C_rest"]["IoU@3"], "IoU_B": sB["C_rest"]["IoU@3"],
                              "ok": hits(x, "C_rest") >= hits("B", "C_rest")
                              and sX["C_rest"]["IoU@3"] >= sB["C_rest"]["IoU@3"] - 0.01},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queries", default=str(F5 / "queries/queries_provisional_v0.json"))
    ap.add_argument("--out", default=str(F5 / "results"))
    ap.add_argument("--conds", nargs="+", help="NAME=dir:levels ...; debe incluir B. Por defecto, las del piloto")
    ap.add_argument("--tag", default="eval_tramo_pilot")
    a = ap.parse_args()
    conds = [parse_cond(c) for c in a.conds] if a.conds else CONDS
    assert conds[0][0] == "B", "la primera condición debe ser B"
    qs = load_json(a.queries)
    queries = qs["queries"]
    emb = Bge(device="cpu", threads=8)
    sel = {}
    for mov, ids in SELECTED.items():
        sc = {s["scene_id"]: s for s in load_json(EXP / "outputs" / mov / "escenas.json")["scenes"]}
        for i in ids:
            sel[(mov, f"S{i}")] = [[sc[i]["t0"], sc[i]["t1"]]]
    qscene = {q["qid"]: [u for (m, u), iv in sel.items() if m == q["movie"] and hit(iv, q["ref"])] for q in queries}

    per, detail = {}, {q["qid"]: {"qid": q["qid"], "movie": q["movie"], "type": q["type"], "query": q["query"],
                                  "ref": q["ref"], "long_scene": qscene[q["qid"]]} for q in queries}
    for name, idir, levels in conds:
        ix = f5_search.F5Index(idir, embedder=emb, with_exp035=False)
        ix.search("warm up query", queries[0]["movie"], levels, METHOD, 10)
        rows = []
        for q in queries:
            res, dt = ix.search(q["query"], q["movie"], levels, METHOD, 10)
            r = per_query(res, q["ref"]) | {"latency_s": dt, "qid": q["qid"], "movie": q["movie"], "type": q["type"]}
            rows.append(r)
            detail[q["qid"]][name] = {k: r[k] for k in ("R@3", "IoU@3", "R@3_iou10", "dur@3")} | {
                "top3": [{k: x[k] for k in ("unit", "level", "intervals", "t0_hms", "t1_hms", "best_fragment",
                                            "evidence_used")} for x in res[:3]]}
        per[name] = rows
        ix.con.close()

    L = {q["qid"] for q in queries if qscene[q["qid"]]}
    subsets = {"all": lambda r: True, "L_long": lambda r: r["qid"] in L, "C_rest": lambda r: r["qid"] not in L}
    summary = {}
    for name, rows in per.items():
        summary[name] = {s: summarize([r for r in rows if f(r)]) for s, f in subsets.items()}
        summary[name]["by_long_scene"] = {f"{m}:{u}": summarize([r for r in rows if u in qscene[r["qid"]]
                                                                 and r["movie"] == m]) for (m, u) in sel}
    tests = {}
    for x in [n for n, *_ in conds if n != "B"]:
        for s, f in subsets.items():
            xs = [r["R@3"] for r in per[x] if f(r)]
            bs = [r["R@3"] for r in per["B"] if f(r)]
            n10, n01, p = mcnemar_exact(xs, bs)
            tests[f"{x} vs B R@3 [{s}]"] = {"x_only": n10, "B_only": n01, "p_exact": p}

    # criterio pre-registrado del piloto (§6), solo si la condición P está presente (sin cambios)
    crit, verdict = None, None
    if "P" in per:
        briefs = {}
        for mov in SELECTED:
            f = HERE / f"briefs_tramos_{mov}.json"
            briefs.update({f"{mov}:{k}": v for k, v in (load_json(f) if f.exists() else {}).items()})
        n_ok = sum(v["status"] == "ok" for v in briefs.values())
        cp = criteria_for("P", summary, per, subsets)
        crit = {"1_R@3_L_delta>=0.10": {"P": cp["1_R@3_L_delta>=0.10"]["P"], "B": cp["1_R@3_L_delta>=0.10"]["B"],
                                        "net_hits": cp["1_R@3_L_delta>=0.10"]["net_hits"],
                                        "ok": cp["1_R@3_L_delta>=0.10"]["ok"]},
                "2_IoU@3_L_P>=B": {"P": cp["2_IoU@3_L>=B"]["P"], "B": cp["2_IoU@3_L>=B"]["B"],
                                   "ok": cp["2_IoU@3_L>=B"]["ok"]},
                "3_no_global_regression": cp["3_no_global_regression"],
                "4_latency_p95<2s": cp["4_latency_p95<2s"],
                "5_briefs_ok>=95%": {"ok_n": n_ok, "n": len(briefs), "ok": len(briefs) == 56 and n_ok >= 0.95 * 56}}
        c = {k: v["ok"] for k, v in crit.items()}
        verdict = ("POSITIVO (escalar)" if all(c.values()) else
                   "NEGATIVO (no escalar)" if not (c["1_R@3_L_delta>=0.10"] and c["3_no_global_regression"]) else
                   "MIXTO (no escalar sin enmienda)")
    criteria = {x: criteria_for(x, summary, per, subsets) for x in per if x != "B"}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rep = {"run": time.strftime("%Y-%m-%d %H:%M:%S"), "queries_file": a.queries, "queries_status": qs.get("status"),
           "method": METHOD, "conditions": {n: {"index": str(i), "levels": lv} for n, i, lv in conds},
           "L_qids": sorted(L), "n_L": len(L), "summary": summary, "paired": tests,
           "criterion": crit, "verdict": verdict, "criteria_by_condition": criteria,
           "per_query": list(detail.values())}
    (out / f"{a.tag}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    with open(out / f"{a.tag}_per_query.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["qid", "movie", "type", "long_scene", "query", "ref"] +
                   [f"{n}|{k}" for n, *_ in conds for k in ("R@3", "IoU@3", "top1")])
        for d in detail.values():
            w.writerow([d["qid"], d["movie"], d["type"], ";".join(d["long_scene"]), d["query"], json.dumps(d["ref"])] +
                       [v for n, *_ in conds for v in (d[n]["R@3"], round(d[n]["IoU@3"], 3),
                        f"{d[n]['top3'][0]['level']}:{d[n]['top3'][0]['unit']} {d[n]['top3'][0]['t0_hms']}-"
                        f"{d[n]['top3'][0]['t1_hms']}" if d[n]["top3"] else "")])

    print(f"[tramo eval] {a.tag}: consultas {len(queries)} ({qs.get('status')}); L={len(L)}")
    print("| cond | subset | n | R@3 | IoU@3 | R@3[IoU>=.1] | R@1 | dur@3 s | lat mean/p95 ms |")
    print("|---|---|---|---|---|---|---|---|---|")
    for n in per:
        for s in ("all", "L_long", "C_rest"):
            x = summary[n][s]
            print(f"| {n} | {s} | {x['n']} | {x['R@3']:.3f} | {x['IoU@3']:.3f} | {x['R@3_iou10']:.3f} | {x['R@1']:.3f} | "
                  f"{x['dur@3']:.0f} | {x['lat_mean_ms']:.0f}/{x['lat_p95_ms']:.0f} |")
    print("by long scene (R@3 / IoU@3):")
    for k in summary["B"]["by_long_scene"]:
        print("  ", k, {n: (summary[n]["by_long_scene"][k]["R@3"], summary[n]["by_long_scene"][k]["IoU@3"],
                            summary[n]["by_long_scene"][k]["n"]) for n in per})
    print("paired:", json.dumps(tests))
    print("criteria:", json.dumps(criteria))
    if crit:
        print("criterion (pilot):", json.dumps(crit))
        print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
