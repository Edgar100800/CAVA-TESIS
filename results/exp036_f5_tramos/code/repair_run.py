#!/usr/bin/env python3
"""EXP-036 F5 cobertura completa v2: regenera SOLO las unidades afectadas por la colisión de uid entre películas.

Causa (v1): tramo_briefs.py indexaba registros por `uid` en lugar de (película, uid); los 12 pares de uid
repetidos entre Endgame y Spider-Man dentro de una misma partición compartieron registro (24 unidades).
Este script: construye full/manifest_repair.json (24 unidades; cada par en la MISMA partición, para ejercitar
el arreglo), despliega el código corregido, verifica hashes/GPU libre, lanza 3 jobs (uno por GPU, lote 8),
espera, descarga a full/fetched/<job> y escribe full_v2/jobs.json (jobs v1 + reparación).

Uso: python3 exp036/f5/tramos/repair_run.py      (stdlib; reutiliza full_orchestrator.py)
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import full_orchestrator as o  # noqa: E402

FULL = HERE / "full"
V2 = HERE / "full_v2"
NS = 3
HOSTS = [o.WORKERS[0], o.WORKERS[1], o.WORKERS[2]]      # .56, .54, .55


def main():
    o.LOGS.mkdir(parents=True, exist_ok=True)
    V2.mkdir(parents=True, exist_ok=True)
    o.log("=== REPARACIÓN v2 (colisión de uid entre películas)")
    rep = json.loads((V2 / "merge_report_v1_guarded.json").read_text())
    bad = sorted({(p["movie"], p["uid"]) for p in rep["problems"]})
    man = json.loads((FULL / "manifest_full.json").read_text())
    E = {(e["movie"], e["uid"]): e for e in man["entries"]}
    uids = sorted({u for _, u in bad}, key=lambda u: (int(u[1:].split("_")[0]), u))
    assert all((m, u) in bad for u in uids for m in o.MOVIES), "cada uid afectado debe estar en ambas películas"
    entries = []
    for i, u in enumerate(uids):
        for m in o.MOVIES:
            entries.append({**E[(m, u)], "shard": i % NS, "full_manifest_shard": E[(m, u)]["shard"]})
    doc = {"built": time.strftime("%F %T"), "purpose": "repair v2: uid collision across movies", "n_shards": NS,
           "n_total": len(entries), "per_shard": {k: sum(e["shard"] == k for e in entries) for k in range(NS)},
           "entries": entries}
    mp = FULL / "manifest_repair.json"
    mp.write_text(json.dumps(doc, indent=1))
    o.log(f"manifiesto de reparación: {len(entries)} unidades, particiones {doc['per_shard']}")
    if "--manifest-only" in sys.argv:
        return
    o.N = NS          # launch() pasa N al worker; la reparación usa 3 particiones (el worker exige coincidencia)

    jobs = []
    for k, w in enumerate(HOSTS):
        e = o.exp_of(w)
        if w["ip"] is not None:
            for rel in ("f5/tramos/tramo_briefs.py", "f5/tramos/full_worker.sh", "f5/tramos/full/manifest_repair.json"):
                assert o.copy_to(w, str(o.EXP / rel), f"{e}/{rel}") == 0, (w["name"], rel)
        files = ["f5/tramos/tramo_briefs.py", "f5/tramos/full_worker.sh", "f5/tramos/full/manifest_repair.json",
                 "f5/tramos/full/manifest_full.json", "scripts/f1_briefs.py"]
        rc, out, _ = o.run(w, "sha256sum " + " ".join(f"{e}/{f}" for f in files) + " | awk '{print $1}'")
        assert out.split() == [o.sha_local(o.EXP / f) for f in files], (w["name"], "hash distinto")
        assert o.gpu_busy(w) is False, (w["name"], "GPU ocupada")
        jid = f"repair_s{k}_{w['name'].strip('.')}"
        outdir = f"{e}/f5/tramos/full/{jid}"
        ok, err = o.launch(w, k, outdir, f"MANIFEST={e}/f5/tramos/full/manifest_repair.json")
        assert ok, (w["name"], err)
        jobs.append({"job": jid, "shard": k, "host": w["name"], "outdir": outdir, "assigned": doc["per_shard"][k],
                     "start": time.strftime("%F %T"), "start_ts": time.time(), "status": "running",
                     "repair_manifest": str(mp)})
        o.log(f"lanzado {jid} en {w['name']} (hashes idénticos, GPU libre)")

    deadline = time.time() + 3600
    while any(j["status"] == "running" for j in jobs) and time.time() < deadline:
        time.sleep(30)
        for j in jobs:
            if j["status"] != "running":
                continue
            w = next(x for x in HOSTS if x["name"] == j["host"])
            st = o.job_status(w, j["outdir"])
            if st and st["done"]:
                j.update(status="done", rc=st["rc"], ok_units=st["ok"], end=time.strftime("%F %T"), end_ts=time.time())
            elif st and not st["alive"] and time.time() - j["start_ts"] > 90:
                j.update(status="dead", rc=st["rc"], end=time.strftime("%F %T"), end_ts=time.time())
            if j["status"] != "running":
                o.fetch_dir(w, j["outdir"], FULL / "fetched" / j["job"])
                lf = FULL / "fetched" / j["job"] / "worker.log"
                if lf.exists():
                    (o.LOGS / f"full_{j['job']}.log").write_text(lf.read_text())
                o.log(f"{j['job']} terminó: {j['status']} rc={j.get('rc')} ok={j.get('ok_units')}/{j['assigned']} "
                      f"({(j['end_ts'] - j['start_ts']) / 60:.1f} min)")
    for j in jobs:
        if j["status"] == "running":
            w = next(x for x in HOSTS if x["name"] == j["host"])
            o.kill_job(w, j["outdir"])
            j.update(status="killed_timeout", end=time.strftime("%F %T"), end_ts=time.time())
            o.log(f"{j['job']} detenido por plazo")
    for w in o.WORKERS:
        o.log(f"GPU {w['name']} tras la reparación: {'OCUPADA' if o.gpu_busy(w) else 'libre'}")
    v1 = json.loads((FULL / "jobs.json").read_text())
    (V2 / "jobs.json").write_text(json.dumps(v1 + jobs, ensure_ascii=False, indent=1))
    o.log("=== REPARACIÓN terminada: " + json.dumps([(j["job"], j["status"], j.get("rc"), j.get("ok_units")) for j in jobs]))


if __name__ == "__main__":
    main()
