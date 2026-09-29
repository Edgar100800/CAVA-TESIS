"""EXP-013b (GPU, solo texto): capitulación por ítem con logits, sin enumerar listas.

EXP-013 falló por el instrumento: al pedir la lista de tramos que empiezan
párrafo, el modelo enumeró casi todos los números y 334/522 salidas se
truncaron. Aquí, por cada corte candidato, el modelo ve la MISMA ventana larga
(hasta 15 tramos antes y 14 después, numerados) y responde una sola pregunta:
¿el tramo #k empieza un párrafo nuevo de la sinopsis? p = softmax de los logits
A/B. La evaluación es por ranking dentro de la película, así que un sesgo
constante hacia "sí" no afecta.

Reutiliza los resúmenes de EXP-012. Salida (resumible): <out>/<tt>.chapterlogit.json
  [{cut, seg_score, p_start}]
"""
import argparse
import json
import os
from pathlib import Path

PROMPT = (
    "Below are consecutive stretches of a film, in order, one line each.\n\n{lines}\n\n"
    "A synopsis of this film would group these stretches into a few paragraphs, each "
    "paragraph covering one plot development (a situation that begins, unfolds and "
    "ends). Most paragraphs span several stretches.\n"
    "Does stretch {k} START a new paragraph, or does it continue the paragraph of "
    "stretch {km1}?\n"
    "Answer with one letter: A = continues the same paragraph, B = starts a new paragraph."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films", nargs="*", default=None)
    ap.add_argument("--ledger", default="data/vjudge_ledger")
    ap.add_argument("--before", type=int, default=15)
    ap.add_argument("--after", type=int, default=14)
    ap.add_argument("--out", default="data/vjudge_chapter_logit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", choices=["vl7b", "text14b"], default="vl7b",
                    help="EXP-014: razonador; mismo prompt e instrumento en ambos")
    args = ap.parse_args()

    led_dir, out = Path(args.ledger), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    films = args.films or sorted(f.name.split(".")[0] for f in led_dir.glob("*.summaries.json"))

    MODELS = {"vl7b": ("Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5"),
              "text14b": ("Qwen/Qwen2.5-14B-Instruct", "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8")}
    if not args.dry_run:
        import torch
        os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
        mid, rev = MODELS[args.model]
        if args.model == "vl7b":
            from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
            processor = AutoProcessor.from_pretrained(mid, revision=rev)
            tok = processor.tokenizer
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                mid, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()
        else:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(mid, revision=rev)
            model = AutoModelForCausalLM.from_pretrained(
                mid, revision=rev, torch_dtype=torch.bfloat16, device_map="cuda").eval()
        ids = [tok.encode(x, add_special_tokens=False) for x in ("A", "B")]
        assert all(len(i) == 1 for i in ids), ids
        ids = [i[0] for i in ids]

        def encode(text):
            if args.model == "vl7b":
                chat = processor.apply_chat_template(
                    [{"role": "user", "content": [{"type": "text", "text": text}]}],
                    tokenize=False, add_generation_prompt=True)
                return processor(text=[chat], return_tensors="pt").to(model.device)
            chat = tok.apply_chat_template([{"role": "user", "content": text}],
                                           tokenize=False, add_generation_prompt=True)
            return tok([chat], return_tensors="pt").to(model.device)

    for tt in films:
        f_out = out / f"{tt}.chapterlogit.json"
        sums = json.loads((led_dir / f"{tt}.summaries.json").read_text())
        led = json.loads((led_dir / f"{tt}.ledger.json").read_text())
        done = json.loads(f_out.read_text()) if f_out.exists() else []
        if len(done) >= len(led):
            continue
        for i, r in enumerate(led[len(done):], start=len(done)):
            u = i + 1                                  # el corte i empieza la unidad i+1
            lo, hi = max(0, u - args.before), min(len(sums), u + args.after + 1)
            lines = "\n".join(f"{j - lo + 1}. {sums[j]['summary']}" for j in range(lo, hi))
            k = u - lo + 1
            text = PROMPT.format(lines=lines, k=k, km1=k - 1)
            if args.dry_run:
                p = None
            else:
                inputs = encode(text)
                with torch.inference_mode():
                    logits = model(**inputs).logits[0, -1, ids].float()
                p = float(torch.softmax(logits, dim=0)[1])
            done.append({"cut": r["cut"], "seg_score": r["seg_score"], "p_start": p,
                         "k": k, "n_lines": hi - lo})
            if len(done) % 25 == 0:
                f_out.write_text(json.dumps(done))
        f_out.write_text(json.dumps(done))
        print(f"[chapterlogit] {tt}: {len(done)} cortes", flush=True)
    print("[chapterlogit] listo", flush=True)


if __name__ == "__main__":
    main()
