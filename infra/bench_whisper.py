#!/usr/bin/env python3
"""Mide Whisper/CTranslate2 sin imprimir ni evaluar las transcripciones."""
from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
import wave
from pathlib import Path


def gpu_memory_mib() -> int | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True,
        )
        return sum(int(line.strip()) for line in result.stdout.splitlines() if line.strip())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--compute-type", choices=("float16", "int8_float16"), required=True)
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    import ctranslate2
    from faster_whisper import WhisperModel

    supported_compute_types = sorted(ctranslate2.get_supported_compute_types(args.device))
    if args.compute_type not in supported_compute_types:
        raise SystemExit(
            f"compute_type={args.compute_type} no está soportado en {args.device}: "
            f"{supported_compute_types}"
        )

    load_started = time.perf_counter()
    model = WhisperModel(str(args.model), device=args.device, compute_type=args.compute_type)
    load_seconds = time.perf_counter() - load_started

    with wave.open(str(args.audio), "rb") as wav:
        audio_seconds = wav.getnframes() / wav.getframerate()
    baseline_memory = gpu_memory_mib()
    samples = [baseline_memory] if baseline_memory is not None else []
    stop = threading.Event()

    def sample_memory() -> None:
        while not stop.wait(0.2):
            used = gpu_memory_mib()
            if used is not None:
                samples.append(used)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        segments, _ = model.transcribe(str(args.audio), vad_filter=True)
        for _ in segments:
            pass
        inference_seconds = time.perf_counter() - started
    finally:
        stop.set()
        sampler.join()

    print(json.dumps({
        "compute_type": args.compute_type,
        "supported_compute_types": supported_compute_types,
        "device": args.device,
        "audio_seconds": round(audio_seconds, 2),
        "load_seconds": round(load_seconds, 2),
        "inference_seconds": round(inference_seconds, 2),
        "real_time_factor": round(inference_seconds / audio_seconds, 4),
        "audio_minutes_per_wall_minute": round(audio_seconds / inference_seconds, 2),
        "gpu_memory_baseline_mib": baseline_memory,
        "gpu_memory_peak_mib": max(samples) if samples else None,
    }, indent=2))


if __name__ == "__main__":
    main()
