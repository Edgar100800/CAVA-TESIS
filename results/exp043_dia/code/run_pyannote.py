"""EXP-043-DIA: pyannote speaker-diarization-community-1 sobre una lista de audios.

Escribe un RTTM por archivo (diarización con solapamientos) y una línea de tiempos en
<out>/timing.jsonl. Retoma: salta los RTTM ya escritos. Correr con HF_HUB_OFFLINE=1.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from pyannote.audio import Pipeline

ap = argparse.ArgumentParser()
ap.add_argument("--list", required=True, help="txt con una ruta de audio por línea")
ap.add_argument("--out", required=True)
args = ap.parse_args()

out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)
pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1").to(torch.device("cuda"))
print("pipeline ok", flush=True)

files = [Path(l.strip()) for l in open(args.list) if l.strip()]
tl = open(out / "timing.jsonl", "a")
for k, f in enumerate(files):
    uri = f.stem
    dst = out / f"{uri}.rttm"
    if dst.exists():
        continue
    x, sr = sf.read(str(f), dtype="float32", always_2d=True)
    wav = torch.from_numpy(np.ascontiguousarray(x.mean(1)))[None]
    t0 = time.time()
    res = pipe({"waveform": wav, "sample_rate": sr, "uri": uri})
    dt = time.time() - t0
    ann = res.speaker_diarization
    tmp = dst.with_suffix(".tmp")
    with open(tmp, "w") as fh:
        ann.write_rttm(fh)
    tmp.rename(dst)
    tl.write(json.dumps({"uri": uri, "audio_s": len(x) / sr, "proc_s": dt,
                         "n_spk": len(ann.labels())}) + "\n")
    tl.flush()
    print(f"{k + 1}/{len(files)} {uri} {len(x) / sr:.0f}s audio {dt:.1f}s {len(ann.labels())} hablantes", flush=True)
print("FIN", flush=True)
