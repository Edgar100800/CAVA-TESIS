"""Escribe el campo estructurado `characters` (nombres + heredados + identidades P#)
en cada tópico de los mapas, sin tocar `label` ni `topic_label`."""
import json
import sys
from pathlib import Path

pairs = [("data/topic_maps", sys.argv[1]), ("data/topic_maps_test", sys.argv[1]),
         ("data/topic_maps_train", sys.argv[1]), ("data/topic_maps_train2", sys.argv[1])]
n = 0
for maps, cat in pairs:
    for f in sorted(Path(maps).glob("*.topic_map.json")):
        doc = json.loads(f.read_text())
        fc = Path(cat) / f"{doc['video_id']}.characters.json"
        if not fc.exists():
            continue
        ch = json.loads(fc.read_text())
        for t in doc["levels"]["default"]["topics"]:
            t["characters"] = ch.get(str(t["topic_id"]), {"names": [], "inherited_names": [], "identities": []})
        f.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        n += 1
print(f"[merge] characters en {n} mapas")
