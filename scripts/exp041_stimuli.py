"""EXP-041-L — estímulos del A/B corto sobre la película (T y H, CAVA vs U).

Genera, desde la corrida congelada `data/films_runs/Spider_Man`:

- CAVA: capítulos (ya existen) + highlights de 240 s (presupuesto fijo del evento).
- U (sin estructura): mismo número de capítulos equiespaciados, mismas duraciones de
  highlights repartidas equiespaciadas, etiquetadas por el mismo modelo.
- `viewer.json` por sistema para la línea de tiempo (T) y miniaturas.
- `version_highlights240_0.mp4` por sistema (H).

No recalcula señales ni resúmenes: reutiliza `work/` de la corrida fuente.
"""
from __future__ import annotations

import argparse
import json
import os
os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from exp040_baselines import (base_u, label_topics, render, _source_state)  # noqa: E402
from topicagg.pipeline import PROFILES  # noqa: E402
from topicagg.versions import build_versions  # noqa: E402


def make_src_link(run: Path, tmp: Path, versions: dict) -> Path:
    """Directorio fuente mínimo para base_u (evita copiar clips/audio)."""
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "work").mkdir(exist_ok=True)
    for f in ("state.json", "summaries.json"):
        (tmp / "work" / f).write_bytes((run / "work" / f).read_bytes())
    (tmp / "topic_map.json").write_bytes((run / "topic_map.json").read_bytes())
    (tmp / "versions.json").write_text(json.dumps(versions, ensure_ascii=False, indent=1))
    return tmp


def thumb(video: Path, t: float, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(t,0):.2f}", "-i", str(video),
                        "-frames:v", "1", "-vf", "scale=192:-2", str(dst)], capture_output=True)
    return r.returncode == 0 and dst.exists()


def viewer(doc: dict, versions: dict, video: Path, out: Path, system: str) -> dict:
    topics = [t for t in doc["levels"]["default"]["topics"] if not t["flags"]["no_topic"]]
    topics.sort(key=lambda t: t["spans"][0][0])
    clips = [c for pl in versions["full_chapters"]["playlists"] for c in pl]
    by_span = {(round(c["t0"], 2), round(c["t1"], 2)): c for c in clips}
    chapters, td = [], out / "thumbs"
    for i, t in enumerate(topics):
        t0, t1 = t["spans"][0]
        c = by_span.get((round(t0, 2), round(t1, 2)))
        clip = c.get("file") if c else None
        name = f"{system}_{i:03d}.jpg"
        ok = thumb(video, (t0 + t1) / 2, td / name)
        chapters.append({"i": i, "t0": round(t0, 2), "t1": round(t1, 2),
                         "label": t.get("label") or "", "thumb": f"thumbs/{name}" if ok else None,
                         "clip": clip, "returns": t.get("returns", 0)})
    return {"system": system, "duration_s": doc["duration_s"], "chapters": chapters}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=str(ROOT / "data/films_runs/Spider_Man"))
    ap.add_argument("--video", default=str(ROOT / "data/films_runs/inputs/Spider_Man.mp4"))
    ap.add_argument("--out", default=str(ROOT / "data/cava_runs_e041"))
    ap.add_argument("--budget", type=float, default=240.0)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    run, video, out = Path(args.run), Path(args.video), Path(args.out)
    doc = json.loads((run / "topic_map.json").read_text())
    D = doc["duration_s"]
    frac = args.budget / D
    print(f"[e041] película {D:.0f}s · presupuesto H {args.budget:.0f}s · frac {frac:.6f}", flush=True)

    # --- CAVA: capítulos existentes + highlights 240 s
    cava = out / "cava"
    cava.mkdir(parents=True, exist_ok=True)
    src_versions = json.loads((run / "versions.json").read_text())
    v = build_versions(doc, highlight_frac=frac)
    v["highlights240"] = v.pop("highlights10pct")
    v["full_chapters"] = src_versions["full_chapters"]  # clips ya cortados
    t0 = time.time()
    made = render(video, cava, {"full_chapters": v["full_chapters"], "highlights240": v["highlights240"]})
    print(f"[e041] CAVA: {made} clips, {time.time()-t0:.1f}s", flush=True)
    vj = viewer(doc, v, video, cava, "cava")
    (cava / "viewer.json").write_text(json.dumps(vj, ensure_ascii=False, indent=1))
    (cava / "versions_240.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))

    # --- U: capítulos equiespaciados + highlights 240 s equiespaciados
    u = out / "u"
    u.mkdir(parents=True, exist_ok=True)
    state = _source_state(run)
    units, asr = state["units"], state.get("asr", [])
    n = len(units)
    unit_times = [[round(a, 2), round(b, 2)] for a, b in units]
    summaries = json.loads((run / "work/summaries.json").read_text())
    cfg = dict(PROFILES["film"]) | {"profile": "film"}
    tmp = make_src_link(run, out / "_src_u", {"recap60": v["recap60"], "highlights10pct": v["highlights240"]})
    doc_u, v_u = base_u(state, u, cfg, tmp, summaries, asr, unit_times, n, D, args.budget)
    doc_u["video_id"] = "Spider_Man_U"
    t0 = time.time()
    topics = doc_u["levels"]["default"]["topics"]
    label_topics(topics, u / "work/topic_labels.json", args.device)
    print(f"[e041] U: etiquetas {time.time()-t0:.1f}s", flush=True)
    made = render(video, u, {"full_chapters": v_u["full_chapters"], "highlights240": v_u["highlights10pct"]})
    print(f"[e041] U: {made} clips", flush=True)
    (u / "topic_map.json").write_text(json.dumps(doc_u, ensure_ascii=False, indent=1))
    vju = viewer(doc_u, v_u, video, u, "u")
    (u / "viewer.json").write_text(json.dumps(vju, ensure_ascii=False, indent=1))
    (u / "versions_240.json").write_text(json.dumps(v_u, ensure_ascii=False, indent=1))

    summary = {
        "video": "Spider_Man", "duration_s": D, "budget_h_s": args.budget,
        "cava": {"chapters": len(vj["chapters"]), "h_clips": len(v["highlights240"]["playlists"][0]),
                 "h_file": "cava/version_highlights240_0.mp4"},
        "u": {"chapters": len(vju["chapters"]), "h_clips": len(v_u["highlights10pct"]["playlists"][0]),
              "h_file": "u/version_highlights240_0.mp4"},
    }
    (out / "stimuli.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps(summary, indent=1), flush=True)


if __name__ == "__main__":
    main()
