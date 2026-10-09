"""EXP-034: segmentos de inaSpeechSegmenter (env `inaseg`, TensorFlow; CPU) por ítem.

Habla = etiqueta 'speech' (detect_gender=False). → data/gatebench/ina/<dom>/<id>.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp034_items import G, all_items  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doms", nargs="+", default=["ava", "mix", "ami", "bbc"])
    args = ap.parse_args()
    from inaSpeechSegmenter import Segmenter
    seg = Segmenter(vad_engine="smn", detect_gender=False, ffmpeg=str(Path(sys.executable).parents[2] / "segloop/bin/ffmpeg"))
    for it in all_items(args.doms):
        o = G / "ina" / it["dom"] / f"{it['id']}.json"
        if o.exists():
            continue
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(json.dumps([(lab, float(a), float(b)) for lab, a, b in seg(it["wav"])]))
        print(f"[ina] {it['dom']} {it['id']}", flush=True)
    print("EXP034_INA_DONE", flush=True)


if __name__ == "__main__":
    main()
