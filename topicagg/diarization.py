"""Diarización pyannote community-1 en un subproceso y V# por unidad.

El producto no importa pyannote: dia-venv mantiene su pila CUDA independiente.
La regla `unit_major` es una copia literal de EXP-043 (`eval_exp043.py`).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np

from cava_dia import COMMUNITY, PYANNOTE_AUDIO, SEGMENTATION

DIARIZATION = COMMUNITY
DEFAULT_PYTHON = "/data/tesis-cava/dia-venv/bin/python"
DEFAULT_HF_CACHE = "/data/tesis-cava/hf_dia"


def run_diarization(wav, out_json, *, python=None, hf_cache=None, device=None):
    """Calcula (o reutiliza) turnos crudos, RTTM con solapamiento y RTTM exclusivo."""
    out = Path(out_json)
    if out.exists():
        return json.loads(out.read_text())
    out.parent.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    cache = hf_cache or os.environ.get("CAVA_DIA_HF_CACHE", DEFAULT_HF_CACHE)
    env.update({"HF_HOME": cache, "HF_HUB_CACHE": cache, "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1"})
    if device:
        env["CUDA_VISIBLE_DEVICES"] = str(device)
    cmd = [python or os.environ.get("CAVA_DIA_PYTHON", DEFAULT_PYTHON), "-I", "-m", "cava_dia.run",
           "--wav", str(wav), "--out", str(out)]
    # El paquete se instala editable y sin dependencias en dia-venv; -I impide
    # importar accidentalmente el código o los paquetes del entorno del producto.
    proc = subprocess.run(cmd, cwd=root, env=env, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError(f"diarización falló ({proc.returncode})\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return json.loads(out.read_text())


def rttm(path):
    """Lee un RTTM al formato (t0, t1, hablante) usado por EXP-043."""
    segs = []
    for line in Path(path).read_text().splitlines():
        p = line.split()
        if p and p[0] == "SPEAKER":
            segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
    return segs


def unit_major(units, segs):
    lab = []
    for u0, u1 in units:
        ov = {}
        for a, b, s in segs:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0.0) + o
        lab.append(max(ov, key=ov.get) if ov else None)
    return lab


def unit_labels(units, turns, gate):
    """V# por mayoría temporal; -1 fuera del filtro ASR y V1 = mayor tiempo total."""
    major = unit_major(units, turns)
    total = {}
    for a, b, spk in turns:
        total[spk] = total.get(spk, 0.0) + max(0.0, b - a)
    names = {spk: i + 1 for i, spk in enumerate(sorted(total, key=lambda s: (-total[s], s)))}
    return np.array([names[spk] if spk and bool(gate[i]) else -1
                     for i, spk in enumerate(major)], dtype=np.int64)


def public_turns(turns):
    """Turnos crudos con una marca de solapamiento, sin etiquetas GT ni nombres externos."""
    out = []
    for i, (a, b, spk) in enumerate(turns):
        overlap = any(j != i and other != spk and a < b2 and a2 < b
                      for j, (a2, b2, other) in enumerate(turns))
        out.append({"t0": a, "t1": b, "speaker": spk, "overlap": overlap})
    return out
