"""CAVA de punta a punta sobre videos largos: video -> tópicos -> etiquetas -> hablantes -> versiones -> clips.

Uso:  python scripts/cava_run.py VIDEO[:perfil[:AUDIO]] ... --out data/cava_runs
      perfil = film (por defecto) | meeting; AUDIO opcional si el video no trae pista de audio
Salida por video en <out>/<nombre>/: topic_map.json, versions.json, index.md/json,
clips/*.mp4, version_<perfil>_<k>.mp4 y work/ (caché resumible de cada etapa).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.pipeline import Pipeline  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--out", default="data/cava_runs")
    ap.add_argument("--no-cut", action="store_true", help="no cortar mp4 (solo mapas y versiones)")
    ap.add_argument("--no-labels", action="store_true", help="sin etiquetas de nivel tópico (14B)")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()
    report = {}
    for spec in args.videos:
        path, profile, audio = (spec.split(":") + ["", ""])[:3]
        name = Path(path).stem
        p = Pipeline(path, Path(args.out) / name, profile=profile or "film", labels=not args.no_labels,
                     audio=audio or None, device=args.device)
        gate = p.run(cut=not args.no_cut)
        report[name] = {"profile": profile or "film", "G_version": gate["G_version"],
                        "duration_min": round(p.state["duration"] / 60, 1),
                        "n_topics": p.doc["levels"]["default"]["n_topics"],
                        "n_returning": p.doc["levels"]["default"]["n_returning"],
                        "voices": len(p.doc.get("voice_identities", []))}
    Path(args.out, "run_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
