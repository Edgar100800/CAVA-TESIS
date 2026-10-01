"""Etiqueta de nivel tópico (EXP-019b): un modelo de texto frozen lee TODOS los
tramos del tópico (qué vio el VJudge + qué se dice, del `context` del mapa) y
escribe "CHARACTERS: … | TOPIC: …". Solo señales propias de CAVA, sin GT.

Tópicos del nivel default con duración ≥ --min-dur s (los que certifica
EXP-019). Si un tópico tiene más de --max-spans tramos, se usan los más largos
en orden temporal.
Salida (resumible): <out>/<tt>.topic_labels.json {topic_id: label}
"""
import argparse
import json
import os
from pathlib import Path

PROMPT = (
    "Below is what an automatic system observed in ONE topic of a film: the stretches "
    "where this topic appears, in time order. For each stretch: what was seen on screen "
    "and the dialogue spoken.\n\n{stretches}\n\n"
    "Write ONE line in exactly this format:\n"
    "CHARACTERS: <the people involved; use names heard in the dialogue when possible, "
    "otherwise short descriptions> | TOPIC: <what this topic is about, at most 15 words>"
)


def stretches_text(t, max_spans):
    idx = sorted(range(len(t["spans"])), key=lambda i: -(t["spans"][i][1] - t["spans"][i][0]))[:max_spans]
    out = []
    for n, i in enumerate(sorted(idx), 1):
        a, b = t["spans"][i]
        ctx = t["context"][i]
        seen = " ".join(ctx["seen"])[:400] or "(nothing described)"
        said = ctx["said"][:300] or "(no dialogue)"
        out.append(f"Stretch {n} ({a / 60:.1f}-{b / 60:.1f} min): Seen: {seen} Said: \"{said}\"")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", nargs="+", required=True)
    ap.add_argument("--out", default="data/topic_labels")
    ap.add_argument("--min-dur", type=float, default=30.0)
    ap.add_argument("--max-spans", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
        mid, rev = "Qwen/Qwen2.5-14B-Instruct", "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"
        tok = AutoTokenizer.from_pretrained(mid, revision=rev)
        model = AutoModelForCausalLM.from_pretrained(mid, revision=rev, torch_dtype=torch.bfloat16,
                                                     device_map="cuda").eval()
    files = [f for d in args.maps for f in sorted(Path(d).glob("*.topic_map.json"))]
    for f in files:
        doc = json.loads(f.read_text())
        tt = doc["video_id"]
        f_out = out / f"{tt}.topic_labels.json"
        done = json.loads(f_out.read_text()) if f_out.exists() else {}
        todo = [t for t in doc["levels"]["default"]["topics"]
                if t["duration_s"] >= args.min_dur and str(t["topic_id"]) not in done]
        for t in todo:
            text = PROMPT.format(stretches=stretches_text(t, args.max_spans))
            if args.dry_run:
                label = f"[dry {len(text)} chars]"
            else:
                chat = tok.apply_chat_template([{"role": "user", "content": text}],
                                               tokenize=False, add_generation_prompt=True)
                inputs = tok([chat], return_tensors="pt").to(model.device)
                with torch.inference_mode():
                    g = model.generate(**inputs, max_new_tokens=70, do_sample=False)
                label = tok.decode(g[0, inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
            done[str(t["topic_id"])] = label.splitlines()[0] if label else ""
            if len(done) % 20 == 0:
                f_out.write_text(json.dumps(done, ensure_ascii=False))
        f_out.write_text(json.dumps(done, ensure_ascii=False))
        print(f"[topiclabels] {tt}: {len(done)} etiquetas", flush=True)
    print("[topiclabels] listo", flush=True)


if __name__ == "__main__":
    main()
