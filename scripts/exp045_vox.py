"""EXP-045-Q: pistas ASR y WavLM sobre los 20 VoxConverse dev de refset_v1 (solo audio).

Uso: python scripts/exp045_vox.py --wavs DIR --out DIR --variant ref|fast [--stages asr,xvec]
  asr   : faster-whisper large-v3 (ref float16 / fast int8_float16), vad_filter=True, como el producto
  xvec  : WavLM-sv por unidad de 5 s con el filtro de habla ASR >= 50 % de la transcripción ref (FP32 / FP16)
Escribe <out>/<variante>/<uri>.asr.json, <uri>.xvec.npy y timings.json (segundos por etapa, duración total).
"""
import argparse
import json
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.pipeline import transcribe  # noqa: E402

FILES = "abjxc afjiv ahnss aisvi akthc ampme asxwr atgpi aufkn azisu bauzd bdopb bkwns blwmj bravd bspxd bwzyf bxpwa bydui ccokr".split()


def units_of(d, u=5.0):
    return [[float(s), float(min(s + u, d))] for s in np.arange(0, d - 1, u)]


def gate_of(units, segs):
    return np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in segs) >= 0.5 * (u1 - u0)
                     for u0, u1 in units])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wavs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--variant", choices=("ref", "fast"), required=True)
    ap.add_argument("--stages", default="asr,xvec")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    out = Path(a.out) / a.variant
    out.mkdir(parents=True, exist_ok=True)
    stages = a.stages.split(",")
    tm_f = out / "timings.json"
    tm = json.loads(tm_f.read_text()) if tm_f.exists() else {}
    durs = {}
    for u in FILES:
        with wave.open(str(Path(a.wavs) / f"{u}.wav")) as w:
            durs[u] = w.getnframes() / w.getframerate()
    tm["duration_s"] = durs
    if "asr" in stages:
        ct = "int8_float16" if a.variant == "fast" else None
        transcribe(Path(a.wavs) / f"{FILES[0]}.wav", a.device, ct)  # calentamiento (carga del modelo fuera de ventana)
        t_all = time.time()
        per = {}
        for u in FILES:
            t0 = time.time()
            segs = transcribe(Path(a.wavs) / f"{u}.wav", a.device, ct)
            per[u] = round(time.time() - t0, 2)
            (out / f"{u}.asr.json").write_text(json.dumps(segs, ensure_ascii=False))
        tm["asr_s"] = per
        tm["asr_total_s"] = round(time.time() - t_all, 1)
        print("asr", a.variant, tm["asr_total_s"], flush=True)
    if "xvec" in stages:
        from topicagg.speaker import XVec
        from topicagg.voice import load_audio
        xv = XVec(a.device, half=a.variant == "fast")
        t_all = time.time()
        for u in FILES:
            ref_asr = json.loads((Path(a.out) / "ref" / f"{u}.asr.json").read_text())
            units = units_of(durs[u])
            gate = gate_of(units, ref_asr)
            x = xv(load_audio(str(Path(a.wavs) / f"{u}.wav")), units, gate)
            np.save(out / f"{u}.xvec.npy", x)
            np.save(out / f"{u}.gate.npy", gate)
        tm["xvec_total_s"] = round(time.time() - t_all, 1)
        print("xvec", a.variant, tm["xvec_total_s"], flush=True)
    tm_f.write_text(json.dumps(tm, indent=1))


if __name__ == "__main__":
    main()
