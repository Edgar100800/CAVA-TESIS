"""EXP-034: ítems de audio del benchmark del filtro de habla (ver pre-registro en EXPERIMENT_LOG).

Cada ítem: dominio, id, wav, unidades y split. Dominios:
  ava    AVASpeech-SMAD, minutos 15–30 (labels relativas a la ventana), unidades de 5 s
  mix    narrador sintético VoxConverse + MUSAN (scripts/exp034_mix.py), unidades de 5 s
  docmix narrador sintético con estructura de documental (EXP-035a, scripts/exp035_mix.py)
  domix  voces dominantes (K >= 2, principal >= 70 %) con la misma estructura (EXP-039, scripts/exp039_mix.py)
  ami    AMI fresh3, Mix-Headset, unidades del caché de señales (10 s)
  bbc    BBC 01–11, audio del pipeline, unidades del pipeline (5 s)
"""
import json
from pathlib import Path

import numpy as np

G = Path("data/gatebench")
LAB = G / "AVASpeech_Music_Labels" / "labels"
UNIT = 5.0


def grid(dur, unit=UNIT):
    return [[float(t), float(min(t + unit, dur))] for t in np.arange(0, dur - 1.0, unit)]


def ava_items():
    ids = sorted(p.stem for p in (LAB / "speech labels").glob("*.csv"))
    for k, i in enumerate(ids):
        w = G / "ava_audio" / f"{i}.wav"
        if w.exists() and w.stat().st_size > 900 * 16000 * 2 * 0.9:
            yield {"dom": "ava", "id": i, "wav": str(w), "units": grid(900.0), "split": "dev" if k % 2 == 0 else "conf"}


def mix_items(sub="mix"):
    for f in sorted((G / sub).glob("*/*.json")):
        m = json.loads(f.read_text())
        yield {"dom": sub, "id": f"{f.parent.name}_{f.stem}", "wav": str(f.with_suffix(".wav")), "units": m["units"],
               "split": "dev" if f.parent.name == "dev" else "conf"}


def ami_items():
    D = Path("data/ami")
    for m in (D / "meetings_fresh3.txt").read_text().split():
        units = json.loads((D / "signals" / f"{m}.json").read_text())["unit_times"]
        yield {"dom": "ami", "id": m, "wav": str(D / "media" / m / f"{m}.Mix-Headset.wav"), "units": units, "split": "conf"}


def bbc_items():
    for ep in range(1, 12):
        w = Path("data/cava_runs_doc") / f"bbc_{ep:02d}" / "work"
        yield {"dom": "bbc", "id": f"bbc_{ep:02d}", "wav": str(w / "audio.wav"),
               "units": json.loads((w / "state.json").read_text())["units"], "split": "sec"}


def all_items(doms=("ava", "mix", "ami", "bbc")):
    f = {"ava": ava_items, "mix": mix_items, "docmix": lambda: mix_items("docmix"), "domix": lambda: mix_items("domix"),
         "ami": ami_items, "bbc": bbc_items}
    for d in doms:
        yield from f[d]()


def coverage(units, segs):
    """Fracción de cada unidad cubierta por la unión de segmentos [(a, b), ...]."""
    segs = sorted((float(a), float(b)) for a, b, *_ in segs)
    merged = []
    for a, b in segs:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    out = np.zeros(len(units))
    for k, (u0, u1) in enumerate(units):
        out[k] = sum(max(0.0, min(u1, b) - max(u0, a)) for a, b in merged) / max(u1 - u0, 1e-9)
    return out
