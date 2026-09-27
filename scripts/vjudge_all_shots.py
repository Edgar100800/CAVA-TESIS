"""VJudge razonamiento por shot para los 3 videos TVSum del piloto CAVA.

Lee el manifest de shots, decodifica los keyframes del mp4, pasa al juez
frozen (Qwen2.5-VL) y produce razonamiento narrativo por shot:
  - qué pasa en el shot
  - qué momento narrativo representa

Salida: data/cava_pilot/<video>/vjudge_all_shots.json
Este razonamiento alimenta la agregación temática (embeddings de texto).
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")

REASONING_PROMPT = (
    "You are given {n} frames from ONE shot of a video. Describe briefly:\n"
    "1) What is happening (action, setting, characters).\n"
    "2) What narrative moment this represents (exposition, action, dialogue,"
    " transition, climax, conclusion, etc).\n"
    "Answer in 2 sentences, concrete."
)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/processing/segmenter/shots.ndjson")
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--out",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/cava_pilot")
    ap.add_argument("--batch-shots", type=int, default=30)
    ap.add_argument("--max-new-tokens", type=int, default=150)
    args = ap.parse_args()

    from PIL import Image
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration as AutoModelVL

    os.environ.setdefault("HF_HOME",
                          "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
    model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
    rev = "cc594898137f460bfe9f0759e9844b3ce807cfb5"
    processor = AutoProcessor.from_pretrained(model_id, revision=rev)
    model = AutoModelVL.from_pretrained(
        model_id, revision=rev, torch_dtype=torch.bfloat16,
        device_map="cuda").eval()

    # manifest: shots por video
    by_video = {}
    for line in open(args.manifest):
        r = json.loads(line)
        by_video.setdefault(r["video_id"], []).append(r)

    # videos a procesar
    target_ids = {Path(v).stem for v in args.videos}

    for vid in sorted(target_ids):
        shots = sorted(by_video.get(vid, []), key=lambda r: int(r["shot_id"]))
        if not shots:
            print(f"[skip] {vid}: sin shots", flush=True)
            continue
        video_path = shots[0]["video_path"]
        n = len(shots)
        out_file = Path(args.out) / vid / "vjudge_all_shots.json"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        if out_file.exists():
            existing = json.loads(out_file.read_text())
            done_ids = {s["shot_id"] for s in existing.get("shots", [])}
        else:
            existing = {"shots": []}
            done_ids = set()
        results = list(existing.get("shots", []))
        done = {s["shot_id"] for s in results}
        pending = [s for s in shots if s["shot_id"] not in done_ids]
        print(f"[vjudge] {vid}: {len(pending)}/{n} shots pendientes", flush=True)

        for si, shot in enumerate(pending):
            t0, t1 = shot["start_ts"], shot["end_ts"]
            span = max(0.5, t1 - t0)
            # keyframes desde el video
            f0 = int(t0 * meta_fps(shot["video_path"])) if "meta_fps" not in dir() else int(t0 * fps_v)
            idx = [int(t0 * meta_fps(shot["video_path"]) +
                       (int(meta_fps(shot["video_path"]) * span) *
                        (j + 0.5) / 3)) for j in range(3)]
            idx = [min(i, int(meta_fps(shot["video_path"]) * span) - 1)
                   for i in idx]

            imgs = []
            for fi in idx:
                if fi < 0:
                    continue
                # decodificar frame directamente del mp4
                import decord
                vr = decord.VideoReader(video_path)
                frame = vr[fi].asnumpy()
                imgs.append(Image.fromarray(frame).resize((448, 224)))
            if not imgs:
                continue

            prompt = REASONING_PROMPT.format(n=len(imgs))
            content = [{"type": "image", "image": img} for img in imgs]
            content.append({"type": "text", "text": prompt})
            messages = [{"role": "user", "content": content}]

            text_input = processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            images_for_proc = [c["image"] for c in content if c["type"] == "image"]
            inputs = processor(text=[text_input], images=images_for_proc,
                               padding=True, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                gen = model.generate(**inputs,
                                     max_new_tokens=args.max_new_tokens,
                                     do_sample=False)
            gen = gen[:, inputs.input_ids.shape[1]:]
            reasoning = processor.batch_decode(
                gen, skip_special_tokens=True)[0].strip()

            results.append({
                "shot_id": shot["shot_id"],
                "t0_s": round(t0, 2), "t1_s": round(t1, 2),
                "reasoning": reasoning,
            })

            if len(results) % 30 == 0 or len(results) == n:
                (out_file).write_text(json.dumps(
                    {"protocol": "vjudge_shot_reasoning_v1",
                     "video_id": vid, "n_shots": n, "shots": results},
                    indent=1, ensure_ascii=False))
            if (si + 1) % 10 == 0 or si + 1 == len(pending):
                print(f"[vjudge] {vid}: {len(results)}/{n} shots", flush=True)

        (out_file).write_text(json.dumps(
            {"protocol": "vjudge_shot_reasoning_v1",
             "video_id": vid, "n_shots": n, "shots": results},
            indent=1, ensure_ascii=False))
        print(f"[vjudge] DONE {vid}: {len(results)} shots", flush=True)


def meta_fps(video_path):
    from segloop.io import video_loader
    return float(video_loader.read_meta(video_path).fps)


if __name__ == "__main__":
    main()
