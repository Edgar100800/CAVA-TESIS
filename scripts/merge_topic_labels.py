"""Añade `topic_label` (EXP-019b) a cada tópico de los mapas; `label` se conserva."""
import json
from pathlib import Path

n = 0
for d in ("data/topic_maps", "data/topic_maps_test"):
    for f in sorted(Path(d).glob("*.topic_map.json")):
        doc = json.loads(f.read_text())
        fl = Path("data/topic_labels") / f"{doc['video_id']}.topic_labels.json"
        tl = json.loads(fl.read_text()) if fl.exists() else {}
        for t in doc["levels"]["default"]["topics"]:
            t["topic_label"] = tl.get(str(t["topic_id"]), t["label"])
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        n += 1
print(f"[merge] topic_label añadido en {n} mapas")
