"""Etiqueta de nivel tópico (EXP-019b): prompt y limpieza de texto.

Antes vivía en scripts/vjudge_topic_labels.py; el pipeline lo importa desde aquí.
"""
import re

# subtítulos SDH: "RATCHED: ..." y "[INMATE COUGHS]" no existen en ASR de producción;
# se eliminan para que la etiqueta no reciba nombres que un video nuevo no daría
SDH_SPEAKER = re.compile(r"\b[A-Z][A-Z .'\-]{1,30}:\s*")
SDH_CUE = re.compile(r"[\[(][^\])]{0,60}[\])]")


_CJK = re.compile(r"[\u3000-\u9fff\uac00-\ud7af\uff00-\uffef]")


def clean_label(text):
    """La etiqueta se corta en el primer carácter CJK: Qwen a veces deriva de idioma a mitad de frase."""
    m = _CJK.search(text)
    return (text[:m.start()] if m else text).rstrip(" ,;:-")


def clean_said(text):
    return re.sub(r"\s+", " ", SDH_CUE.sub(" ", SDH_SPEAKER.sub(" ", text))).strip()

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
        said = clean_said(ctx["said"])[:300] or "(no dialogue)"
        out.append(f"Stretch {n} ({a / 60:.1f}-{b / 60:.1f} min): Seen: {seen} Said: \"{said}\"")
    return "\n".join(out)
