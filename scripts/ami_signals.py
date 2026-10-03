"""Señales CAVA para reuniones AMI (EXP-020), unidades fijas de 10 s.

Por reunión escribe data/ami/signals/<m>.npz y <m>.json:
  voice       espectrograma log-mel + tono (topicagg.voice), sin modelos
  visual      SigLIP del fotograma central de la unidad (cámara de sala:
              ES Corner, IS C, TS Overview1; guardada como <m>.Room.avi)
  transcript  ASR faster-whisper large-v3 (texto por unidad) -> bge en CPU aparte
y data/ami/vjudge/<m>.summaries.json: resumen Qwen2.5-VL-7B frozen por unidad
desde 3 fotogramas + el texto ASR de la unidad (formato de los mapas: lo, hi,
summary). Ningún dato de GT entra en las señales. Resumible por etapa.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.voice import load_audio, voice_features  # noqa: E402

D = Path("data/ami")
UNIT = 10.0
PROMPT = ("These {n} frames come from one 10-second stretch of a meeting recording.\n"
          "Speech: \"{speech}\"\n\nIn ONE sentence, say what happens here: who is involved, "
          "what they are doing or discussing. Plain text, no preamble.")


def frame_at(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=448:-2", str(out)], check=False)
    return out if out.exists() else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meetings", default="data/ami/meetings_40.txt")
    ap.add_argument("--stages", nargs="+", default=["units", "voice", "asr", "visual", "vjudge"])
    args = ap.parse_args()
    import torch
    sig_dir, vj_dir, fr_dir = D / "signals", D / "vjudge", D / "frames"
    for d in (sig_dir, vj_dir, fr_dir):
        d.mkdir(parents=True, exist_ok=True)
    meetings = Path(args.meetings).read_text().split()
    os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")

    for m in meetings:
        wav, vid = D / "media" / m / f"{m}.Mix-Headset.wav", D / "media" / m / f"{m}.Room.avi"
        if not (wav.exists() and vid.exists() and wav.stat().st_size > 1e6 and vid.stat().st_size > 1e6):
            print(f"[ami-signals] {m}: falta audio o video, se omite", flush=True)
            continue
        fj = sig_dir / f"{m}.json"
        meta = json.loads(fj.read_text()) if fj.exists() else {"meeting": m}
        if "units" in args.stages and "unit_times" not in meta:
            audio = load_audio(str(wav))
            dur = len(audio) / 16000
            meta["duration"] = dur
            meta["unit_times"] = [[float(s), float(min(s + UNIT, dur))] for s in np.arange(0, dur - 1, UNIT)]
            fj.write_text(json.dumps(meta))
        units = meta["unit_times"]
        npz = sig_dir / f"{m}.npz"
        arrays = dict(np.load(npz)) if npz.exists() else {}
        if "voice" in args.stages and "voice" not in arrays:
            arrays["voice"] = voice_features(load_audio(str(wav)), units)
        if "asr" in args.stages and "asr_text" not in meta:
            from faster_whisper import WhisperModel
            wm = WhisperModel("large-v3", device="cuda", compute_type="float16")
            segs, _ = wm.transcribe(str(wav), language="en", vad_filter=True)
            segs = [(s.start, s.end, s.text.strip()) for s in segs]
            meta["asr_text"] = [" ".join(t for a, b, t in segs if a < u1 and b > u0) for u0, u1 in units]
            fj.write_text(json.dumps(meta))
            del wm
        if "visual" in args.stages and "visual" not in arrays:
            from PIL import Image
            from transformers import AutoModel, AutoProcessor
            proc = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
            sm = AutoModel.from_pretrained("google/siglip-base-patch16-224").to("cuda").eval()
            vecs = []
            for k, (u0, u1) in enumerate(units):
                f = frame_at(vid, (u0 + u1) / 2, fr_dir / f"{m}_{k:04d}.jpg")
                if f is None:
                    vecs.append(np.zeros(768, np.float32))
                    continue
                with torch.inference_mode():
                    o = sm.get_image_features(**proc(images=[Image.open(f).convert("RGB")],
                                                     return_tensors="pt").to("cuda"))
                    o = (o.pooler_output if hasattr(o, "pooler_output") else o[0]).float().cpu().numpy()[0]
                vecs.append(o)
            arrays["visual"] = np.stack(vecs).astype(np.float32)
        if arrays:
            np.savez_compressed(npz, **arrays)
        if "vjudge" in args.stages:
            fv = vj_dir / f"{m}.summaries.json"
            sums = json.loads(fv.read_text()) if fv.exists() else []
            if len(sums) < len(units):
                from PIL import Image
                from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
                mid, rev = "Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5"
                vp = AutoProcessor.from_pretrained(mid, revision=rev)
                vm = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                    mid, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()
                for k in range(len(sums), len(units)):
                    u0, u1 = units[k]
                    fs = [frame_at(vid, u0 + (u1 - u0) * q, fr_dir / f"{m}_{k:04d}_{int(q * 10)}.jpg")
                          for q in (0.15, 0.5, 0.85)]
                    imgs = [Image.open(f).convert("RGB").resize((448, 252)) for f in fs if f]
                    text = PROMPT.format(n=len(imgs), speech=(meta.get("asr_text", [""] * len(units))[k] or "(silence)")[:500])
                    content = [{"type": "image", "image": im} for im in imgs] + [{"type": "text", "text": text}]
                    chat = vp.apply_chat_template([{"role": "user", "content": content}], tokenize=False,
                                                  add_generation_prompt=True)
                    inp = vp(text=[chat], images=imgs or None, padding=True, return_tensors="pt").to(vm.device)
                    with torch.inference_mode():
                        g = vm.generate(**inp, max_new_tokens=60, do_sample=False)
                    summ = vp.batch_decode(g[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0].strip()
                    sums.append({"unit": k, "lo": k, "hi": k + 1, "summary": summ})
                    if len(sums) % 25 == 0:
                        fv.write_text(json.dumps(sums, ensure_ascii=False))
                fv.write_text(json.dumps(sums, ensure_ascii=False))
                del vm
        print(f"[ami-signals] {m}: {len(units)} unidades", flush=True)
    print("[ami-signals] listo", flush=True)


if __name__ == "__main__":
    main()
