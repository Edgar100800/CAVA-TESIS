"""EXP-012 (GPU): story ledger — el VJudge juzga cada corte contra la historia previa.

EXP-011 paso 2-R: con contexto local (±2 shots) el VJudge no añade señal de trama
sobre SegLoop. Aquí el juez ve MINUTOS de historia, comprimidos en texto:

  etapa 1  unidades = tramos entre los top-100 cortes candidatos de SegLoop (los
           mismos del paso 2). Qwen2.5-VL resume cada unidad en una frase
           (quién, dónde, qué pasa) desde 3 keyframes + su diálogo.
  etapa 2  solo texto: para cada corte, "historia hasta aquí" = resúmenes de las
           `ctx` unidades previas, "siguiente" = resumen de la unidad posterior.
           ¿Sigue el mismo evento de trama (A) o empieza otro (B)? p_new = softmax
           de los logits A/B. ctx ∈ {1, 3}: la ablación que aísla el contexto largo.

Salida (resumible): <out>/<tt>.summaries.json  [{unit, lo, hi, summary}]
                    <out>/<tt>.ledger.json     [{cut, seg_score, p_new_ctx1, p_new_ctx3}]
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np

from narrative_interpreter import parse_srt
from vjudge_relational import MN, candidates, keyframe

SUMMARY_PROMPT = (
    "These {n} frames come from one continuous stretch of a film.\n"
    "Dialogue: \"{dialogue}\"\n\n"
    "In ONE sentence, say what happens here: who is involved, where, and what "
    "event takes place. Plain text, no preamble."
)
LEDGER_PROMPT = (
    "Here is a film's story, one line per consecutive stretch.\n"
    "Story so far:\n{story}\n\nNext stretch: {nxt}\n\n"
    "Does the next stretch continue the same plot event as the story so far, "
    "or does the story move to a new plot event (new situation, time jump, or "
    "another storyline)?\n"
    "Answer with one letter: A = same plot event continues, B = new plot event."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films", nargs="*", default=None)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--voters", default="data/movienet_voters")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--ctx", type=int, nargs="+", default=[1, 3])
    ap.add_argument("--out", default="data/vjudge_ledger")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    corpus, vdir, out = Path(args.corpus), Path(args.voters), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    films = args.films or sorted(f.stem for f in vdir.glob("*.npz"))

    if not args.dry_run:
        import torch
        from PIL import Image
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
        mid, rev = "Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5"
        processor = AutoProcessor.from_pretrained(mid, revision=rev)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            mid, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()
        ids = [processor.tokenizer.encode(x, add_special_tokens=False) for x in ("A", "B")]
        assert all(len(i) == 1 for i in ids), ids
        ids = [i[0] for i in ids]

        def run(content, imgs, gen_tokens=0):
            chat = processor.apply_chat_template([{"role": "user", "content": content}],
                                                 tokenize=False, add_generation_prompt=True)
            inputs = processor(text=[chat], images=imgs or None, padding=True,
                               return_tensors="pt").to(model.device)
            with torch.inference_mode():
                if gen_tokens:
                    g = model.generate(**inputs, max_new_tokens=gen_tokens, do_sample=False)
                    return processor.batch_decode(g[:, inputs.input_ids.shape[1]:],
                                                  skip_special_tokens=True)[0].strip()
                logits = model(**inputs).logits[0, -1, ids].float()
            return float(torch.softmax(logits, dim=0)[1])

    for tt in films:
        c = json.loads((corpus / f"{tt}.json").read_text())
        n, st = c["n_shots"], c["shot_times"]
        seg = np.asarray(np.load(vdir / f"{tt}.npz")["segloop"][:n - 1], np.float32)
        cands = candidates(seg, args.top)
        bounds = [0] + cands + [n]
        cues = parse_srt(MN / "subtitle" / f"{tt}.srt")

        # etapa 1: un resumen por unidad
        f_sum = out / f"{tt}.summaries.json"
        sums = json.loads(f_sum.read_text()) if f_sum.exists() else []
        for u in range(len(sums), len(bounds) - 1):
            lo, hi = bounds[u], bounds[u + 1]
            shots = sorted({min(lo + int((hi - lo) * f), hi - 1) for f in (0.15, 0.5, 0.85)})
            kfs = [p for p in (keyframe(tt, s) for s in shots) if p]
            t0, t1 = st[lo][0], st[hi - 1][1]
            dia = " ".join(x for a, b, x in cues if a < t1 and b > t0)[:500]
            text = SUMMARY_PROMPT.format(n=len(kfs), dialogue=dia or "(none)")
            if args.dry_run:
                summary = f"[dry {len(kfs)} frames, {len(dia)} chars]"
            else:
                imgs = [Image.open(p).convert("RGB").resize((448, 252)) for p in kfs]
                content = [{"type": "image", "image": im} for im in imgs]
                content.append({"type": "text", "text": text})
                summary = run(content, imgs, gen_tokens=60)
            sums.append({"unit": u, "lo": lo, "hi": hi, "summary": summary})
            if len(sums) % 20 == 0:
                f_sum.write_text(json.dumps(sums, ensure_ascii=False))
        f_sum.write_text(json.dumps(sums, ensure_ascii=False))

        # etapa 2: juicio de cada corte contra la historia previa (solo texto)
        f_led = out / f"{tt}.ledger.json"
        led = json.loads(f_led.read_text()) if f_led.exists() else []
        for i, cut in enumerate(cands[len(led):], start=len(led)):
            row = {"cut": cut, "seg_score": float(seg[cut - 1])}
            for k in args.ctx:
                story = "\n".join(f"- {s['summary']}" for s in sums[max(0, i + 1 - k):i + 1])
                text = LEDGER_PROMPT.format(story=story, nxt=sums[i + 1]["summary"])
                row[f"p_new_ctx{k}"] = None if args.dry_run else run(
                    [{"type": "text", "text": text}], [])
            led.append(row)
            if len(led) % 25 == 0:
                f_led.write_text(json.dumps(led))
        f_led.write_text(json.dumps(led))
        print(f"[ledger] {tt}: {len(sums)} unidades, {len(led)} cortes", flush=True)
    print("[ledger] listo", flush=True)


if __name__ == "__main__":
    main()
