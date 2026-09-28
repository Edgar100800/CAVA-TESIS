"""EXP-011 paso 2 (GPU): VJudge relacional en los cortes candidatos de SegLoop.

El VJudge no describe segmentos (EXP-010): COMPARA el antes y el después de un
corte y responde si sigue el mismo evento de trama o la historia pasa a otro.
La respuesta se lee como probabilidad de los logits de "A" (misma trama) y "B"
(nueva), no como texto generado.

Candidatos por película: los `--top` cortes de mayor score SegLoop (con
separación ≥ 2 shots). Contexto por candidato c (pre-registrado):
  frames  keyframe central de los shots c-6, c-1 | c, c+5
  texto   subtítulos de los 45 s antes y los 45 s después del corte
Condiciones: mm (frames + texto) y frames (solo frames).

Salida (resumible): <out>/<tt>.<cond>.json
  [{cut, seg_score, p_new}]   cut en convención 1..n-1 (inicio del shot nuevo)
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

from narrative_interpreter import parse_srt

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")

PROMPT_MM = (
    "The first {nb} images come BEFORE a cut in a film; the last {na} come AFTER it.\n"
    "Dialogue before the cut: \"{tb}\"\nDialogue after the cut: \"{ta}\"\n\n"
    "Does the same plot event continue across the cut (same situation, even if "
    "the camera or place changes a little), or does the story move to a different "
    "plot event (new situation, time jump, or other storyline)?\n"
    "Answer with one letter: A = same plot event continues, B = story moves to a new plot event."
)
PROMPT_FRAMES = (
    "The first {nb} images come BEFORE a cut in a film; the last {na} come AFTER it.\n\n"
    "Does the same plot event continue across the cut (same situation, even if "
    "the camera or place changes a little), or does the story move to a different "
    "plot event (new situation, time jump, or other storyline)?\n"
    "Answer with one letter: A = same plot event continues, B = story moves to a new plot event."
)


def candidates(seg, top, min_gap=2):
    chosen = []
    for i in np.argsort(-seg):
        c = int(i) + 1
        if all(abs(c - x) >= min_gap for x in chosen):
            chosen.append(c)
        if len(chosen) >= top:
            break
    return sorted(chosen)


def keyframe(tt, shot):
    for j in (1, 0, 2):
        p = MN / "240P_frames" / tt / f"shot_{shot:04d}_img_{j}.jpg"
        if p.exists():
            return p
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films", nargs="*", default=None, help="por defecto: todos con voters")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--voters", default="data/movienet_voters")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--conditions", nargs="+", default=["mm", "frames"], choices=["mm", "frames"])
    ap.add_argument("--out", default="data/vjudge_relational")
    ap.add_argument("--dry-run", action="store_true", help="solo prepara entradas, sin modelo")
    args = ap.parse_args()

    corpus, vdir, out = Path(args.corpus), Path(args.voters), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    films = args.films or sorted(f.stem for f in vdir.glob("*.npz"))

    processor = model = ids = None
    if not args.dry_run:
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
        mid, rev = "Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5"
        processor = AutoProcessor.from_pretrained(mid, revision=rev)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            mid, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()
        tok = processor.tokenizer
        ids = [tok.encode(x, add_special_tokens=False) for x in ("A", "B")]
        assert all(len(i) == 1 for i in ids), ids
        ids = [i[0] for i in ids]
    from PIL import Image

    for cond in args.conditions:
        for tt in films:
            f_out = out / f"{tt}.{cond}.json"
            c = json.loads((corpus / f"{tt}.json").read_text())
            n, st = c["n_shots"], c["shot_times"]
            seg = np.asarray(np.load(vdir / f"{tt}.npz")["segloop"][:n - 1], np.float32)
            cands = candidates(seg, args.top)
            done = json.loads(f_out.read_text()) if f_out.exists() else []
            if len(done) >= len(cands):
                continue
            cues = parse_srt(MN / "subtitle" / f"{tt}.srt")
            for cut in cands[len(done):]:
                before = [s for s in (cut - 6, cut - 1) if 0 <= s < n]
                after = [s for s in (cut, cut + 5) if 0 <= s < n]
                kb = [p for p in (keyframe(tt, s) for s in before) if p]
                ka = [p for p in (keyframe(tt, s) for s in after) if p]
                t = st[cut][0]
                tb = " ".join(x for a, b, x in cues if b > t - 45 and a < t)[-400:]
                ta = " ".join(x for a, b, x in cues if a >= t and a < t + 45)[:400]
                tmpl = PROMPT_MM if cond == "mm" else PROMPT_FRAMES
                text = tmpl.format(nb=len(kb), na=len(ka), tb=tb or "(none)", ta=ta or "(none)")
                if args.dry_run:
                    done.append({"cut": cut, "seg_score": float(seg[cut - 1]), "p_new": None,
                                 "n_frames": len(kb) + len(ka), "prompt_chars": len(text)})
                    continue
                import torch
                imgs = [Image.open(p).convert("RGB").resize((448, 252)) for p in kb + ka]
                content = [{"type": "image", "image": im} for im in imgs]
                content.append({"type": "text", "text": text})
                chat = processor.apply_chat_template([{"role": "user", "content": content}],
                                                     tokenize=False, add_generation_prompt=True)
                inputs = processor(text=[chat], images=imgs, padding=True,
                                   return_tensors="pt").to(model.device)
                with torch.inference_mode():
                    logits = model(**inputs).logits[0, -1, ids].float()
                p_new = float(torch.softmax(logits, dim=0)[1])
                done.append({"cut": cut, "seg_score": float(seg[cut - 1]), "p_new": p_new})
                if len(done) % 25 == 0 or len(done) == len(cands):
                    f_out.write_text(json.dumps(done))
            f_out.write_text(json.dumps(done))
            print(f"[relational] {tt}/{cond}: {len(done)} candidatos", flush=True)
    print("[relational] listo", flush=True)


if __name__ == "__main__":
    main()
