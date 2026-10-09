"""Prueba manual de CAVA sobre videos externos, sin etiquetas del corpus."""
import argparse
import html
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "SegLoop"))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", type=Path)
    ap.add_argument("--seconds", type=float, default=600, help="0 = video completo")
    ap.add_argument("--bin-seconds", type=float, default=10)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if not args.video.is_file():
        ap.error(f"No existe el video: {args.video}")
    if args.seconds < 0 or args.bin_seconds <= 0:
        ap.error("seconds debe ser >= 0 y bin-seconds > 0")
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor
    from segloop.io.asr_whisper import transcribe
    from demos.demo_multimodal import tfidf_embeddings
    from topicagg.multimodal_manager import manage

    torch.set_num_threads(4)
    cache = ROOT.parent / "SegLoop/data/hf_cache/hub"
    os.environ["HF_HUB_OFFLINE"] = "1"
    out = args.out or ROOT / "test-video/results" / args.video.stem
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(args.video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    if not cap.isOpened() or fps <= 0 or frames <= 0:
        raise RuntimeError("No se pudo decodificar el video")
    duration = frames / fps
    end = min(duration, args.seconds) if args.seconds else duration
    n = math.ceil(end / args.bin_seconds)
    if n < 3:
        raise RuntimeError("Se requieren al menos tres ventanas temporales")
    times = [[i * args.bin_seconds, min((i + 1) * args.bin_seconds, end)] for i in range(n)]
    config = dict(percentile=80, min_gap=2, link_quorum=2, cut_quorum=2,
                  tolerance_bins=1, return_percentile=90, link_mode="average", abstain=True)
    protocol = {"video": str(args.video.resolve()), "duration_seconds": duration,
                "analyzed_seconds": end, "bin_seconds": args.bin_seconds,
                "sampling": "un frame central por ventana; no detección de shots",
                "signals": ["transcript_tfidf_whisper_tiny", "visual_siglip"],
                "config": config, "evaluation": "demo manual sin ground truth ni métricas de precisión"}
    protocol_path = out / "protocol.json"
    reuse = protocol_path.exists() and json.loads(protocol_path.read_text()) == protocol
    protocol_path.write_text(json.dumps(protocol, indent=2, ensure_ascii=False))
    ffmpeg = Path(sys.executable).parent / "ffmpeg"
    audio = out / "audio.wav"
    if not (reuse and audio.exists()):
        subprocess.run([str(ffmpeg), "-y", "-v", "error", "-i", str(args.video),
                        "-t", str(end), "-vn", "-ac", "1", "-ar", "16000", str(audio)], check=True)
    whisper = next((cache / "models--Systran--faster-whisper-tiny/snapshots").iterdir())
    print(f"ASR: {end:.1f}s", flush=True)
    from segloop.io.asr_whisper import AsrSegment
    transcript_path = out / "transcript.json"
    if reuse and transcript_path.exists():
        cues = [AsrSegment(**c) for c in json.loads(transcript_path.read_text())]
    else:
        cues = transcribe(str(audio), model_size=str(whisper), device="cpu", compute_type="int8")
    (out / "transcript.json").write_text(json.dumps([vars(c) for c in cues], indent=2, ensure_ascii=False))
    texts = [" ".join(c.text for c in cues if c.start < b and c.end > a) for a, b in times]
    text_emb = tfidf_embeddings(texts)
    if text_emb.shape[1] == 0 or not np.any(text_emb):
        raise RuntimeError("No hay texto suficiente para una prueba con dos señales")
    print(f"SigLIP: {n} ventanas", flush=True)
    model_name = "google/siglip-base-patch16-224"
    processor = AutoProcessor.from_pretrained(model_name, cache_dir=str(cache), local_files_only=True)
    model = AutoModel.from_pretrained(model_name, cache_dir=str(cache), local_files_only=True).eval()
    visual = []
    thumbs = out / "frames"
    thumbs.mkdir(exist_ok=True)
    for i, (a, b) in enumerate(times):
        frame_path = thumbs / f"{i:04d}.jpg"
        # FFmpeg permite decodificar AV1 por software en este entorno.
        subprocess.run([str(ffmpeg), "-y", "-v", "error", "-threads", "2",
                        "-ss", str((a + b) / 2), "-i", str(args.video),
                        "-frames:v", "1", "-vf", "scale=480:-2", str(frame_path)], check=True)
        with Image.open(frame_path) as frame:
            img = frame.convert("RGB")
        inputs = processor(images=img, return_tensors="pt")
        with torch.inference_mode():
            features = model.get_image_features(**inputs)
            if hasattr(features, "pooler_output"):
                features = features.pooler_output
            elif not isinstance(features, torch.Tensor):
                features = features[0]
            visual.append(features.float().cpu().numpy()[0])
        if i % 20 == 0:
            print(f"visual {i + 1}/{n}", flush=True)
    cap.release()
    visual = np.asarray(visual, dtype=np.float32)
    assert np.isfinite(visual).all() and np.isfinite(text_emb).all()
    np.savez_compressed(out / "signals.npz", transcript=text_emb, visual=visual, times=times)
    plan = manage({"transcript": text_emb, "visual": visual}, n_segments=n, **config)
    groups = [{"topic_id": g.topic_id, "segment_indices": g.segment_indices,
               "signal_support": g.signal_support, "no_topic": getattr(g, "no_topic", False),
               "needs_review": getattr(g, "needs_review", False)} for g in plan.groups]
    assert sorted(i for g in groups for i in g["segment_indices"]) == list(range(n))
    group_ids = {i: g["topic_id"] for g in groups for i in g["segment_indices"]}
    result = {"protocol": protocol, "n_windows": n, "n_asr_segments": len(cues),
              "text_windows": sum(bool(t.strip()) for t in texts),
              "consensus_cuts": plan.consensus_cuts,
              "cut_seconds": [times[c][0] for c in plan.consensus_cuts],
              "per_signal_cuts": plan.per_signal_cuts, "groups": groups,
              "windows": [{"index": i, "start": a, "end": b, "text": texts[i],
                           "group": group_ids[i]} for i, (a, b) in enumerate(times)]}
    (out / "topics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    rows = "".join(f'<tr><td>{i}</td><td>{a:.1f}–{b:.1f}s</td><td>{group_ids[i]}</td>'
                   f'<td><img width="240" src="frames/{i:04d}.jpg"></td><td>{html.escape(texts[i])}</td></tr>'
                   for i, (a, b) in enumerate(times))
    (out / "review.html").write_text('<!doctype html><meta charset="utf-8"><title>CAVA: video externo</title>'
        '<style>body{font-family:sans-serif;margin:2em}td,th{padding:8px;border:1px solid #ddd}table{border-collapse:collapse}</style>'
        f'<h1>Prueba CAVA: {html.escape(args.video.stem)}</h1>'
        f'<p>Analizados {end:.1f}s de {duration:.1f}s. {n} ventanas, {len(groups)} grupos.</p>'
        f'<p>Cortes de consenso (segundos): {result["cut_seconds"]}</p>'
        '<p>Demo sin ground truth. Los números de grupo no son nombres de temas. Revisar texto y frames para valorar coherencia.</p>'
        '<table><tr><th>Ventana</th><th>Tiempo</th><th>Grupo</th><th>Imagen</th><th>Transcripción</th></tr>' + rows + '</table>')
    print(json.dumps({"out": str(out), "cuts": result["cut_seconds"], "groups": len(groups)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
