"""Exporta los tramos consecutivos de consenso como MP4 H.264/AAC."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys


def timestamp(seconds):
    value = int(seconds)
    return f"{value // 3600:02}:{value % 3600 // 60:02}:{value % 60:02}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("result_dir", type=Path)
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    if args.workers < 1:
        ap.error("workers debe ser positivo")
    root = args.result_dir.resolve()
    result_path = root / "topics.json"
    result = json.loads(result_path.read_text())
    source = Path(result["protocol"]["video"])
    duration = result["protocol"]["analyzed_seconds"]
    bounds = [0.0] + result["cut_seconds"] + [duration]
    assert all(a < b for a, b in zip(bounds, bounds[1:]))
    out = root / "clips"
    out.mkdir(exist_ok=True)
    ffmpeg = Path(sys.executable).parent / "ffmpeg"
    ffprobe = Path(sys.executable).parent / "ffprobe"
    settings = {"source": str(source), "source_size": source.stat().st_size,
                "source_mtime_ns": source.stat().st_mtime_ns,
                "topics_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
                "video_codec": "libx264", "preset": "veryfast", "crf": 23,
                "audio_codec": "aac", "audio_bitrate": "128k"}
    settings_path = out / "export_protocol.json"
    if settings_path.exists() and json.loads(settings_path.read_text()) != settings:
        raise RuntimeError("Los clips existentes corresponden a otro protocolo. Usar otra carpeta de resultados.")
    settings_path.write_text(json.dumps(settings, indent=2))
    cues = json.loads((root / "transcript.json").read_text())

    def probe(path, expected):
        meta = json.loads(subprocess.check_output([str(ffprobe), "-v", "error",
            "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height",
            "-of", "json", str(path)], text=True))
        actual = float(meta["format"]["duration"])
        streams = {s["codec_type"]: s for s in meta["streams"]}
        if abs(actual - expected) > .25:
            raise RuntimeError(f"Duración incorrecta en {path.name}: {actual} vs {expected}")
        if streams.get("video", {}).get("codec_name") != "h264" or streams.get("audio", {}).get("codec_name") != "aac":
            raise RuntimeError(f"Faltan los canales H.264/AAC en {path.name}")
        return actual, int(meta["format"]["size"])

    def export(index, start, end):
        filename = f"clip_{index:03d}_{timestamp(start).replace(':', '-')}_{timestamp(end).replace(':', '-')}.mp4"
        target = out / filename
        expected = end - start
        if not target.exists():
            temporary = out / (target.stem + ".partial.mp4")
            log = out / (target.stem + ".log")
            with log.open("w") as output:
                subprocess.run([str(ffmpeg), "-y", "-nostdin", "-hide_banner", "-loglevel", "error",
                    "-threads", "2", "-ss", str(start), "-i", str(source), "-t", str(expected),
                    "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-threads", "2",
                    "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                    str(temporary)], stdout=output, stderr=output, check=True)
            probe(temporary, expected)
            temporary.replace(target)
        actual, size = probe(target, expected)
        text = " ".join(c["text"] for c in cues if c["start"] < end and c["end"] > start)
        return {"clip": index, "file": filename, "start_seconds": start, "end_seconds": end,
                "expected_duration_seconds": expected, "actual_duration_seconds": actual,
                "bytes": size, "transcript": text}

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(export, i, a, b) for i, (a, b) in enumerate(zip(bounds, bounds[1:]), 1)]
        for future in as_completed(futures):
            rows.append(future.result())
            print(f"Exportados {len(rows)}/{len(futures)} | último: {rows[-1]['file']}", flush=True)
    rows.sort(key=lambda r: r["clip"])
    assert len(rows) == len(bounds) - 1
    assert abs(sum(r["expected_duration_seconds"] for r in rows) - duration) < 1e-6
    manifest = {"protocol": settings, "n_clips": len(rows), "source_duration_seconds": duration,
                "total_bytes": sum(r["bytes"] for r in rows), "clips": rows}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    cards = []
    for r in rows:
        center = min(int((r["start_seconds"] + r["end_seconds"]) / 20), result["n_windows"] - 1)
        cards.append(f'<article><h2>Clip {r["clip"]:02} · {timestamp(r["start_seconds"])} → {timestamp(r["end_seconds"])}</h2>'
            f'<p>Duración: {r["expected_duration_seconds"]:.1f} s</p>'
            f'<video controls preload="none" poster="../frames/{center:04d}.jpg" src="{html.escape(r["file"])}"></video>'
            f'<p><a download href="{html.escape(r["file"])}">Descargar MP4</a></p>'
            f'<details><summary>Ver transcripción</summary><p>{html.escape(r["transcript"])}</p></details></article>')
    (out / "index.html").write_text('<!doctype html><html lang="es"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>CAVA · Clips</title>'
        '<style>body{font-family:system-ui;background:#f1f4f7;color:#182533;margin:0 auto;max-width:1200px;padding:24px}'
        'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}'
        'article{background:white;border-radius:12px;padding:18px}video{width:100%;border-radius:8px}'
        'h2{font-size:18px}details p{line-height:1.6}a{color:#17618a}</style>'
        f'<h1>CAVA · {len(rows)} clips del video completo</h1>'
        '<p>Tramos consecutivos delimitados por consenso de texto e imagen. Conservan todo el video; no son un resumen.</p>'
        '<p>Revisión manual pendiente: algunas fronteras pueden cortar una frase o mantener varios temas.</p>'
        '<main>' + ''.join(cards) + '</main></html>')
    print(json.dumps({"n_clips": len(rows), "total_bytes": manifest["total_bytes"],
                      "viewer": str(out / "index.html")}), flush=True)


if __name__ == "__main__":
    main()
