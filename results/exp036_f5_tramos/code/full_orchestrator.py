#!/usr/bin/env python3
"""EXP-036 F5 cobertura completa: orquestador distribuido (stdlib; lo lanza run_full_coverage.sh).

Fases:
  0. despliegue + verificación de cada worker: acceso, GPU sin procesos, venv/modelo, sha256 de código,
     manifiesto y entradas idénticos a .56
  1. lanzamiento: partición 0 -> .56 (local), 1 -> .54, 2 -> .55, 3 -> .44 (desacoplado, setsid nohup)
  2. vigilancia cada POLL s (plazo 6 h): `done`/`rc`/pid; worker muerto o inalcanzable -> reintento en el mismo
     host (nueva carpeta sembrada con los ok ya hechos) y, si vuelve a fallar, reasignación a un host libre
  3. descarga de JSON/logs -> full_merge.py -> tramo_index.py (full/index_add) -> tramo_eval.py
     (B, P, F) -> full_report.py -> full_coverage.done
Al vencer el plazo se detienen los workers que sigan vivos (no quedan procesos GPU) y se fusiona lo que haya.

Uso:
  python3 full_orchestrator.py --preflight      # solo fases 0 (despliega y verifica)
  python3 full_orchestrator.py --simulate       # flujo completo con workers falsos (sin GPU), sin fusionar
  python3 full_orchestrator.py                  # ejecución real
"""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent                      # /data/tesis-cava/exp036/f5/tramos
EXP = HERE.parents[1]
ROOT = EXP.parent
FULL = HERE / "full"
LOGS = HERE / "logs"
VPY = str(ROOT / "CAVA_minimo/.venv/bin/python")
K1 = "/data/tesis-cava/exports/deploy_exp036_shards_20261111/id_ed25519"
K2 = str(Path.home() / ".ssh/id_l507_004")
N = 4
WORKERS = [
    {"name": ".56", "ip": None, "key": None, "root": str(ROOT), "cava": str(ROOT / "CAVA_minimo"), "shard": 0},
    {"name": ".54", "ip": "10.100.41.54", "key": K1, "root": "/data/tesis-cava/cava-exp036",
     "cava": "/data/tesis-cava/cava-exp036", "shard": 1},
    {"name": ".55", "ip": "10.100.41.55", "key": K1, "root": "/data/tesis-cava/cava-exp036",
     "cava": "/data/tesis-cava/cava-exp036", "shard": 2},
    {"name": ".44", "ip": "10.100.41.44", "key": K2, "root": "/data/tesis-cava/cava-exp036",
     "cava": "/data/tesis-cava/cava-exp036", "shard": 3},
]
CODE = ["f5/tramos/tramo_briefs.py", "f5/tramos/full_worker.sh", "f5/tramos/full/manifest_full.json",
        "scripts/f1_briefs.py"]
DEPLOY = CODE[:3]                                  # f1_briefs.py ya existe y se exige idéntico (no se copia)
INPUTS = ["{exp}/outputs/{m}/escenas.json", "{cava}/outputs/{m}/work/state.json",
          "{cava}/outputs/{m}/work/summaries.json", "{cava}/outputs/{m}/characters_registry.txt"]
MOVIES = ["Avengers_Endgame", "Spider_Man"]
EVENTS = []


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    with open(LOGS / "full_orchestrator.log", "a") as fh:
        fh.write(line + "\n")


def event(msg):
    EVENTS.append(f"{time.strftime('%F %T')} {msg}")
    log("EVENTO " + msg)


def exp_of(w):
    return f"{w['root']}/exp036"


