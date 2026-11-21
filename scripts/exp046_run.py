"""EXP-046-STAB: corridas repetidas de la cadena completa desde el video, modo R (ref) o D (ASR determinista).

Uso (una corrida):
  python scripts/exp046_run.py run --mode R|D --video Spider_Man --out RUNDIR [--machine 56]
Uso (cola por máquina, varios videos concurrentes dentro de 24 GB de GPU):
  python scripts/exp046_run.py queue --jobs jobs.json --workers 3 --machine 56

Sin etiquetas del LLM, sin cortar mp4, hilos BLAS = 1, pila v1.1. Cada corrida parte de un directorio vacío (nada cacheado).
Se guardan además las pistas que usa el mapa (voz, visual, bge de transcripción y de vjudge) para el análisis de atribución.
La cola reparte la GPU con un libro de memoria (`gpu_slot`) por etapa; no cambia ninguna salida.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

BASE = Path("/data/tesis-cava/exp046")
LEDGER = Path("/tmp/exp046_gpu_ledger.json")
LOCK = Path("/tmp/exp046_gpu_ledger.lock")
BUDGET_MIB = 22000
# peso por etapa en MiB: picos medidos con nvidia-smi en la corrida piloto (ASR ≈ 4,1-5,8 GB; SigLIP ≈ 1,4; VL-7B ≈ 16,7;
# WavLM/pyannote ≈ 4) más margen; el presupuesto deja ≈ 2 GB para los contextos CUDA de los procesos inactivos
WEIGHT = {"asr": 6500, "signals": 2000, "vjudge": 17500, "speakers": 4000}
PIN_ENV = {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
           "VECLIB_MAXIMUM_THREADS": "1", "TOKENIZERS_PARALLELISM": "false"}


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class gpu_slot:
    """Libro de memoria de GPU compartido (archivo + flock): una etapa entra si cabe en BUDGET_MIB."""

    def __init__(self, stage):
        self.w, self.stage, self.key = WEIGHT[stage], stage, f"{os.getpid()}:{stage}"

    def __enter__(self):
        t0 = time.time()
        while True:
            with open(LOCK, "a+") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)
                led = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"held": {}, "queue": []}
                led["held"] = {k: v for k, v in led["held"].items() if _alive(int(k.split(":")[0]))}
                led["queue"] = [q for q in led["queue"] if _alive(int(q.split(":")[0]))]
                if self.key not in led["queue"]:
                    led["queue"].append(self.key)
                used = sum(v for v in led["held"].values())
                # FIFO estricto: solo el primero de la cola puede entrar (evita que las etapas chicas dejen sin turno al vjudge)
                if led["queue"][0] == self.key and used + self.w <= BUDGET_MIB:
                    led["queue"].pop(0)
                    led["held"][self.key] = self.w
                    LEDGER.write_text(json.dumps(led))
                    self.waited = time.time() - t0
                    return self
                LEDGER.write_text(json.dumps(led))
            time.sleep(3)

    def __exit__(self, *a):
        try:
            import torch
            if torch.cuda.is_initialized():
                torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
        with open(LOCK, "a+") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            led = json.loads(LEDGER.read_text()) if LEDGER.exists() else {"held": {}, "queue": []}
            led["held"].pop(self.key, None)
            LEDGER.write_text(json.dumps(led))


def versions_record():
    import importlib.metadata as md
    import platform
    pk = ["torch", "transformers", "faster-whisper", "ctranslate2", "numpy", "scipy", "scikit-learn", "av", "pillow",
          "huggingface-hub", "safetensors", "tokenizers", "onnxruntime-gpu", "nvidia-cublas-cu12", "nvidia-cudnn-cu12",
          "nvidia-cuda-runtime-cu12"]
    vs = {}
    for p in pk:
        try:
            vs[p] = md.version(p)
        except md.PackageNotFoundError:
            vs[p] = None

    def sh(cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    rec = {"hostname": platform.node(), "python": platform.python_version(), "packages": vs,
           "gpu": sh("nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader"),
           "cpu": sh("lscpu | grep 'Model name' | sed 's/.*: *//'"),
           "kernel": platform.release(), "ffmpeg": sh("ffmpeg -version | head -1"),
           "dia_venv": sh(f"{os.environ.get('CAVA_DIA_PYTHON', '/data/tesis-cava/dia-venv/bin/python')} -I -c "
                          "\"import torch,pyannote.audio as p;print('torch',torch.__version__,'pyannote.audio',p.__version__)\""),
           "env": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                  "LD_LIBRARY_PATH", "CAVA_DIA_PYTHON", "CAVA_DIA_HF_CACHE")}}
    return rec


def do_run(a):
    import numpy as np
    import topicagg.diarization as D
    from exp045_common import STACK, VIDEOS
    from topicagg.pipeline import Pipeline

    orig = D.run_diarization

    def dia(*x, **k):
        # el LD_LIBRARY_PATH con el cuDNN del venv de producto rompe el cuDNN de dia-venv: se quita solo para pyannote
        old = os.environ.pop("LD_LIBRARY_PATH", None)
        try:
            return orig(*x, **k)
        finally:
            if old is not None:
                os.environ["LD_LIBRARY_PATH"] = old
    D.run_diarization = dia

    cfg = VIDEOS[a.video]
    out = Path(a.out)
    if (out / "run_manifest.json").exists() and (out / "stab_done.json").exists():
        print("ya hecho", out)
        return
    p = Pipeline(cfg["path"], out, profile=cfg["profile"], stack=STACK, labels=False, audio=cfg["audio"],
                 asr_mode="det" if a.mode == "D" else "ref")
    tim = {}

    def wrap(name, stage):
        orig_m = getattr(p, name)

        def f():
            t0 = time.time()
            if stage:
                with gpu_slot(stage):
                    t1 = time.time()
                    orig_m()
                tim[name + "_wait"] = round(t1 - t0, 1)
                tim[name + "_run"] = round(time.time() - t1, 1)
            else:
                orig_m()
                tim[name + "_run"] = round(time.time() - t0, 1)
        setattr(p, name, f)
    for n, st in (("prepare", None), ("asr", "asr"), ("signals", "signals"), ("vjudge", "vjudge"),
                  ("topic_map", None), ("labels", None), ("speakers", "speakers")):
        wrap(n, st)
    t_all = time.time()
    gate = p.run(cut=False)
    # pistas del mapa para atribución y diferencias por pista
    np.savez_compressed(out / "work" / "sig_bge.npz", transcript=p.sig["transcript"], vjudge=p.sig["vjudge"])
    if not (out / "work/asr.det.json").exists():
        (out / "work/asr.ref.json").write_text(json.dumps({"segments": p.asr_segments}, ensure_ascii=False))
    (out / "stab_done.json").write_text(json.dumps({
        "mode": a.mode, "video": a.video, "machine": a.machine, "G_version": gate["G_version"],
        "wall_s": round(time.time() - t_all, 1), "stage_s": tim, "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))
    # intermedios grandes (se reconstruyen desde el video): audio y fotogramas
    (out / "work" / "audio.wav").unlink(missing_ok=True)
    import shutil
    shutil.rmtree(out / "work" / "frames", ignore_errors=True)
    print(f"[exp046] {a.mode} {a.video} {a.machine} listo en {time.time() - t_all:.0f} s", flush=True)


def queue(a):
    jobs = json.loads(Path(a.jobs).read_text())
    jobs = [j for j in jobs if j["machine"] == a.machine]
    env = os.environ.copy() | PIN_ENV
    from concurrent.futures import ThreadPoolExecutor
    log = BASE / "logs"
    log.mkdir(parents=True, exist_ok=True)

    def one(j):
        out = Path(j["out"])
        if (out / "stab_done.json").exists():
            return j["out"], 0
        lf = log / (j["out"].replace("/", "_").strip("_")[-120:] + ".log")
        with open(lf, "w") as fh:
            r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/exp046_run.py"), "run", "--mode", j["mode"],
                                "--video", j["video"], "--out", j["out"], "--machine", a.machine],
                               env=env, stdout=fh, stderr=subprocess.STDOUT)
        print(f"[queue {a.machine}] {j['mode']} {j['video']} {j['out']} rc={r.returncode}", flush=True)
        return j["out"], r.returncode
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(one, jobs))
    print("QUEUE_DONE", a.machine, sum(1 for _, rc in res if rc), "fallos", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--mode", choices=("R", "D"), required=True)
    r.add_argument("--video", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--machine", default="56")
    q = sub.add_parser("queue")
    q.add_argument("--jobs", required=True)
    q.add_argument("--workers", type=int, default=3)
    q.add_argument("--machine", required=True)
    v = sub.add_parser("versions")
    v.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "run":
        do_run(a)
    elif a.cmd == "queue":
        queue(a)
    else:
        Path(a.out).write_text(json.dumps(versions_record(), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
