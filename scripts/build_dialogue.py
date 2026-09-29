"""bge-base del subtítulo de cada shot (EXP-016, películas sin votantes val).

Escribe <out>/<tt>.npz con `dialogue` [n, 768] (fila 0 = sin diálogo), igual
que el campo `dialogue` de build_val_voters.py. Resumible.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_val_voters import MN  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from narrative_interpreter import parse_srt  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--out", default="data/movienet_dialogue")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bge = BgeEmbedder()
    for tt in Path(args.films_file).read_text().split():
        if (out / f"{tt}.npz").exists():
            continue
        st = json.loads((Path(args.corpus) / f"{tt}.json").read_text())["shot_times"]
        cues = parse_srt(MN / "subtitle" / f"{tt}.srt")
        texts = [" ".join(x for a, b, x in cues if a < t1 and b > t0) for t0, t1 in st]
        np.savez_compressed(out / f"{tt}.npz", dialogue=bge(texts).astype(np.float16))
        print(f"[dialogue] {tt}: {len(texts)} shots", flush=True)


if __name__ == "__main__":
    main()
