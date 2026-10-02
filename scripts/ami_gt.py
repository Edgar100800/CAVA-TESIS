"""GT de AMI por reunión (EXP-020, solo evaluación): quién habla cuándo y tópicos.

Fuentes (AMI manual annotations 1.6.2, CC BY 4.0):
  segments/<m>.<X>.segments.xml  turnos por participante X (inicio/fin)
  words/<m>.<X>.words.xml        palabras con tiempos (para ubicar tópicos)
  topics/<m>.topic.xml           tópicos de primer nivel; tipo = ontología de
                                 tópicos de escenario, o la descripción libre
                                 si el tipo es "other" (top.4)
Salida: data/ami/gt/<m>.json
  {"duration", "speech": [[speaker, t0, t1]], "topics": [{"label", "t0", "t1"}]}
Dos tópicos con la misma etiqueta = mismo tópico (puede retornar).
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

A = Path("data/ami/annotations")
NITE = "{http://nite.sourceforge.net/}"
HREF = re.compile(r"([\w.]+)\.words\.xml#id\(([\w.]+)\)(?:\.\.id\(([\w.]+)\))?")


def ontology():
    root = ET.parse(A / "ontologies" / "default-topics.xml").getroot()
    return {e.get(NITE + "id"): e.get("name") for e in root.iter() if e.get("name")}


def word_times(meeting):
    times = {}
    for f in (A / "words").glob(f"{meeting}.*.words.xml"):
        for w in ET.parse(f).getroot():
            if w.get("starttime") and w.get("endtime"):
                times[w.get(NITE + "id")] = (float(w.get("starttime")), float(w.get("endtime")))
    return times


def ids_in_range(a, b):
    pa, na = a.rsplit("words", 1)
    pb, nb = b.rsplit("words", 1)
    return [f"{pa}words{k}" for k in range(int(na), int(nb) + 1)] if pa == pb else [a, b]


def main(meetings):
    onto = ontology()
    out = Path("data/ami/gt")
    out.mkdir(parents=True, exist_ok=True)
    for m in meetings:
        wt = word_times(m)
        speech = []
        for f in sorted((A / "segments").glob(f"{m}.*.segments.xml")):
            spk = f.name.split(".")[1]
            for s in ET.parse(f).getroot():
                if s.get("transcriber_start"):
                    speech.append([spk, float(s.get("transcriber_start")), float(s.get("transcriber_end"))])
        topics = []
        ft = A / "topics" / f"{m}.topic.xml"
        for t in ET.parse(ft).getroot().findall("topic"):
            tid = None
            for ptr in t.iter(NITE + "pointer"):
                mm = re.search(r"id\(([\w.]+)\)", ptr.get("href", ""))
                if mm:
                    tid = mm.group(1)
                    break
            label = onto.get(tid, "other") if tid else None
            if not label or tid == "top.4" or label == "other":
                desc = (t.get("description") or "").strip().lower()
                other = (t.get("other_description") or "").strip().lower()
                # algunas reuniones guardan el tipo en `description` en vez del puntero
                label = desc if desc and desc != "other" else ("other: " + other if other else "other")
            ts = []
            for ch in t.iter(NITE + "child"):
                h = HREF.search(ch.get("href", ""))
                if h:
                    for wid in ids_in_range(h.group(2), h.group(3) or h.group(2)):
                        if wid in wt:
                            ts.append(wt[wid])
            if ts:
                topics.append({"label": label, "t0": min(a for a, _ in ts), "t1": max(b for _, b in ts)})
        topics.sort(key=lambda x: x["t0"])
        dur = max([b for _, _, b in speech] + [t["t1"] for t in topics] + [0.0])
        (out / f"{m}.json").write_text(json.dumps({"meeting": m, "duration": dur, "speech": speech,
                                                   "topics": topics}, indent=1))
        rec = len(topics) - len({t["label"] for t in topics})
        print(f"[ami-gt] {m}: {dur / 60:.1f} min, hablantes {len({s[0] for s in speech})}, "
              f"tópicos {len(topics)} ({rec} retornos)", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]).read_text().split())
