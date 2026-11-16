"""Normalize uploaded films, run CAVA, and export exact clip timestamps."""
import csv
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    ("Avengers*", "Avengers_Endgame"),
    ("Spider-Man*", "Spider_Man"),
]


def timestamp(seconds):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=int, choices=range(len(SOURCES)))
    parser.add_argument("--sample-seconds", type=float)
    parser.add_argument("--sample-start", type=float, default=600)
    parser.add_argument("--smoke-cpu-labels", action="store_true")
    args = parser.parse_args()
    if args.smoke_cpu_labels and not args.sample_seconds:
        parser.error("--smoke-cpu-labels requires --sample-seconds")
    pattern, name = SOURCES[args.index]
    sources = list((ROOT / "films").glob(pattern + ".mkv"))
    if len(sources) != 1:
        raise RuntimeError(f"Expected one source for {pattern}: {sources}")
    source = sources[0]
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(source),
    ], text=True))
    audio = next(s["index"] for s in probe["streams"]
                 if s["codec_type"] == "audio" and s.get("tags", {}).get("language") == "eng")
    base = ROOT / ("data/films_smoke" if args.sample_seconds else "data/films_runs")
    if args.sample_seconds:
        name += f"_sample_{args.sample_start:g}_{args.sample_seconds:g}"
    prepared = base / "inputs"
    prepared.mkdir(parents=True, exist_ok=True)
    video = prepared / f"{name}.mp4"
    if not video.exists():
        partial = prepared / f"{name}.part.mp4"
        seek = ["-ss", str(args.sample_start)] if args.sample_seconds else []
        limit = ["-t", str(args.sample_seconds)] if args.sample_seconds else []
        subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", *seek, "-i", str(source), *limit,
            "-map", "0:v:0", "-map", f"0:{audio}", "-sn", "-dn",
            "-map_metadata", "-1", "-map_chapters", "-1", "-vf", "scale=-2:480",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-threads", "8",
            "-c:a", "aac", "-ac", "2", "-b:a", "128k", "-movflags", "+faststart",
            str(partial),
        ], check=True)
        partial.replace(video)
    out = base / name
    out.mkdir(exist_ok=True)
    (out / "source.json").write_text(json.dumps({
        "original": str(source), "prepared": str(video),
        "audio_language": "eng", "profile": "film",
        "source_offset_s": args.sample_start if args.sample_seconds else 0,
        "sample_seconds": args.sample_seconds,
    }, indent=2))
    if args.smoke_cpu_labels:
        sys.path.insert(0, str(ROOT))
        from topicagg.pipeline import Pipeline

        class SmokePipeline(Pipeline):
            def labels(self):
                original_device = self.device
                self.device = "cpu"
                try:
                    return super().labels()
                finally:
                    self.device = original_device

        print("SMOKE: labels on CPU; other model stages on CUDA", flush=True)
        SmokePipeline(video, out, profile="film").run()
    else:
        subprocess.run([sys.executable, str(ROOT / "scripts/cava_run.py"),
                        f"{video}:film", "--out", str(base)], check=True, cwd=ROOT)
    manifest = json.loads((out / "run_manifest.json").read_text())
    if not manifest["outputs"]["G_version"]:
        raise RuntimeError("CAVA version validation failed")
    rows = [json.loads(line) for line in (out / "clips.jsonl").read_text().splitlines()]
    if not rows:
        raise RuntimeError("CAVA generated no clips")
    with (out / "clip_times.csv").open("w", newline="") as fh:
        fields = ["version", "playlist", "order", "inicio", "fin", "t0", "t1",
                  "duration_s", "topic_id", "topic_label", "file"]
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            if not 0 <= row["t0"] < row["t1"]:
                raise ValueError(f"Invalid interval: {row}")
            clip = out / row["file"]
            if not clip.is_file() or clip.stat().st_size == 0:
                raise RuntimeError(f"Missing clip: {clip}")
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                "-of", "json", str(clip),
            ], text=True))
            if abs(float(probe["format"]["duration"]) - row["duration_s"]) > 0.15:
                raise RuntimeError(f"Incorrect clip duration: {clip}")
            if not {"audio", "video"} <= {s["codec_type"] for s in probe["streams"]}:
                raise RuntimeError(f"Missing audio/video stream: {clip}")
            if args.sample_seconds:
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-i", str(clip),
                                "-f", "null", "-"], check=True, capture_output=True)
            writer.writerow(row | {"inicio": timestamp(row["t0"]), "fin": timestamp(row["t1"])})
    print(f"DONE: {out / 'clip_times.csv'} ({len(rows)} clips)", flush=True)


if __name__ == "__main__":
    main()
