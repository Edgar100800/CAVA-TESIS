#!/usr/bin/env python3
"""Prepara 100 prompts de etiquetas reales, sin guardar respuestas del modelo."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SPEAKER = re.compile(r"\b[A-Z][A-Z .'-]{1,30}:\s*")
CUE = re.compile(r"[\[(][^\])]{0,60}[\])]")
PROMPT = (
    "Below is what an automatic system observed in ONE topic of a film: the stretches "
    "where this topic appears, in time order. For each stretch: what was seen on screen "
    "and the dialogue spoken.\n\n{stretches}\n\n"
    "Write ONE line in exactly this format:\n"
    "CHARACTERS: <the people involved; use names heard in the dialogue when possible, "
    "otherwise short descriptions> | TOPIC: <what this topic is about, at most 15 words>"
)


def prompt_for(topic: dict) -> str:
    spans = topic["spans"]
    context = topic["context"]
    selected = sorted(
        sorted(range(len(spans)), key=lambda i: -(spans[i][1] - spans[i][0]))[:8]
    )
    lines = []
    for number, index in enumerate(selected, 1):
        start, end = spans[index]
        ctx = context[index]
        seen = " ".join(ctx.get("seen", []))[:400] or "(nothing described)"
        said = CUE.sub(" ", SPEAKER.sub(" ", ctx.get("said", "")))
        said = re.sub(r"\s+", " ", said).strip()[:300] or "(no dialogue)"
        lines.append(
            f'Stretch {number} ({start / 60:.1f}-{end / 60:.1f} min): '
            f'Seen: {seen} Said: "{said}"'
        )
    return PROMPT.format(stretches="\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic-map", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--min-duration", type=float, default=30.0)
    args = parser.parse_args()

    doc = json.loads(args.topic_map.read_text())
    topics = [
        topic for topic in doc["levels"]["default"]["topics"]
        if topic.get("duration_s", 0) >= args.min_duration
    ]
    topics.sort(key=lambda topic: (topic.get("topic_id", 0), topic["spans"][0][0]))
    if not topics:
        raise SystemExit("El mapa no contiene tópicos que cumplan --min-duration")

    prompts = [prompt_for(topics[index % len(topics)]) for index in range(args.count)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as output:
        for prompt in prompts:
            output.write(json.dumps({"prompt": prompt}, ensure_ascii=False) + "\n")
    print(json.dumps({"prompts": len(prompts), "unique_topics": len(topics), "out": str(args.out)}))


if __name__ == "__main__":
    main()
