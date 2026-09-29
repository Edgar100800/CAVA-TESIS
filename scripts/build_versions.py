"""Escribe las versiones por consumidor de cada mapa de tópicos + el gate G-versión.

Salida: data/versions/<tt>.versions.json ({profile: {budget_s, playlists}}) y
results/g_version_report.json (resumen por película).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.versions import build_versions, check_versions  # noqa: E402

out = Path("data/versions")
out.mkdir(parents=True, exist_ok=True)
report = {}
for f in sorted(Path("data/topic_maps").glob("*.topic_map.json")):
    doc = json.loads(f.read_text())
    v = build_versions(doc)
    (out / f"{doc['video_id']}.versions.json").write_text(json.dumps(v, indent=1, ensure_ascii=False))
    report[doc["video_id"]] = check_versions(v)
passed = sum(r["G_version"] for r in report.values())
Path("results/g_version_report.json").write_text(json.dumps(
    {"n_films": len(report), "passed": passed, "per_film": report}, indent=1))
print(f"[versions] G-versión {passed}/{len(report)} películas")
