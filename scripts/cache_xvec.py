"""Caché de embeddings de hablante (WavLM-sv, EXP-028) por unidad, con su filtro de habla y GT de hablante.

  voxconverse/<split>  unidades de 5 s, filtro = VAD oráculo (RTTM), dom = hablante dominante GT
                       → data/voxconverse/xvec/<split>/<id>.npz
  ami                  unidades de 10 s del pipeline, filtro = unidad con texto ASR, dom = hablante dominante GT
                       → data/ami/signals/<m>.xvec.npz
  bbc                  unidades de 5 s del pipeline, filtro = ≥ 50 % cubierta por ASR (sin GT de hablante)
                       → data/cava_runs_doc/bbc_XX/work/speaker_xvec.npy (la caché del pipeline)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import speech_gate  # noqa: E402
from eval_speaker_embed import UNIT, rttm, unit_gt  # noqa: E402
from eval_voice_identities import dominant  # noqa: E402
from topicagg.speaker import XVec  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--which", nargs="+", default=["voxconverse", "ami", "bbc"])
    args = ap.parse_args()
    xv = XVec()
    if "voxconverse" in args.which:
        V = Path("data/voxconverse")
        for split in ("dev", "test"):
            out = V / "xvec" / split
            out.mkdir(parents=True, exist_ok=True)
            gt_dir = V / "voxconverse-master" / split
            for w in sorted(V.glob(f"wav_{split}/**/*.wav")):
                rt = gt_dir / f"{w.stem}.rttm"
                if not rt.exists() or (out / f"{w.stem}.npz").exists():
                    continue
                audio = load_audio(str(w))
                dur = len(audio) / 16000
                units = [[t, min(t + UNIT, dur)] for t in np.arange(0, dur - 1.0, UNIT)]
                dom, gate = unit_gt(units, rttm(rt))
                np.savez_compressed(out / f"{w.stem}.npz", x=xv(audio, units, gate).astype(np.float16), gate=gate,
                                    dom=np.array([d or "" for d in dom]), units=np.asarray(units, np.float32))
                print(f"[xvec] vox {split} {w.stem}: {len(units)} unidades", flush=True)
    if "ami" in args.which:
        D = Path("data/ami")
        ms = (D / "meetings_all80.txt").read_text().split() + (D / "meetings_fresh3.txt").read_text().split()
        for m in ms:
            fj, wav = D / "signals" / f"{m}.json", D / "media" / m / f"{m}.Mix-Headset.wav"
            if not (fj.exists() and wav.exists()) or (D / "signals" / f"{m}.xvec.npz").exists():
                continue
            meta = json.loads(fj.read_text())
            units = meta["unit_times"]
            gate = np.array([bool((t or "").strip()) for t in meta["asr_text"]])
            dom = dominant(units, json.loads((D / "gt" / f"{m}.json").read_text())["speech"])
            np.savez_compressed(D / "signals" / f"{m}.xvec.npz", x=xv(load_audio(str(wav)), units, gate).astype(np.float16),
                                gate=gate, dom=np.array([d or "" for d in dom]))
            print(f"[xvec] ami {m}: {len(units)} unidades", flush=True)
    if "bbc" in args.which:
        for ep in range(1, 12):
            w = Path("data/cava_runs_doc") / f"bbc_{ep:02d}" / "work"
            if (w / "speaker_xvec.npy").exists():
                continue
            st = json.loads((w / "state.json").read_text())
            gate = speech_gate(st["units"], st["asr_segments"])
            np.save(w / "speaker_xvec.npy", xv(load_audio(str(w / "audio.wav")), st["units"], gate))
            print(f"[xvec] bbc {ep:02d}", flush=True)


if __name__ == "__main__":
    main()
