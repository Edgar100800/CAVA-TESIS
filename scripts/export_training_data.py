"""Exporta datos de entrenamiento CAVA: señales por unidad + objetivos GT, un archivo por video.

Esquema (data/training/<dominio>/<id>.npz + <id>.json):
  npz  units [n,2] (s) · una matriz por señal (float16; nunca fusionadas)
       ami:      voice, visual, transcript, vjudge
       movienet: visual, dialogue, vjudge
       objetivos:
         ami:      topic [n] (índice de etiqueta GT o -1), speaker [n] (hablante dominante o -1)
         movienet: scene [n] (escena GT), beat [n] (párrafo story o -1),
                   cast [n, C] (multi-hot de personajes por shot, cast GT)
  json dominio, split, id, vocabularios (etiquetas de tópico, hablantes, personajes)
Las señales son las mismas que usa el pipeline; el GT solo va en los objetivos.
Uso para pesos: aprender pesos/umbrales POR SEÑAL de manage() (permitido por
ADR-0001), nunca una representación fusionada.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_voice_identities import dominant  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402

OUT = Path("data/training")
MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")


def export_ami(meetings, split, bge):
    D = Path("data/ami")
    out = OUT / "ami"
    out.mkdir(parents=True, exist_ok=True)
    for m in meetings:
        fj, fz, fv = D / "signals" / f"{m}.json", D / "signals" / f"{m}.npz", D / "vjudge" / f"{m}.summaries.json"
        if not (fj.exists() and fz.exists() and fv.exists()):
            continue
        meta, z, sums = json.loads(fj.read_text()), np.load(fz), json.loads(fv.read_text())
        gt = json.loads((D / "gt" / f"{m}.json").read_text())
        units = meta["unit_times"]
        n = min(len(units), len(sums), len(z["voice"]))
        units = units[:n]
        labels = sorted({t["label"] for t in gt["topics"]})
        topic = [labels.index(next((t["label"] for t in gt["topics"] if t["t0"] <= (a + b) / 2 <= t["t1"]),
                                   None)) if any(t["t0"] <= (a + b) / 2 <= t["t1"] for t in gt["topics"]) else -1
                 for a, b in units]
        dom = dominant(units, gt["speech"])
        spk = sorted({d for d in dom if d})
        np.savez_compressed(out / f"{m}.npz", units=np.asarray(units, np.float32),
                            voice=z["voice"][:n].astype(np.float16), visual=z["visual"][:n].astype(np.float16),
                            transcript=bge([t or "" for t in meta["asr_text"][:n]]).astype(np.float16),
                            vjudge=bge([s["summary"] for s in sums[:n]]).astype(np.float16),
                            topic=np.asarray(topic, np.int16),
                            speaker=np.asarray([spk.index(d) if d else -1 for d in dom], np.int16))
        (out / f"{m}.json").write_text(json.dumps({"domain": "ami", "split": split, "id": m, "unit_s": 10.0,
                                                   "topic_labels": labels, "speakers": spk}))
        print(f"[export] ami {split} {m}: {n} unidades", flush=True)


def export_movienet(films, split, bge, summary_dir):
    out = OUT / "movienet"
    out.mkdir(parents=True, exist_ok=True)
    for tt in films:
        fz, fd = Path("data/movienet_topics") / f"{tt}.npz", None
        for d in ("data/movienet_voters", "data/movienet_dialogue"):
            if (Path(d) / f"{tt}.npz").exists():
                fd = Path(d) / f"{tt}.npz"
        fs = Path(summary_dir) / f"{tt}.summaries.json"
        if not (fz.exists() and fd and fs.exists()):
            continue
        meta = json.loads((Path("data/movienet_topics") / f"{tt}.json").read_text())
        vis = np.load(fz)["visual"]
        dia = np.load(fd)["dialogue"]
        sums = json.loads(fs.read_text())
        n = min(len(vis), len(dia), sums[-1]["hi"], meta["n_shots"])
        e = bge([u["summary"] for u in sums])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for u, v in zip(sums, e):
            vj[u["lo"]:min(u["hi"], n)] = v
        ann = json.loads((MN / "annotation" / f"{tt}.json").read_text())
        scene = np.zeros(n, np.int16)
        for k, s in enumerate(ann.get("scene") or []):
            scene[s["shot"][0]:min(s["shot"][1] + 1, n)] = k
        beat = np.full(n, -1, np.int16)
        for k, s in enumerate(sorted(ann.get("story") or [], key=lambda x: x["shot"][0])):
            beat[s["shot"][0]:min(s["shot"][1] + 1, n)] = k
        chars = sorted({c["pid"] for c in (ann.get("cast") or []) if c.get("pid") and c["pid"] != "others"})
        cast = np.zeros((n, len(chars)), np.uint8)
        for c in ann.get("cast") or []:
            if c.get("pid") in chars and c["shot_idx"] < n:
                cast[c["shot_idx"], chars.index(c["pid"])] = 1
        np.savez_compressed(out / f"{tt}.npz", units=np.asarray(meta["shot_times"][:n], np.float32),
                            visual=vis[:n].astype(np.float16), dialogue=dia[:n].astype(np.float16),
                            vjudge=vj.astype(np.float16), scene=scene, beat=beat, cast=cast)
        (out / f"{tt}.json").write_text(json.dumps({"domain": "movienet", "split": split, "id": tt,
                                                    "characters": chars}))
        print(f"[export] movienet {split} {tt}: {n} shots, {len(chars)} personajes", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--which", nargs="+", default=["ami", "movienet"])
    args = ap.parse_args()
    bge = BgeEmbedder()
    if "ami" in args.which:
        for f, split in (("data/ami/meetings_40.txt", "dev"), ("data/ami/meetings_fresh40.txt", "conf"),
                         ("data/ami/meetings_fresh3.txt", "fresh3")):
            if Path(f).exists():
                export_ami(Path(f).read_text().split(), split, bge)
    if "movienet" in args.which:
        for f, split, sd in (("scripts/exp017_dev_films.txt", "val", "data/vjudge_ledger"),
                             ("scripts/exp018_test_films.txt", "test", "data/vjudge_ledger_test8"),
                             ("scripts/exp016_train_films.txt", "train", "data/vjudge_ledger_train8"),
                             ("scripts/exp019_train2_films.txt", "train2", "data/vjudge_ledger_train2")):
            export_movienet(Path(f).read_text().split(), split, bge, sd)


if __name__ == "__main__":
    main()
