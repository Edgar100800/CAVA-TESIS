"""EXP-045-Q: corridas auxiliares sobre una copia del `work/` de la corrida ref (aislamiento por pista y ablaciones).

Uso: python scripts/exp045_runs.py --spec "vjudge=fast" --names Spider_Man,bbc_01 [--labels]
  Para cada video crea /data/tesis-cava/exp045/runs/abl/<spec>/<video>/ con `work/` = copia de la corrida ref
  (archivos pequeños copiados, audio/frames enlazados) + los artefactos fast que la spec pida, y ejecuta solo las
  etapas necesarias (hasta el mapa; con --labels también etiquetas). Escribe topic_map.json, versions.json y
  timings.json (s por etapa). Las salidas de las pistas fast quedan con la variante en el nombre.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp045_common import EXP, STACK, VIDEOS  # noqa: E402
from topicagg import variants as V  # noqa: E402
from topicagg.pipeline import Pipeline  # noqa: E402
from topicagg.versions import build_versions, check_versions  # noqa: E402

LINK = {"audio.wav", "frames", "frames1fps"}


def make_work(src_run, src_fast, dst, spec):
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "work").mkdir(exist_ok=True)
    for p in (src_run / "work").iterdir():
        t = dst / "work" / p.name
        if t.exists() or t.is_symlink():
            continue
        if p.name in LINK or p.is_dir():
            t.symlink_to(p.resolve())
        else:
            shutil.copy2(p, t)
    var = V.parse_variant(spec)
    fw = src_fast / "work"
    # artefactos de la corrida fast completa que se reutilizan cuando la spec los pide (ASR y visual no dependen de LLM)
    if var["asr"] == "fast":
        shutil.copy2(fw / "asr.fast.json", dst / "work")
    if var["visual"] == "fast":
        shutil.copy2(fw / "signals.visual.fast.npy", dst / "work")
    if var["vjudge"] == "fast" and not (dst / "work/frames1fps").exists() and (fw / "frames1fps").exists():
        (dst / "work/frames1fps").symlink_to((fw / "frames1fps").resolve())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--names", default=",".join(VIDEOS))
    ap.add_argument("--runs", default=str(EXP / "runs"))
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    runs = Path(a.runs)
    tag = a.spec.replace("=", "-").replace(",", "+") + ("+LBL" if a.labels else "")
    for name in a.names.split(","):
        v = VIDEOS[name]
        out = runs / "abl" / tag / name
        make_work(runs / "ref" / name, runs / "fast" / name, out, a.spec)
        p = Pipeline(v["path"], out, profile=v["profile"], stack=STACK, labels=a.labels, audio=v["audio"],
                     device=a.device, variant=a.spec)
        tm = {}
        for st in ("prepare", "asr", "signals", "vjudge", "topic_map") + (("labels",) if a.labels else ()):
            t0 = time.time()
            getattr(p, st)()
            tm[st] = round(time.time() - t0, 2)
        doc = p.doc
        vers = build_versions(doc)
        (out / "topic_map.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        (out / "versions.json").write_text(json.dumps(vers, ensure_ascii=False, indent=1))
        tm["G_version"] = check_versions(vers)["G_version"]
        tm["duration_s"] = p.state["duration"]
        tm["sub"] = p.sub_timings
        (out / "timings.json").write_text(json.dumps(tm, indent=1))
        print(f"[abl {tag}] {name}: {tm}", flush=True)


if __name__ == "__main__":
    main()
