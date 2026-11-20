"""Worker offline de pyannote. Escribe JSON + RTTM con solapamiento y exclusivo."""
import argparse
import json
import os
import random
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from pyannote.audio import Pipeline

from cava_dia import COMMUNITY, PYANNOTE_AUDIO, SEGMENTATION


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    random.seed(0)
    np.random.seed(0)
    torch.manual_seed(0)
    torch.cuda.manual_seed_all(0)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipe = Pipeline.from_pretrained(COMMUNITY[0], revision=COMMUNITY[1]).to(device)

    wav_path, out = Path(args.wav), Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    x, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
    wav = torch.from_numpy(np.ascontiguousarray(x.mean(1)))[None]
    res = pipe({"waveform": wav, "sample_rate": sr, "uri": wav_path.stem})
    ann = res.speaker_diarization
    exclusive = res.exclusive_speaker_diarization
    rttm = out.with_suffix(".rttm")
    rttm_exclusive = out.with_suffix(".exclusive.rttm")
    with open(rttm, "w") as fh:
        ann.write_rttm(fh)
    with open(rttm_exclusive, "w") as fh:
        exclusive.write_rttm(fh)

    def turns(annotation):
        return [{"t0": float(s.start), "t1": float(s.end), "speaker": str(spk)}
                for s, _, spk in annotation.itertracks(yield_label=True)]

    doc = {"schema": "cava-diarization-v1", "wav": str(wav_path),
           "model": list(COMMUNITY), "segmentation_model": list(SEGMENTATION),
           "pyannote_audio": PYANNOTE_AUDIO, "device": str(device),
           "hf_hub_offline": os.environ.get("HF_HUB_OFFLINE") == "1",
           "rttm": rttm.name, "exclusive_rttm": rttm_exclusive.name,
           "turns": turns(ann), "exclusive_turns": turns(exclusive)}
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    os.replace(tmp, out)


if __name__ == "__main__":
    main()