def ssh_base(w):
    return ["ssh", "-i", w["key"], "-o", "IdentitiesOnly=yes", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ServerAliveInterval=15", f"utec_alumno@{w['ip']}"]


def run(w, cmd, timeout=60):
    args = ["bash", "-c", cmd] if w["ip"] is None else ssh_base(w) + [cmd]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 255, "", "timeout"


def copy_to(w, local, remote):
    if w["ip"] is None:
        if str(Path(local).resolve()) != str(Path(remote).resolve()):
            Path(remote).parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", local, remote], check=True)
        return 0
    s = ssh_base(w)
    return subprocess.run(["scp", "-q"] + s[1:-1] + [local, f"{s[-1]}:{remote}"], timeout=300).returncode


def fetch_dir(w, remote_dir, local_dir):
    local_dir.mkdir(parents=True, exist_ok=True)
    if w["ip"] is None:
        r = subprocess.run(["bash", "-c", f"cp {shlex.quote(remote_dir)}/* {shlex.quote(str(local_dir))}/ 2>/dev/null"])
        return r.returncode
    s = ssh_base(w)
    return subprocess.run(["scp", "-q"] + s[1:-1] + [f"{s[-1]}:{remote_dir}/*", str(local_dir) + "/"],
                          timeout=600, capture_output=True).returncode


def sha_local(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def gpu_busy(w):
    rc, out, _ = run(w, "nvidia-smi --query-compute-apps=pid --format=csv,noheader | wc -l")
    return None if rc != 0 else int(out or 0) > 0


# ------------------------------------------------------------------ fase 0
def preflight(w, deploy=True):
    rc, _, err = run(w, "true", 20)
    if rc != 0:
        return False, f"sin acceso ({err[:80]})"
    e = exp_of(w)
    if deploy and w["ip"] is not None:
        run(w, f"mkdir -p {e}/f5/tramos/full")
        for rel in DEPLOY:
            if copy_to(w, str(EXP / rel), f"{e}/{rel}") != 0:
                return False, f"fallo al copiar {rel}"
    busy = gpu_busy(w)
    if busy is None:
        return False, "nvidia-smi falló"
    if busy:
        return False, "GPU ocupada por otro proceso"
    snap = "models/hub/models--Qwen--Qwen2.5-14B-Instruct/snapshots/cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"
    rc, _, _ = run(w, f"test -x {w['cava']}/.venv/bin/python && test -d {w['cava']}/{snap}")
    if rc != 0:
        return False, "falta venv o modelo"
    files = [f"{e}/{r}" for r in CODE] + [p.format(exp=e, cava=w["cava"], m=m) for m in MOVIES for p in INPUTS]
    ref = [sha_local(EXP / r) for r in CODE] + [sha_local(p.format(exp=str(EXP), cava=str(ROOT / "CAVA_minimo"), m=m))
                                               for m in MOVIES for p in INPUTS]
    rc, out, _ = run(w, "sha256sum " + " ".join(files) + " | awk '{print $1}'")
    got = out.split()
    if rc != 0 or got != ref:
        bad = [f for f, a, b in zip(files, got + [""] * len(files), ref) if a != b]
        return False, f"hash distinto: {bad[:3]}"
    return True, f"ok ({len(files)} ficheros idénticos)"


# ------------------------------------------------------------------ jobs
def launch(w, shard, outdir, fake_env=""):
    e = exp_of(w)
    # ';' (no '&&'): solo el setsid va en segundo plano con sus redirecciones; si no, la subshell en segundo
    # plano heredaba la tubería de ssh/subprocess y el lanzamiento no volvía hasta que acababa el worker.
    cmd = (f"mkdir -p {outdir}; cd /; {fake_env} setsid nohup bash {e}/f5/tramos/full_worker.sh "
           f"{shard} {N} {w['cava']} {outdir} > /dev/null 2>&1 < /dev/null & echo lanzado")
    rc, out, err = run(w, cmd, 30)
    return rc == 0 and "lanzado" in out, err


def job_status(w, outdir):
    rc, out, _ = run(w, f"test -f {outdir}/done && echo DONE; cat {outdir}/rc 2>/dev/null | sed 's/^/RC=/'; "
                        f"p=$(cat {outdir}/pid 2>/dev/null); [ -n \"$p\" ] && kill -0 $p 2>/dev/null && echo ALIVE; "
                        f"cat {outdir}/briefs_tramos_*.json 2>/dev/null | grep -c '\"status\": \"ok\"'", 30)
    if rc not in (0, 1):
        return None
    lines = out.splitlines()
    rcv = next((int(l[3:]) for l in lines if l.startswith("RC=") and l[3:].lstrip("-").isdigit()), None)
    nok = int(lines[-1]) if lines and lines[-1].isdigit() else 0
    return {"done": "DONE" in lines, "rc": rcv, "alive": "ALIVE" in lines, "ok": nok}


def kill_job(w, outdir):
    run(w, f"p=$(cat {outdir}/pid 2>/dev/null); [ -n \"$p\" ] && kill -TERM -- -$p 2>/dev/null; sleep 5; "
           f"[ -n \"$p\" ] && kill -KILL -- -$p 2>/dev/null; true", 40)


def shard_records(shard_jobs):
    """Unión de registros descargados de una partición: ok primero; si no, el último fallido."""
    recs = {}
    for j in shard_jobs:
        for m in MOVIES:
            f = FULL / "fetched" / j["job"] / f"briefs_tramos_{m}.json"
            if f.exists():
                for uid, r in json.loads(f.read_text()).items():
                    k = (m, uid)
                    if k not in recs or (recs[k]["status"] != "ok" and r.get("status") == "ok") or \
                            (recs[k]["status"] != "ok" and r.get("status") != "ok"):
                        recs[k] = {**r, "_job_rc": j.get("rc")}
    return recs


def remaining_of(shard, jobs, assigned):
    recs = shard_records([j for j in jobs if j["shard"] == shard])
    rem = []
    for k in assigned[shard]:
        r = recs.get(k)
        if r and r.get("status") == "ok":
            continue
        hard = (r or {}).get("problems", {}).get("hard", [])
        if r and r.get("_job_rc") == 0 and hard and "oom" not in hard:
            continue                                   # fallo determinista (greedy): no se repite
        rem.append(k)
    return rem, recs


def seed(w, outdir, recs):
    """Siembra la carpeta nueva con los ok ya conseguidos para que el worker los salte."""
    tmp = FULL / "seed_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    run(w, f"mkdir -p {outdir}")
    for m in MOVIES:
        d = {uid: {k: v for k, v in r.items() if k != "_job_rc"} for (mm, uid), r in recs.items()
             if mm == m and r.get("status") == "ok"}
        if d:
            p = tmp / f"briefs_tramos_{m}.json"
            p.write_text(json.dumps(d, ensure_ascii=False))
            copy_to(w, str(p), f"{outdir}/briefs_tramos_{m}.json")


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--timeout-h", type=float, default=6.0)
    ap.add_argument("--poll", type=int, default=120)
    ap.add_argument("--adopt", action="store_true",
                    help="adopta los jobs s<K>_<host>_a1 ya en marcha en lugar de lanzarlos (no duplica GPU)")
    a = ap.parse_args()
    LOGS.mkdir(parents=True, exist_ok=True)
    FULL.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    sim = a.simulate
    poll = 5 if sim else a.poll
    tag = "sim_" if sim else ""
    log(f"=== orquestador {'SIMULACIÓN' if sim else 'PREFLIGHT' if a.preflight else 'REAL'} pid={__import__('os').getpid()}")

    man = json.loads((FULL / "manifest_full.json").read_text())
    assigned = {k: [(e["movie"], e["uid"]) for e in man["entries"] if e["shard"] == k] for k in range(N)}
    log(f"manifiesto: {man['n_total']} tramos, {man['n_pilot_done']} del piloto, particiones "
        f"{ {k: len(v) for k, v in assigned.items()} }")

    jobs = []
    attempts = {k: 0 for k in range(N)}
    resolved = {k: False for k in range(N)}
    pending_reassign = []
    byname = {w["name"]: w for w in WORKERS}
    adopted = set()
    if a.adopt:
        for w in WORKERS:
            k = w["shard"]
            jid = f"s{k}_{w['name'].strip('.')}_a1"
            outdir = f"{exp_of(w)}/f5/tramos/full/{jid}"
            st = job_status(w, outdir)
            if st and (st["alive"] or st["done"]):
                rc, ts, _ = run(w, f"stat -c %Y {outdir}/pid")
                t0 = float(ts) if rc == 0 and ts.isdigit() else time.time()
                attempts[k] = 1
                jobs.append({"job": jid, "shard": k, "host": w["name"], "outdir": outdir,
                             "assigned": len(assigned[k]), "start": time.strftime("%F %T", time.localtime(t0)),
                             "start_ts": t0, "status": "running", "misses": 0, "ok_units": st["ok"], "adopted": True})
                adopted.add(w["name"])
                log(f"adoptado {jid} en {w['name']}: vivo={st['alive']} done={st['done']} ok={st['ok']} "
                    f"(inicio {time.strftime('%T', time.localtime(t0))})")
            else:
                log(f"adopción {w['name']}: no hay job vivo en {outdir}; se tratará con preflight normal")

    healthy = {}
    for w in WORKERS:
        if w["name"] in adopted:          # su GPU está ocupada por NUESTRO job; se comprueban solo los hashes
            ok, msg = True, "adoptado (job propio en marcha)"
        else:
            ok, msg = preflight(w)
        healthy[w["name"]] = ok
        log(f"preflight {w['name']} (shard {w['shard']}): {'OK' if ok else 'FALLO'} {msg}")
    if a.preflight:
        return

    def start(w, shard, recs=None):
        attempts[shard] += 1
        jid = f"{tag}s{shard}_{w['name'].strip('.')}_a{attempts[shard]}"
        outdir = f"{exp_of(w)}/f5/tramos/full/{jid}"
        if recs:
            seed(w, outdir, recs)
        fake = ""
        if sim:   # shard 3 falla 1 vez (reintento en el mismo host); shard 2 falla 2 veces (reasignación)
            fail = (shard == 3 and attempts[shard] == 1) or (shard == 2 and attempts[shard] <= 2)
            fake = f"FAKE=1 FAKE_SLEEP={8 + 4 * shard} FAKE_RC={1 if fail else 0}"
        ok, err = launch(w, shard, outdir, fake)
        j = {"job": jid, "shard": shard, "host": w["name"], "outdir": outdir, "assigned": len(assigned[shard]),
             "start": time.strftime("%F %T"), "start_ts": time.time(), "status": "running" if ok else "launch_failed",
             "misses": 0}
        jobs.append(j)
        log(f"lanzado {jid} en {w['name']}: {'ok' if ok else 'FALLO ' + err[:120]}")
        return ok

    for w in WORKERS:
        if w["name"] in adopted:
            continue
        if healthy[w["name"]]:
            if not start(w, w["shard"]):
                pending_reassign.append(w["shard"])
        else:
            event(f"worker {w['name']} no pasa preflight: su partición {w['shard']} queda para reasignar")
            pending_reassign.append(w["shard"])

    deadline = t_start + a.timeout_h * 3600
    last_progress = 0
    while not all(resolved.values()):
        if time.time() > deadline:
            event(f"PLAZO de {a.timeout_h} h agotado: se detienen los workers vivos")
            for j in jobs:
                if j["status"] == "running":
                    kill_job(byname[j["host"]], j["outdir"])
                    fetch_dir(byname[j["host"]], j["outdir"], FULL / "fetched" / j["job"])
                    j.update(status="killed_timeout", end=time.strftime("%F %T"), end_ts=time.time())
            break
        time.sleep(poll)
        for j in jobs:
            if j["status"] != "running":
                continue
            w = byname[j["host"]]
            st = job_status(w, j["outdir"])
            if st is None:
                j["misses"] += 1
                if j["misses"] >= 5:
                    event(f"{j['job']}: host {w['name']} inalcanzable 5 veces seguidas -> se da por muerto")
                    j.update(status="dead", end=time.strftime("%F %T"), end_ts=time.time())
                    healthy[w["name"]] = False
                continue
            j["misses"] = 0
            j["ok_units"] = st["ok"]
            if st["done"]:
                j.update(status="done", rc=st["rc"], end=time.strftime("%F %T"), end_ts=time.time())
            elif not st["alive"] and time.time() - j["start_ts"] > 90:
                event(f"{j['job']}: proceso muerto sin marca done")
                j.update(status="dead", rc=st["rc"], end=time.strftime("%F %T"), end_ts=time.time())
            if j["status"] != "running":
                fetch_dir(w, j["outdir"], FULL / "fetched" / j["job"])
                lf = FULL / "fetched" / j["job"] / "worker.log"
                if lf.exists():
                    (LOGS / f"full_{j['job']}.log").write_text(lf.read_text())
                log(f"{j['job']} terminó: status={j['status']} rc={j.get('rc')} ok={st['ok']}/{j['assigned']} "
                    f"({(j['end_ts'] - j['start_ts']) / 60:.1f} min)")
        # particiones cuyo último job terminó
        for k in range(N):
            if resolved[k] or k in pending_reassign:
                continue
            kj = [j for j in jobs if j["shard"] == k]
            if not kj or kj[-1]["status"] == "running":
                continue
            last = kj[-1]
            if sim:
                rem = [] if last.get("rc") == 0 else assigned[k]
                recs = {}
            else:
                rem, recs = remaining_of(k, jobs, assigned)
            if not rem:
                resolved[k] = True
                log(f"partición {k} RESUELTA (último job {last['job']})")
                continue
            if attempts[k] >= 4:
                event(f"partición {k}: {len(rem)} tramos sin completar tras 4 intentos; se abandona")
                resolved[k] = True
                continue
            w = byname[last["host"]]
            n_on_host = sum(1 for j in kj if j["host"] == w["name"])
            if healthy[w["name"]] and n_on_host < 2 and gpu_busy(w) is False:
                event(f"partición {k}: {len(rem)} tramos pendientes; reintento en el mismo host {w['name']}")
                start(w, k, recs)
            else:
                event(f"partición {k}: {len(rem)} tramos pendientes; se encola para reasignar")
                pending_reassign.append(k)
        # reasignación a hosts libres
        for k in list(pending_reassign):
            busy_hosts = {j["host"] for j in jobs if j["status"] == "running"}
            free = [w for w in WORKERS if healthy[w["name"]] and w["name"] not in busy_hosts]
            free = [w for w in free if gpu_busy(w) is False]
            if not free:
                continue
            w = free[0]
            recs = {} if sim else remaining_of(k, jobs, assigned)[1]
            event(f"partición {k} reasignada a {w['name']}")
            pending_reassign.remove(k)
            if not start(w, k, recs):
                pending_reassign.append(k)
        if time.time() - last_progress > (30 if sim else 600):
            last_progress = time.time()
            prog = ", ".join(f"{j['job']}:{j.get('ok_units', 0)}/{j['assigned']}" for j in jobs if j["status"] == "running")
            log(f"progreso: {prog or '(sin jobs activos)'}; resueltas {sum(resolved.values())}/{N}")

    wall = (time.time() - t_start) / 60
    jl = [{k: v for k, v in j.items() if k != "misses"} for j in jobs]
    if sim:
        log(f"SIMULACIÓN terminada en {wall:.1f} min: " + json.dumps([(j['job'], j['status'], j.get('rc')) for j in jl]))
        for w in WORKERS:
            run(w, f"rm -rf {exp_of(w)}/f5/tramos/full/sim_*")
        subprocess.run(["bash", "-c", f"rm -rf {FULL}/fetched/sim_* {LOGS}/full_sim_*"])
        return
    (FULL / "jobs.json").write_text(json.dumps(jl, ensure_ascii=False, indent=1))
    (FULL / "orchestrator_state.json").write_text(json.dumps({"events": EVENTS, "wall_min": round(wall, 1),
                                                              "jobs": jl}, ensure_ascii=False, indent=1))
    # no deben quedar procesos GPU de este trabajo
    for w in WORKERS:
        log(f"GPU {w['name']} tras la generación: {'OCUPADA' if gpu_busy(w) else 'libre'}")

    def step(name, args, timeout=7200):
        log(f"--- {name}: {' '.join(args)}")
        with open(LOGS / f"full_{name}.log", "w") as fh:
            r = subprocess.run(args, stdout=fh, stderr=subprocess.STDOUT, cwd=str(ROOT), timeout=timeout)
        log(f"--- {name} rc={r.returncode} (log logs/full_{name}.log)")
        return r.returncode

    t = "exp036/f5/tramos"
    rc_m = step("merge", [VPY, "-I", f"{t}/full_merge.py"])
    merge = json.loads((FULL / "merge_report.json").read_text()) if (FULL / "merge_report.json").exists() else {}
    rc_i = rc_e = None
    if rc_m == 0 and merge.get("n_ok", 0) > 56:
        rc_i = step("index", [VPY, "-I", f"{t}/tramo_index.py", "--briefs-dir", f"{t}/full", "--out-root", f"{t}/full",
                              "--variants", "index_add"])
        if rc_i == 0:
            rc_e = step("eval", [VPY, "-I", f"{t}/tramo_eval.py", "--tag", "eval_tramo_full", "--conds",
                                 "B=exp036/f5/index:scene,topic", "P=exp036/f5/tramos/index_add:scene,topic,tramo",
                                 "F=exp036/f5/tramos/full/index_add:scene,topic,tramo"])
    else:
        event(f"merge rc={rc_m}, n_ok={merge.get('n_ok')}: no se construye índice ni se evalúa")
    (FULL / "orchestrator_state.json").write_text(json.dumps({"events": EVENTS, "wall_min": round(wall, 1),
                                                              "jobs": jl}, ensure_ascii=False, indent=1))
    rc_r = step("report", [VPY, "-I", f"{t}/full_report.py"])
    adoption = json.loads((FULL / "adoption.json").read_text()) if (FULL / "adoption.json").exists() else {}
    done = {"finished": time.strftime("%F %T"), "wall_min": round((time.time() - t_start) / 60, 1),
            "n_ok": merge.get("n_ok"), "covers_all": merge.get("covers_all"), "rc": {"merge": rc_m, "index": rc_i,
            "eval": rc_e, "report": rc_r}, "adopted": adoption.get("adopted"), "report": "exp036/f5/TRAMO_FULL.md"}
    (HERE / "full_coverage.done").write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
    log(f"=== FIN {json.dumps(done, ensure_ascii=False)}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("ERROR FATAL\n" + traceback.format_exc())
        if not ({"--simulate", "--preflight"} & set(sys.argv)):
            (HERE / "full_coverage.done").write_text(json.dumps({"finished": time.strftime("%F %T"), "status": "error",
                                                                 "see": "logs/full_orchestrator.log"}) + "\n")
        sys.exit(1)
