#!/usr/bin/env python3
"""Mide capacidad de generación por API; ignora y no persiste el texto de salida."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import subprocess
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen


def gpu_memory_mib() -> int | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True,
        )
        return sum(int(line.strip()) for line in result.stdout.splitlines() if line.strip())
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def post(base_url: str, model: str, prompt: str, max_tokens: int) -> tuple[int, int, float]:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "seed": 17,
    }).encode()
    request = Request(
        f"{base_url.rstrip('/')}/chat/completions", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    started = time.perf_counter()
    with urlopen(request, timeout=900) as response:
        payload = json.loads(response.read())
    elapsed = time.perf_counter() - started
    usage = payload.get("usage") or {}
    if "prompt_tokens" not in usage or "completion_tokens" not in usage:
        raise RuntimeError("La API no devolvió usage.prompt_tokens/completion_tokens")
    return int(usage["prompt_tokens"]), int(usage["completion_tokens"]), elapsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--max-tokens", type=int, default=70)
    args = parser.parse_args()

    prompts = [json.loads(line)["prompt"] for line in args.prompts.read_text().splitlines() if line]
    if not prompts:
        raise SystemExit("No hay prompts")
    prompts = [prompts[index % len(prompts)] for index in range(args.requests)]

    # Calentamiento fuera de la ventana medida; no se conserva el texto generado.
    post(args.base_url, args.model, prompts[0], min(args.max_tokens, 8))
    baseline_memory = gpu_memory_mib()
    memory_samples = [baseline_memory] if baseline_memory is not None else []
    stop = threading.Event()

    def sample_memory() -> None:
        while not stop.wait(0.2):
            used = gpu_memory_mib()
            if used is not None:
                memory_samples.append(used)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(post, args.base_url, args.model, prompt, args.max_tokens)
                for prompt in prompts
            ]
            results = [future.result() for future in futures]
    finally:
        wall_seconds = time.perf_counter() - started
        stop.set()
        sampler.join()

    prompt_tokens = sum(result[0] for result in results)
    completion_tokens = sum(result[1] for result in results)
    latencies = [result[2] for result in results]
    peak_memory = max(memory_samples) if memory_samples else None
    print(json.dumps({
        "model": args.model,
        "requests": len(results),
        "concurrency": args.concurrency,
        "max_tokens": args.max_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "wall_seconds": round(wall_seconds, 2),
        "completion_tokens_per_second": round(completion_tokens / wall_seconds, 2),
        "all_tokens_per_second": round((prompt_tokens + completion_tokens) / wall_seconds, 2),
        "request_latency_median_seconds": round(statistics.median(latencies), 2),
        "request_latency_p95_seconds": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 2),
        "gpu_memory_baseline_mib": baseline_memory,
        "gpu_memory_peak_mib": peak_memory,
    }, indent=2))


if __name__ == "__main__":
    main()
