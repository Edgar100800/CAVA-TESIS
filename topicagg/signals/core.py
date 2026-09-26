"""Señales multimodales para topicagg (v2).

Interfaces por señal. v2.0 implementa TRANSCRIPT completa (embeddings ya
extraídos, p.ej. RoBERTa de BLiSS) y deja contratos definidos para OCR,
AUDIO y VIDEO (se llenan con extracción real cuando haya GPU/videos).
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class SegmentSignal:
    """Señales de UN segmento temporal [t0, t1] del video."""
    t0: float
    t1: float
    transcript_embedding: np.ndarray | None = None   # [D_text]
    ocr_text_embedding: np.ndarray | None = None     # [D_text] (texto EN pantalla)
    ocr_raw: list[str] = field(default_factory=list)
    audio_embedding: np.ndarray | None = None        # [D_audio]
    video_embedding: np.ndarray | None = None        # [D_video]
    source: str = "segment"


class TranscriptSignal:
    """Transcript temporizado -> embeddings por segmento (IMPLEMENTADO).

    Los embeddings pueden venir pre-extraídos (RoBERTa de BLiSS) o de un
    encoder en línea; el segmentador solo necesita los vectores.
    """

    def __init__(self, sentences: list[str], times: list[list[float]],
                 embeddings):
        assert len(sentences) == len(times) == len(embeddings)
        self.sentences = sentences
        self.times = times
        self.emb = np.asarray(embeddings, dtype=np.float32)

    def segment_embeddings(self, t0: float, t1: float, step_s: float = 2.0):
        """Embedding por sub-segmento de `step_s` (media de sus sentencias)."""
        out_t, out_e = [], []
        t = t0
        while t < t1:
            t_next = min(t + step_s, t1)
            idx = [i for i, (a, b) in enumerate(self.times)
                   if a < t_next and b > t]
            if idx:
                out_t.append((t, t_next))
                out_e.append(self.emb[idx].mean(axis=0))
            t = t_next
        return out_t, np.asarray(out_e, dtype=np.float32)


class OcrSignal(Protocol):
    """Texto renderizado EN el frame (contrato v2.1 — motor por definir:
    tesseract / PaddleOCR / VLM-OCR). Misma interfaz que TranscriptSignal
    pero alimentado por muestreo de frames (k por segmento)."""
    def segment_embeddings(self, t0: float, t1: float, step_s: float = 2.0): ...


class AudioSignal(Protocol):
    """Audio del segmento (contrato v2.1 — whisper/ASR + eventos acústicos)."""
    def segment_embeddings(self, t0: float, t1: float, step_s: float = 2.0): ...


class VideoSignal(Protocol):
    """Video del segmento (contrato v2.1 — grid 2s + SigLIP/BaSSL o CLIP)."""
    def segment_embeddings(self, t0: float, t1: float, step_s: float = 2.0): ...
