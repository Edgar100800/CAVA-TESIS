"""VJudge sobre MovieNet keyframes: razonamiento semántico por shot.

Lee los keyframes pre-extraídos por shot (240P), los pasa al juez frozen
(Qwen2.5-VL) y produce por shot:
  - descripción de qué pasa
  - tópico narrativo sugerido

Este razonamiento alimenta la agregación temática: shots con descripciones
similares → mismo tópico. Es la señal que el ensemble frozen NO lleva
(frontera ≠ importancia, ρ≈0) y que el VJudge sí puede dar.

Resume-safe por movie. Salida: data/cava/mn_reasoning/<ttid>.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")

REASONING_PROMPT = (
    "These are {n} frames from ONE shot of a film. Describe briefly:\n"
    "1) What is happening (action, setting, characters).\n"
    "2) What narrative moment this represents (exposition, action, dialogue,"
    " transition, climax, etc).\n"
    "Answer in 2 sentences, concrete."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--movies", nargs="+", required=True, help="tt_ids")
    ap.add_argument("--frames-root",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/movienet/240P_frames")
    ap.add_argument("--shots-root",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/movienet/scene318/shot_movie318")
    ap.add_argument("--srt-root",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/movienet/subtitle")
    ap.add_argument("--info",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/movienet/official/video_info.json")
    ap.add_argument("--out",
                    default="/home/edgar.chambilla/Tesis/CAVA/data/mn_reasoning")
    ap.add_argument("--batch-shots", type=int, default=50)
    args = ap.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration as AutoModelVL

    os.environ.setdefault("HF_HOME",
                          "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
    model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
    revision = "cc594898137f460bfe9f0759e9844b3ce807cfb5"
    processor = AutoProcessor.from_pretrained(model_id, revision=revision)
    model = AutoModelVL.from_pretrained(
        model_id, revision=revision, torch_dtype=torch.bfloat16,
        device_map="cuda" if torch.cuda.is_available() else "cpu")
    model.eval()

    info = json.load(open(args.info))
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    for tt in args.movies:
        out_file = out_root / f"{tt}.json"
        if out_file.exists():
            print(f"[skip] {tt} ya procesado", flush=True)
            continue
        kf_dir = Path(args.frames_root) / tt
        shot_file = Path(args.shots_root) / f"{tt}.txt"
        srt_file = Path(args.srt_root) / f"{tt}.srt"
        if not all(x.exists() for x in (kf_dir, shot_file, srt_file)):
            print(f"[skip] {tt}: insumos faltantes", flush=True)
            continue

        fps = float(info.get(tt, {}).get("fps", 25.0))
        # shots: del shot_file (start_f, end_f, kf1, kf2, kf3)
        shots = [[int(x) for x in l.split()]
                 for l in shot_file.read_text().splitlines() if l.strip()]
        n = len(shots)

        # srt cues
        RE = __import__("re").compile(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
        cues, s, e, txt = [], None, None, []
        for line in srt_file.read_text(errors="ignore").splitlines():
            m = RE.search(line)
            if m:
                g = [int(x) for x in m.groups()]
                if txt and s is not None:
                    cues.append((s, e, " ".join(txt)))
                s = g[0]*3600+g[1]*60+g[2]+g[3]/1000
                e = g[4]*3600+g[5]*60+g[6]+g[7]/1000
                txt = []
            elif line.strip() and s is not None:
                txt.append(line.strip())
        if txt and s is not None:
            cues.append((s, e, " ".join(txt)))

        print(f"[vjudge-mn] {tt}: {n} shots, {len(cues)} cues, "
              f"dur={n/fps:.0f}s", flush=True)

        results = []
        for si in range(0, n, args.batch_shots):
            batch = shots[si:si + args.batch_shots]
            for k, shot in enumerate(batch):
                shot_idx = si + k
                t0 = shot[0] / fps
                t1 = (shot[1] + 1) / fps
                # keyframes del shot (hasta 3)
                imgs = []
                for j in range(3):
                    p = kf_dir / f"shot_{shot_idx:04d}_img_{j}.jpg"
                    if p.exists():
                        imgs.append(Image.open(p).convert("RGB").resize((448, 224)))
                if not imgs:
                    continue
                transcript = " ".join(
                    tx for a, b, tx in cues if a < t1 and b > t0)
                prompt = REASONING_PROMPT.format(n=len(imgs))
                if transcript:
                    prompt += f"\n\nTranscript in this shot: {transcript[:300]}"

                messages = [{
                    "role": "user",
                    "content": [{"type": "image"} for _ in imgs] +
                               [{"type": "text", "text": prompt}]
                }]
                text_input = processor.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=True)
                inputs = processor(
                    text=[text_input], images=imgs, return_tensors="pt"
                ).to(model.device)
                with torch.inference_mode():
                    gen = model.generate(
                        **inputs, max_new_tokens=180, do_sample=False)
                gen = gen[:, inputs.input_ids.shape[1]:]
                reasoning = processor.batch_decode(
                    gen, skip_special_tokens=True)[0].strip()

                results.append({
                    "shot_idx": shot_idx,
                    "t0_s": round(t0, 2), "t1_s": round(t1, 2),
                    "n_frames": len(imgs),
                    "reasoning": reasoning,
                    "transcript_snippet": transcript[:200] if transcript else "",
                })
            # guardar checkpoint del batch
            (out_root / f"{tt}.json").write_text(
                json.dumps({"protocol": "vjudge_movie_shot_reasoning",
                            "video_id": tt, "fps": fps, "n_shots": n,
                            "shots": results}, indent=1, ensure_ascii=False))
            print(f"[vjudge-mn] {tt}: {len(results)}/{n} shots", flush=True)

        print(f"[vjudge-mn] DONE {tt}: {len(results)} shots", flush=True)


if __name__ == "__main__":
    main()
