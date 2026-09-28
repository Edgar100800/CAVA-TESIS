"""Narrative Interpreter (EXP-010): VJudge como intérprete narrativo por segmento.

El VJudge (Qwen2.5-VL-7B frozen) lee un SEGMENTO de ~5 shots y describe el
momento narrativo. Este script SOLO genera las lecturas (parte GPU); la
agregación y la evaluación viven en `narrative_eval.py` (CPU).

Condiciones (ablation del intérprete, mismo prompt base):
  mm      keyframes + transcript juntos (el intérprete integrado)
  frames  solo keyframes
  text    solo transcript (sin imágenes)

La hipótesis de EXP-010 es que `mm` supera a `frames` y `text`. Si no lo hace,
la integración dentro del VJudge no aporta nada.

Salida (resumible; se guarda cada 20 segmentos):
  <out>/<tt>.meta.json          shots, fps, gt_scene_cuts (índice de shot)
  <out>/<tt>.<cond>.json        [{seg_idx, shot_start, shot_end, t0, t1,
                                  has_transcript, description}]
"""
import argparse
import json
import os
import re
from pathlib import Path

PROMPT_HEAD = {
    "mm": ("You are given {n} keyframes and the dialogue transcript from ONE "
           "segment of a film.\nTranscript: \"{transcript}\"\n\n"),
    "frames": "You are given {n} keyframes from ONE segment of a film.\n\n",
    "text": ("You are given the dialogue transcript from ONE segment of a film."
             "\nTranscript: \"{transcript}\"\n\n"),
}
PROMPT_TAIL = (
    "Describe the narrative moment this segment captures. Answer exactly:\n"
    "TOPIC: <what the scene is about, at most 12 words>\n"
    "FUNCTION: <setup | development | climax | resolution | transition>\n"
    "SUMMARY: <1-2 sentences on what happens and who is involved>\n"
    "Focus on the story, not on camera or visual style."
)


def parse_srt(path):
    rx = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
    cues, s, e, txt = [], None, None, []
    for line in Path(path).read_text(errors="ignore").splitlines():
        m = rx.search(line)
        if m:
            g = [int(x) for x in m.groups()]
            if txt and s is not None:
                cues.append((s, e, " ".join(txt)))
            s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            txt = []
        elif line.strip() and not line.strip().isdigit() and s is not None:
            txt.append(line.strip())
    if txt and s is not None:
        cues.append((s, e, " ".join(txt)))
    return cues


