"""Lista de películas del split test con señales extraídas y cast (EXP-018)."""
import json
from pathlib import Path

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")
test = {json.loads(l)["video_id"] for l in open(MN / "anno" / "anno.test.ndjson")}
ok = []
for tt in sorted(test):
    a = MN / "annotation" / f"{tt}.json"
    if not (Path("data/movienet_topics") / f"{tt}.npz").exists() or not a.exists():
        continue
    if any(c.get("pid") and c["pid"] != "others" for c in (json.loads(a.read_text()).get("cast") or [])):
        ok.append(tt)
Path("scripts/exp018_test_films.txt").write_text("\n".join(ok) + "\n")
print(f"[exp018] {len(ok)} películas test con señales y cast")
