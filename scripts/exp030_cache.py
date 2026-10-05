"""EXP-030: caché de transcripciones por unidad (Parakeet) y segmentos Whisper (solo VoxConverse; en AMI y BBC
Whisper ya está en la caché del pipeline) → data/asr_compare/<dominio>/<id>.json"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.asr_parakeet import Parakeet  # noqa: E402
from topicagg.speaker import XVec  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402

O = Path("data/asr_compare")
O.mkdir(parents=True, exist_ok=True)
pk = Parakeet()
xv = XVec()
from faster_whisper import WhisperModel  # noqa: E402
wm = WhisperModel("large-v3", device="cuda", compute_type="float16")


def save(dom, i, d):
    (O / dom).mkdir(parents=True, exist_ok=True)
    (O / dom / f"{i}.json").write_text(json.dumps(d, ensure_ascii=False))


V = Path("data/voxconverse")
for split in ("test", "dev"):
    for w in sorted(V.glob(f"wav_{split}/**/*.wav")):
        if (O / f"vox_{split}" / f"{w.stem}.json").exists():
            continue
        z = np.load(V / "xvec" / split / f"{w.stem}.npz") if (V / "xvec" / split / f"{w.stem}.npz").exists() else None
        if z is None:
            continue
        units = z["units"].tolist()
        audio = load_audio(str(w))
        segs, _ = wm.transcribe(str(w), vad_filter=True)
        # xvec de TODAS las unidades: el criterio 2 necesita las unidades que un ASR marca como habla sin serlo
        np.save(O / f"vox_{split}_{w.stem}.xall.npy", xv(audio, units, np.ones(len(units), bool)).astype(np.float16))
        save(f"vox_{split}", w.stem, {"units": units, "parakeet": pk.units(audio, units),
                                      "whisper_segments": [(s.start, s.end, s.text.strip()) for s in segs]})
        print(f"[asr] vox {split} {w.stem}", flush=True)
D = Path("data/ami")
for m in (D / "meetings_fresh3.txt").read_text().split():
    if (O / "ami" / f"{m}.json").exists():
        continue
    units = json.loads((D / "signals" / f"{m}.json").read_text())["unit_times"]
    save("ami", m, {"units": units, "parakeet": pk.units(load_audio(str(D / "media" / m / f"{m}.Mix-Headset.wav")), units)})
    print(f"[asr] ami {m}", flush=True)
for ep in range(1, 12):
    w = Path("data/cava_runs_doc") / f"bbc_{ep:02d}" / "work"
    if (O / "bbc" / f"bbc_{ep:02d}.json").exists():
        continue
    units = json.loads((w / "state.json").read_text())["units"]
    save("bbc", f"bbc_{ep:02d}", {"units": units, "parakeet": pk.units(load_audio(str(w / "audio.wav")), units)})
    print(f"[asr] bbc {ep:02d}", flush=True)
print("ASR_CACHE_DONE")
