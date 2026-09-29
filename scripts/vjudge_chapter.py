"""EXP-013 (GPU, solo texto): el VJudge capitula el ledger como una sinopsis.

EXP-012: el juicio absoluto "¿mismo o nuevo evento?" por corte satura (p_new
mediana 0.97) porque dos resúmenes consecutivos siempre difieren. Aquí la
decisión es RELATIVA: el modelo lee `--window` resúmenes consecutivos (~30 min)
y marca qué tramos empezarían un párrafo nuevo de una sinopsis. Ventanas
solapadas (paso `--stride`); score de cada corte = fracción de ventanas que lo
contienen (no como primer tramo) y lo marcan.

Reutiliza los resúmenes de EXP-012 (`data/vjudge_ledger/<tt>.summaries.json`).
Salida (resumible): <out>/<tt>.chapter.json
  {"windows": [{"start", "marked": [unit...], "raw"}],
   "cuts": [{"cut", "seg_score", "votes", "covered", "score"}]}
"""
import argparse
import json
import os
import re
from pathlib import Path

import numpy as np

PROMPT = (
    "Below are consecutive stretches of a film, in order, one line each.\n\n{lines}\n\n"
    "A synopsis of this film would group these stretches into a few paragraphs, each "
    "paragraph covering one plot development (a situation that begins, unfolds and "
    "ends). Most paragraphs span several stretches.\n"
    "List the numbers of the stretches that START a new paragraph (do not list 1). "
    "Answer only with the numbers, comma-separated."
)


def windows(n_units, size, stride):
    starts = list(range(0, max(1, n_units - size + 1), stride))
    if starts[-1] + size < n_units:
        starts.append(n_units - size)
    return starts


def parse(raw, size):
    return sorted({int(x) for x in re.findall(r"\d+", raw) if 2 <= int(x) <= size})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films", nargs="*", default=None)
    ap.add_argument("--ledger", default="data/vjudge_ledger")
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--out", default="data/vjudge_chapter")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    led_dir, out = Path(args.ledger), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    films = args.films or sorted(f.name.split(".")[0] for f in led_dir.glob("*.summaries.json"))

    if not args.dry_run:
        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
        mid, rev = "Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5"
        processor = AutoProcessor.from_pretrained(mid, revision=rev)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            mid, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()

    for tt in films:
        f_out = out / f"{tt}.chapter.json"
        if f_out.exists():
            continue
        sums = json.loads((led_dir / f"{tt}.summaries.json").read_text())
        led = json.loads((led_dir / f"{tt}.ledger.json").read_text())
        n_units = len(sums)
        size = min(args.window, n_units)
        wins = []
        for s0 in windows(n_units, size, args.stride):
            lines = "\n".join(f"{i + 1}. {sums[s0 + i]['summary']}" for i in range(size))
            text = PROMPT.format(lines=lines)
            if args.dry_run:
                raw = f"[dry {len(text)} chars]"
            else:
                chat = processor.apply_chat_template(
                    [{"role": "user", "content": [{"type": "text", "text": text}]}],
                    tokenize=False, add_generation_prompt=True)
                inputs = processor(text=[chat], return_tensors="pt").to(model.device)
                with torch.inference_mode():
                    g = model.generate(**inputs, max_new_tokens=80, do_sample=False)
                raw = processor.batch_decode(g[:, inputs.input_ids.shape[1]:],
                                             skip_special_tokens=True)[0].strip()
            wins.append({"start": s0, "marked": [s0 + k - 1 for k in parse(raw, size)],
                         "raw": raw})
        # corte led[i] separa la unidad i de la i+1 -> "empieza la unidad i+1"
        votes = np.zeros(n_units, int)
        cover = np.zeros(n_units, int)
        for w in wins:
            cover[w["start"] + 1:w["start"] + size] += 1
            for u in w["marked"]:
                votes[u] += 1
        cuts = []
        for i, r in enumerate(led):
            u = i + 1
            cuts.append({"cut": r["cut"], "seg_score": r["seg_score"], "votes": int(votes[u]),
                         "covered": int(cover[u]),
                         "score": float(votes[u] / cover[u]) if cover[u] else None})
        f_out.write_text(json.dumps({"window": size, "stride": args.stride,
                                     "windows": wins, "cuts": cuts}, ensure_ascii=False))
        print(f"[chapter] {tt}: {len(wins)} ventanas, {int((votes > 0).sum())} tramos marcados",
              flush=True)
    print("[chapter] listo", flush=True)


if __name__ == "__main__":
    main()
