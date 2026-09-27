"""Extrae señales por shot para el corpus MovieNet-tópicos (314 películas).

Por película:
  - visual: SigLIP mean sobre los keyframes pre-extraídos por shot (240P_frames)
  - text: TF-IDF L2 sobre cues de subtítulo solapados al shot
  - GT: cortes de escena (cambio de invideo_scene_id) a nivel de shot

Salida por película en --out: <tt>.npz (visual f16, tfidf f32) y
<tt>.json (gt_scene_cuts, shot_times, fps, n_shots). Resume-safe.

Nota de señales: el visual aquí es SigLIP-only (sin BaSSL: BaSSL requiere
video decodificado). Para el manager es solo otro canal de embeddings.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

RE = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
SEGLoop = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")


def parse_srt(path):
    cues, start, end, text = [], None, None, []
    for line in Path(path).read_text(errors="ignore").splitlines():
        m = RE.search(line)
        if m:
            g = [int(x) for x in m.groups()]
            if text and start is not None:
                cues.append((start, end, " ".join(text)))
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
            text = []
        elif line.strip() and start is not None:
            text.append(line.strip())
    if text and start is not None:
        cues.append((start, end, " ".join(text)))
    return cues


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/home/edgar.chambilla/Tesis/CAVA/data/movienet_topics")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--batch", type=int, default=128)
    args = ap.parse_args()

    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    siglip_name = "google/siglip-base-patch16-224"
    os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
    processor = AutoProcessor.from_pretrained(siglip_name)
    model = AutoModel.from_pretrained(siglip_name).to(
        "cuda" if torch.cuda.is_available() else "cpu")
    model.eval()

    seg_root = SEGLoop
    shot_root = seg_root / "scene318" / "shot_movie318"
    srt_root = seg_root / "subtitle"
    frames_root = seg_root / "240P_frames"
    info = json.load(open(seg_root / "official" / "video_info.json"))

    anno = {}
    anno_dir = seg_root / "anno"
    for f in ("anno.train.ndjson", "anno.val.ndjson", "anno.test.ndjson"):
        for line in open(anno_dir / f):
            r = json.loads(line)
            anno.setdefault(r["video_id"], []).append(r)

    movies = sorted(anno)
    if args.limit:
        movies = movies[: args.limit]

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    done = skipped = 0
    for mi, tt in enumerate(movies, 1):
        out_npz = out_root / f"{tt}.npz"
        if out_npz.exists():
            skipped += 1
            continue
        shot_file = shot_root / f"{tt}.txt"
        srt_file = srt_root / f"{tt}.srt"
        rows = anno.get(tt)
        if not shot_file.exists() or not srt_file.exists() or not rows:
            print(f"[skip] {tt}: faltan insumos", flush=True)
            continue

        shots = [[int(x) for x in l.split()]
                 for l in shot_file.read_text().splitlines() if l.strip()]
        rows = sorted(rows, key=lambda r: int(r["shot_id"]))
        n = min(len(shots), len(rows))
        shots, rows = shots[:n], rows[:n]
        fps = float(info.get(tt, {}).get("fps", 25.0))

        gt_cuts = [k for k in range(1, n)
                   if int(rows[k]["invideo_scene_id"]) > int(rows[k - 1]["invideo_scene_id"])]

        cues = parse_srt(srt_file)

        vocab, docs = {}, []
        shot_txt = []
        for k in range(n):
            t0 = shots[k][0] / fps
            t1 = (shots[k][1] + 1) / fps
            txt = " ".join(tx for a, b, tx in cues if a < t1 and b > t0)
            shot_txt.append(txt)
            toks = [w for w in re.sub(r"[^a-z0-9 ]", " ", txt.lower()).split()
                    if len(w) > 2]
            docs.append(toks)
            for w in set(toks):
                vocab.setdefault(w, 0)
        vocab = {w: i for i, w in enumerate(sorted(vocab))}
        df = np.zeros(len(vocab), dtype=np.float32)
        for toks in docs:
            for w in set(toks):
                df[vocab[w]] += 1
        idf = np.log((1 + n) / (1 + df)) + 1.0
        tfidf = np.zeros((n, len(vocab)), dtype=np.float32)
        for i, toks in enumerate(docs):
            for w in toks:
                tfidf[i, vocab[w]] += 1.0
            for w in set(toks):
                tfidf[i, vocab[w]] *= idf[vocab[w]]
        nrm = np.linalg.norm(tfidf, axis=1, keepdims=True)
        tfidf = tfidf / (nrm + 1e-8)

        # SigLIP: media de keyframes por shot
        from PIL import Image
        kf_dir = frames_root / tt
        keyframes = [[kf_dir / f"shot_{k:04d}_img_{j}.jpg" for j in range(3)
                      if (kf_dir / f"shot_{k:04d}_img_{j}.jpg").exists()]
                     for k in range(n)]
        flat = [(k, p) for k, paths in enumerate(keyframes) for p in paths]
        visual = None  # dim descubierta en el primer batch
        counts = np.zeros(n, dtype=np.float32)
        for s in range(0, len(flat), args.batch):
            chunk = flat[s:s + args.batch]
            imgs = [Image.open(p).convert("RGB") for _, p in chunk]
            inputs = processor(images=imgs, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                out = model.get_image_features(**inputs)
                out = (out.pooler_output if hasattr(out, "pooler_output")
                       else out[0]).float().cpu().numpy()
            if visual is None:
                visual = np.zeros((n, out.shape[1]), dtype=np.float32)
            for (k, p), v in zip(chunk, out):
                visual[k] += v
                counts[k] += 1
        for k in range(n):
            if counts[k] > 0:
                visual[k] /= counts[k]

        np.savez_compressed(out_npz, visual=visual.astype(np.float16),
                            tfidf=tfidf.astype(np.float16),
                            counts=counts)
        shot_times = [[round(shots[k][0] / fps, 2),
                       round((shots[k][1] + 1) / fps, 2)] for k in range(n)]
        (out_root / f"{tt}.json").write_text(json.dumps({
            "video_id": tt, "fps": fps, "n_shots": n,
            "gt_scene_cuts": gt_cuts, "shot_times": shot_times,
            "n_subtitle_cues": len(cues),
        }))
        done += 1
        if mi % 25 == 0 or mi == len(movies):
            print(f"[mn] {mi}/{len(movies)} {tt}: {n} shots, "
                  f"{len(gt_cuts)} escenas GT, done={done}", flush=True)

    print(f"MOVIENET_EXTRACT_DONE done={done} skipped={skipped}", flush=True)


if __name__ == "__main__":
    main()
