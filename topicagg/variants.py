"""Variantes de ejecución por pista (EXP-045-Q).

`ref` (por defecto) es la precisión y el motor actuales y reproduce byte a byte `tfm-v1.0`/`v1.1`.
`fast` cambia solo la precisión o el motor de una pista:
  asr      faster-whisper compute_type int8_float16 (ref: float16)
  visual   SigLIP: decode-once (fotograma 1 fps más cercano) + lotes de 64 + FP16 (ref: ffmpeg por unidad, FP32)
  vjudge   Qwen2.5-VL-7B BF16 en vLLM, peticiones en lote, fotogramas decode-once (ref: HF generate de a 1)
  embed    bge en GPU FP16 (ref: CPU FP32)
  labels   Qwen2.5-14B con FP8 dinámico en vLLM (ref: HF BF16)
  clips    NVENC h264 (ref: libx264 veryfast)
  speaker  WavLM-sv FP16 (ref: FP32)
Los cachés de las variantes no ref llevan la variante en el nombre de archivo.
"""
from __future__ import annotations

import base64
import io
import json
import math
import os
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TRACKS = ("asr", "visual", "vjudge", "embed", "labels", "clips", "speaker")
VL_MODEL = os.environ.get("CAVA_VLLM_VL_MODEL", "qwen-vl7b-bf16")
TXT_MODEL = os.environ.get("CAVA_VLLM_TXT_MODEL", "qwen14b-fp8")
VL_URL = os.environ.get("CAVA_VLLM_VL_URL", "http://127.0.0.1:8100/v1")
TXT_URL = os.environ.get("CAVA_VLLM_TXT_URL", "http://127.0.0.1:8200/v1")
REPETITION_PENALTY = 1.05  # generation_config.json de Qwen2.5-14B/VL-7B; HF generate(do_sample=False) lo conserva


def parse_variant(spec):
    """'ref' | 'fast' | 'asr=fast,labels=fast' -> {pista: 'ref'|'fast'} (las no nombradas quedan en ref)."""
    if isinstance(spec, dict):
        out = {t: "ref" for t in TRACKS} | spec
    elif spec in (None, "", "ref"):
        out = {t: "ref" for t in TRACKS}
    elif spec == "fast":
        out = {t: "fast" for t in TRACKS}
    else:
        out = {t: "ref" for t in TRACKS}
        for part in spec.split(","):
            k, _, v = part.partition("=")
            out[k.strip()] = v.strip()
    for k, v in out.items():
        if k not in TRACKS or v not in ("ref", "fast", "fast_exact"):
            raise ValueError(f"variante inválida {k}={v}; pistas {TRACKS}, valores ref|fast")
    return out


def suffix(v):
    return "" if v == "ref" else f".{v}"


# ---- decode-once --------------------------------------------------------------------------------------------

def decode_once(video, out_dir, fps=1):
    """Decodifica el video una sola vez a `fps` fotogramas/s (448 px de ancho, como `_frame`)."""
    out_dir = Path(out_dir)
    done = out_dir / ".done"
    if not done.exists():
        out_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps={fps},scale=448:-2",
                        "-start_number", "0", str(out_dir / "f%06d.jpg")], check=True, capture_output=True)
        done.write_text("ok")
    return out_dir


class FrameIndex:
    """Fotograma 1 fps más cercano a t (empate hacia el anterior)."""

    def __init__(self, out_dir):
        self.dir = Path(out_dir)
        self.n = len(list(self.dir.glob("f*.jpg")))

    def path(self, t):
        if self.n == 0:
            return None
        k = min(max(math.ceil(t - 0.5), 0), self.n - 1)
        p = self.dir / f"f{k:06d}.jpg"
        return p if p.exists() and p.stat().st_size > 0 else None


# ---- vLLM (API compatible con OpenAI) -----------------------------------------------------------------------

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _chat(url, model, messages, max_tokens, retries=3):
    body = json.dumps({"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0,
                       "repetition_penalty": REPETITION_PENALTY}).encode()
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(url + "/chat/completions", body, {"Content-Type": "application/json"})
            with _opener.open(req, timeout=900) as r:
                return json.loads(r.read())["choices"][0]["message"]["content"] or ""
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"vLLM {url} falló tras {retries} intentos: {last}")


def chat_many(url, model, conversations, max_tokens, workers=64):
    """Todas las peticiones de un video en lote; el servidor agrupa por su cuenta (batching continuo)."""
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(lambda m: _chat(url, model, m, max_tokens), conversations))


def png_data_url(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
