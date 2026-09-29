"""Construye `data/topic_maps/<tt>.topic_map.json` para películas MovieNet.

Señales (sin fusión): visual (SigLIP por shot), dialogue (bge del subtítulo),
vjudge (bge del resumen VJudge de la unidad del shot) y, si se da
--segloop-dir, SegLoop como votante de fronteras. Parámetros = pre-registro
EXP-017b (percentile 80, return_percentile 90, link_mode average, quorum 2).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from narrative_eval import BgeEmbedder  # noqa: E402
from topicagg.topic_map import build_topic_map  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--dialogue-dir", required=True)
    ap.add_argument("--summary-dir", required=True)
    ap.add_argument("--segloop-dir", default=None)
    ap.add_argument("--out", default="data/topic_maps")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bge = BgeEmbedder()
    for tt in Path(args.films_file).read_text().split():
        meta = json.loads((Path(args.corpus) / f"{tt}.json").read_text())
        vis = np.asarray(np.load(Path(args.corpus) / f"{tt}.npz")["visual"], np.float32)
        dia = np.asarray(np.load(Path(args.dialogue_dir) / f"{tt}.npz")["dialogue"], np.float32)
        sums = json.loads((Path(args.summary_dir) / f"{tt}.summaries.json").read_text())
        n = min(len(vis), len(dia), sums[-1]["hi"], meta["n_shots"])
        e = bge([u["summary"] for u in sums])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for u, v in zip(sums, e):
            vj[u["lo"]:min(u["hi"], n)] = v
        bnd = None
        if args.segloop_dir and (Path(args.segloop_dir) / f"{tt}.npz").exists():
            bnd = {"segloop": np.asarray(np.load(Path(args.segloop_dir) / f"{tt}.npz")["segloop"][:n - 1],
                                         np.float32)}
        doc = build_topic_map(tt, {"visual": vis[:n], "dialogue": dia[:n], "vjudge": vj},
                              meta["shot_times"][:n], unit_summaries=sums, boundary_signals=bnd)
        (out / f"{tt}.topic_map.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        d = doc["levels"]["default"]
        print(f"[topicmap] {tt}: {d['n_topics']} tópicos ({d['n_returning']} con retornos), "
              f"fine {doc['levels']['fine']['n_topics']}", flush=True)


if __name__ == "__main__":
    main()
