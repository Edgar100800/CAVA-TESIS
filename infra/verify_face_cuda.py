#!/usr/bin/env python3
"""Smoke de buffalo_l: prepara los modelos y ejecuta un fotograma en CUDA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import onnxruntime as ort
from insightface.app import FaceAnalysis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frame", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=Path.home() / ".insightface")
    parser.add_argument("--det-size", type=int, default=640)
    args = parser.parse_args()

    frame = cv2.imread(str(args.frame))
    if frame is None:
        raise SystemExit(f"No se pudo leer el fotograma: {args.frame}")
    available = ort.get_available_providers()
    if "CUDAExecutionProvider" not in available:
        raise SystemExit(f"CUDAExecutionProvider no disponible: {available}")

    app = FaceAnalysis(
        name="buffalo_l", root=str(args.root),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )
    app.prepare(ctx_id=0, det_size=(args.det_size, args.det_size))
    faces = app.get(frame)
    session_providers = {
        name: model.session.get_providers() for name, model in app.models.items()
    }
    if any("CUDAExecutionProvider" not in providers for providers in session_providers.values()):
        raise SystemExit(f"Alguna sesión no registró CUDAExecutionProvider: {session_providers}")
    print(json.dumps({
        "available_providers": available,
        "session_providers": session_providers,
        "frame_shape": list(frame.shape),
        "detections": len(faces),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
