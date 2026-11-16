"""EXP-036 F5 cobertura completa: valida y fusiona los briefs de tramo (piloto + particiones).

Para cada una de las entradas del manifiesto (501):
  - pilot_done -> registro del piloto (tramos/briefs_tramos_<mov>.json)
  - si no      -> registros de las carpetas descargadas de SU partición (full/fetched/<job>/), en orden de job
Validación de cada registro aceptado:
  status ok; mismo t0/t1 que el manifiesto; evidencia recalculada aquí con f1_briefs.evidence_lines con el
  mismo sha256 y n_evidence que el manifiesto; validate() de F1 re-ejecutado sobre la salida cruda del último
  intento sin problemas duros y con el mismo objeto JSON que el guardado; los ids citados existen.
Disjunción: un registro de una partición que no le corresponde es una violación (no se usa).
No se inventa nada: una unidad sin registro válido queda como `missing` o `invalid` en el informe.

Escribe full/briefs_tramos_<mov>.json (solo registros válidos) y full/merge_report.json.
Uso: CAVA_minimo/.venv/bin/python -I exp036/f5/tramos/full_merge.py [--full-dir ...]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tramo_briefs as tb  # noqa: E402
from f1_briefs import KEYS, extract_json, validate  # noqa: E402


def check(rec, man, ev, reg, mov):
    errs = []
    if rec.get("status") != "ok":
        return [f"status={rec.get('status')}"]
    if rec.get("movie") != mov:
        errs.append("movie_field_mismatch")
    budgets = [x.get("max_new") for x in rec.get("attempts") or []]
    if any(b2 <= b1 for b1, b2 in zip(budgets, budgets[1:])):
        errs.append("attempts_not_increasing")   # firma de la colisión de uid entre películas (v1)
    if abs(rec["t0"] - man["t0"]) > 1e-6 or abs(rec["t1"] - man["t1"]) > 1e-6:
        errs.append("interval_mismatch")
    if tb.ev_sha(ev) != man["ev_sha"] or len(ev) != man["n_evidence"] or rec.get("n_evidence") != len(ev):
        errs.append("evidence_mismatch")
    if rec.get("ev_sha") and rec["ev_sha"] != man["ev_sha"]:
        errs.append("worker_evidence_sha_mismatch")
    b = rec.get("brief")
    if not isinstance(b, dict) or any(k not in b for k in KEYS):
        errs.append("schema")
    att = (rec.get("attempts") or [None])[-1]
    if not att or "raw" not in att:
        errs.append("no_raw_attempt")
    else:
        hit = att.get("gen_tokens", 0) >= att.get("max_new", 10 ** 9)
        obj, prob = validate(att["raw"], len(ev), hit, reg)
        if prob["hard"]:
            errs.append("revalidate_hard:" + ",".join(prob["hard"]))
        if obj != b or extract_json(att["raw"]) != b:
            errs.append("brief_differs_from_raw")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-dir", default=str(HERE / "full"))
    ap.add_argument("--pilot-dir", default=str(HERE))
    ap.add_argument("--out-dir", help="dónde escribir briefs fusionados y merge_report (por defecto, --full-dir)")
    ap.add_argument("--jobs", help="jobs.json a usar (por defecto, <full-dir>/jobs.json)")
    a = ap.parse_args()
    full = Path(a.full_dir)
    outd = Path(a.out_dir) if a.out_dir else full
    outd.mkdir(parents=True, exist_ok=True)
    man = json.loads((full / "manifest_full.json").read_text())
    jf = Path(a.jobs) if a.jobs else full / "jobs.json"
    jobs = json.loads(jf.read_text()) if jf.exists() else []
    entries = {(e["movie"], e["uid"]): e for e in man["entries"]}
    # jobs de reparación: llevan su propio manifiesto; para sus unidades solo se aceptan registros de reparación
    repair_of = {}
    for j in jobs:
        if j.get("repair_manifest"):
            rm = json.loads(Path(j["repair_manifest"]).read_text())
            j["_assign"] = {(e["movie"], e["uid"]) for e in rm["entries"] if e["shard"] == j["shard"]}
            for k in j["_assign"]:
                repair_of[k] = True

    evid, regs = {}, {}
    for mov in tb.MOVIE_ORDER:
        todo, reg = tb.load_movie(mov, "all")
        regs[mov] = reg
        evid.update({(mov, u["uid"]): u["evidence"] for u in todo})
    assert set(evid) == set(entries), "el manifiesto no coincide con los tramos recalculados"

    # candidatos por unidad, en orden: piloto, luego jobs en orden de lanzamiento
    cands = collections.defaultdict(list)
    violations = []
    for mov in tb.MOVIE_ORDER:
        f = Path(a.pilot_dir) / f"briefs_tramos_{mov}.json"
        for uid, rec in (json.loads(f.read_text()) if f.exists() else {}).items():
            if (mov, uid) in entries and entries[(mov, uid)]["pilot_done"]:
                cands[(mov, uid)].append(("pilot", rec))
    for j in jobs:
        d = full / "fetched" / j["job"]
        for mov in tb.MOVIE_ORDER:
            f = d / f"briefs_tramos_{mov}.json"
            if not f.exists():
                continue
            for uid, rec in json.loads(f.read_text()).items():
                e = entries.get((mov, uid))
                if j.get("repair_manifest"):
                    if (mov, uid) not in j["_assign"]:
                        violations.append({"job": j["job"], "movie": mov, "uid": uid, "manifest_shard": "repair"})
                        continue
                    cands[(mov, uid)].append((j["job"], rec))
                    continue
                if (mov, uid) in repair_of:
                    continue                  # registro original de una unidad reparada: descartado
                if e is None or e["pilot_done"] or e["shard"] != j["shard"]:
                    violations.append({"job": j["job"], "movie": mov, "uid": uid,
                                       "manifest_shard": None if e is None else e["shard"]})
                    continue
                cands[(mov, uid)].append((j["job"], rec))

    merged = {m: {} for m in tb.MOVIE_ORDER}
    status = {}
    for key, e in entries.items():
        mov, uid = key
        errs_all = []
        chosen = None
        for src, rec in cands.get(key, []):
            errs = check(rec, e, evid[key], regs[mov], mov)
            if not errs:
                chosen = (src, rec)
                break
            errs_all.append({"source": src, "errors": errs})
        if chosen:
            merged[mov][uid] = {**chosen[1], "merged_from": chosen[0]}
            status[key] = ("ok", chosen[0])
        else:
            status[key] = ("missing" if not cands.get(key) else "invalid", errs_all)

    for mov, d in merged.items():
        (outd / f"briefs_tramos_{mov}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
    n_ok = sum(v[0] == "ok" for v in status.values())
    per_shard = collections.defaultdict(lambda: collections.Counter())
    for key, (st, _) in status.items():
        per_shard["pilot" if entries[key]["pilot_done"] else f"shard{entries[key]['shard']}"][st] += 1
    rep = {"n_manifest": len(entries), "n_ok": n_ok,
           "n_missing": sum(v[0] == "missing" for v in status.values()),
           "n_invalid": sum(v[0] == "invalid" for v in status.values()),
           "covers_all": n_ok == len(entries), "shards_disjoint": not violations, "violations": violations,
           "per_movie_ok": {m: len(d) for m, d in merged.items()}, "n_repaired_units": len(repair_of),
           "per_source": {k: dict(v) for k, v in per_shard.items()},
           "merged_from": dict(collections.Counter(v[1] for v in status.values() if v[0] == "ok")),
           "problems": [{"movie": k[0], "uid": k[1], "status": v[0], "detail": v[1]}
                        for k, v in status.items() if v[0] != "ok"]}
    (outd / "merge_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k not in ("problems", "violations")}, ensure_ascii=False))
    if rep["problems"]:
        print("problemas (primeros 10):", json.dumps(rep["problems"][:10], ensure_ascii=False))


if __name__ == "__main__":
    main()