def build_segments(tt, seg_root, frames_root, anno, info, seg_shots):
    shot_f = seg_root / "scene318" / "shot_movie318" / f"{tt}.txt"
    srt_f = seg_root / "subtitle" / f"{tt}.srt"
    rows = anno.get(tt)
    if not shot_f.exists() or not srt_f.exists() or not rows:
        return None, None
    rows = sorted(rows, key=lambda r: int(r["shot_id"]))
    shots = [[int(x) for x in l.split()[:2]]
             for l in shot_f.read_text().splitlines() if l.strip()]
    n = min(len(shots), len(rows))
    fps = float(info.get(tt, {}).get("fps", 25.0))
    gt_cuts = [k for k in range(1, n)
               if int(rows[k]["invideo_scene_id"]) > int(rows[k - 1]["invideo_scene_id"])]
    cues = parse_srt(srt_f)

    segments = []
    for ss in range(0, n, seg_shots):
        es = min(ss + seg_shots, n)
        t0, t1 = shots[ss][0] / fps, (shots[es - 1][1] + 1) / fps
        kfs = []
        for si in sorted({min(ss + int((es - ss) * f), es - 1) for f in (0.1, 0.5, 0.9)}):
            for j in (1, 0, 2):  # img_1 = frame central del shot
                p = frames_root / tt / f"shot_{si:04d}_img_{j}.jpg"
                if p.exists():
                    kfs.append(str(p))
                    break
        trans = " ".join(tx for a, b, tx in cues if a < t1 and b > t0)
        segments.append({"seg_idx": len(segments), "shot_start": ss, "shot_end": es,
                         "t0": round(t0, 2), "t1": round(t1, 2),
                         "keyframes": kfs, "transcript": trans[:600]})
    meta = {"video_id": tt, "fps": fps, "n_shots": n, "seg_shots": seg_shots,
            "shot_times": [[round(a / fps, 2), round((b + 1) / fps, 2)]
                           for a, b in shots[:n]],
            "gt_scene_cuts": gt_cuts}
    return meta, segments


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--movies", nargs="+", required=True, help="tt_ids")
    ap.add_argument("--max-movies", type=int, default=3)
    ap.add_argument("--conditions", nargs="+", default=["mm", "frames", "text"],
                    choices=["mm", "frames", "text"])
    ap.add_argument("--seg-shots", type=int, default=5)
    ap.add_argument("--max-new-tokens", type=int, default=120)
    ap.add_argument("--seg-root", default="/home/edgar.chambilla/Tesis/SegLoop/data/movienet")
    ap.add_argument("--frames-root",
                    default="/home/edgar.chambilla/Tesis/SegLoop/data/movienet/240P_frames")
    ap.add_argument("--out", default="/home/edgar.chambilla/Tesis/CAVA/data/narrative_interpreter")
    args = ap.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
    model_id = "Qwen/Qwen2.5-VL-7B-Instruct"
    rev = "cc594898137f460bfe9f0759e9844b3ce807cfb5"
    processor = AutoProcessor.from_pretrained(model_id, revision=rev)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()

    seg_root, frames_root = Path(args.seg_root), Path(args.frames_root)
    info = json.load(open(seg_root / "official" / "video_info.json"))
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    anno = {}
    for f in ("anno.train.ndjson", "anno.val.ndjson", "anno.test.ndjson"):
        for line in open(seg_root / "anno" / f):
            r = json.loads(line)
            anno.setdefault(r["video_id"], []).append(r)

    movies = args.movies[: args.max_movies]
    prepared = {}
    for tt in movies:
        meta, segments = build_segments(tt, seg_root, frames_root, anno, info, args.seg_shots)
        if meta is None:
            print(f"[skip] {tt}: sin insumos", flush=True)
            continue
        (out_root / f"{tt}.meta.json").write_text(json.dumps(meta))
        prepared[tt] = segments
        print(f"[narrative] {tt}: {meta['n_shots']} shots -> {len(segments)} segmentos, "
              f"{len(meta['gt_scene_cuts'])} cortes GT", flush=True)

    def generate(content):
        messages = [{"role": "user", "content": content}]
        text_input = processor.apply_chat_template(messages, tokenize=False,
                                                   add_generation_prompt=True)
        imgs = [c["image"] for c in content if c["type"] == "image"]
        inputs = processor(text=[text_input], images=imgs or None, padding=True,
                           return_tensors="pt").to(model.device)
        with torch.inference_mode():
            gen = model.generate(**inputs, max_new_tokens=args.max_new_tokens,
                                 do_sample=False)
        gen = gen[:, inputs.input_ids.shape[1]:]
        return processor.batch_decode(gen, skip_special_tokens=True)[0].strip()

    # condición externa: `mm` termina para todas las películas antes que las ablaciones
    for cond in args.conditions:
        for tt, segments in prepared.items():
            out_f = out_root / f"{tt}.{cond}.json"
            done = json.loads(out_f.read_text()) if out_f.exists() else []
            if len(done) >= len(segments):
                print(f"[narrative] {tt}/{cond}: completo, salto", flush=True)
                continue
            for seg in segments[len(done):]:
                trans = seg["transcript"].strip()
                has_t = bool(trans)
                if cond == "text" and not has_t:
                    desc = ""  # sin señal: el eval lo trata como vacío
                else:
                    head_key = "frames" if (cond == "frames" or not has_t) else cond
                    content = []
                    if cond != "text":
                        content = [{"type": "image",
                                    "image": Image.open(p).convert("RGB").resize((448, 252))}
                                   for p in seg["keyframes"]]
                    head = PROMPT_HEAD[head_key].format(n=len(content), transcript=trans[:400])
                    content.append({"type": "text", "text": head + PROMPT_TAIL})
                    desc = generate(content)
                done.append({k: seg[k] for k in ("seg_idx", "shot_start", "shot_end",
                                                  "t0", "t1")}
                            | {"has_transcript": has_t, "description": desc})
                if len(done) % 20 == 0 or len(done) == len(segments):
                    out_f.write_text(json.dumps(done, ensure_ascii=False, indent=1))
                    print(f"[narrative] {tt}/{cond}: {len(done)}/{len(segments)}", flush=True)
    print("[narrative] listo", flush=True)


if __name__ == "__main__":
    main()
