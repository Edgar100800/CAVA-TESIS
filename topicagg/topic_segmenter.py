"""Segmentador temático por desplazamiento de embeddings (señal text-side).

Detección de fronteras TEMÁTICAS (no visuales): un corte entre sub-segmentos i
y i+1 es candidato cuando la similitud coseno entre el contexto-izquierdo y el
contexto-derecho cae por debajo de un umbral adaptativo (percentil de la serie).
Requiere embeddings por sub-segmento (paso 2s) — v2.0 usa transcript; las otras
señales se agregan con el mismo mecanismo cuando existan.
"""
from __future__ import annotations
import numpy as np


def _centroid_window(embs: np.ndarray, center: int, w: int) -> np.ndarray | None:
    lo, hi = max(0, center - w), min(len(embs), center + w)
    if hi - lo < 2:
        return None
    c = embs[lo:hi].mean(axis=0)
    n = np.linalg.norm(c)
    return c / n if n > 0 else None


def boundary_scores(embs: np.ndarray, w: int = 3) -> np.ndarray:
    """Score de frontera temática entre sub-segmento i-1 e i, para i=1..n-1
    (distancia coseno entre centroides de ventana izquierda/derecha)."""
    n = len(embs)
    out = np.zeros(max(0, n - 1), dtype=np.float32)
    for i in range(1, n):
        L = _centroid_window_left(embs, i, w)     # ventana que termina en i-1
        R = _centroid_window_right(embs, i, w)    # ventana que empieza en i
        if L is None or R is None:
            out[i - 1] = 0.0
            continue
        out[i - 1] = float(1.0 - float(L @ R))
    return out


def _centroid_window_right(embs, i, w):
    lo, hi = i, min(len(embs), i + w)
    if hi - lo < 1:
        return None
    c = embs[lo:hi].mean(axis=0)
    n = np.linalg.norm(c)
    return c / n if n > 0 else None


def _centroid_window_left(embs, i, w):
    lo, hi = max(0, i - w), i
    if hi - lo < 1:
        return None
    c = embs[lo:hi].mean(axis=0)
    n = np.linalg.norm(c)
    return c / n if n > 0 else None


def detect_boundaries(embs: np.ndarray, w: int = 3, percentile: float = 80.0,
                      min_gap: int = 3) -> list[int]:
    """Cortes temáticos = picos del score por encima del percentil dado,
    con separación mínima `min_gap` sub-segmentos."""
    s = boundary_scores(embs, w)
    if len(s) == 0:
        return []
    thr = np.percentile(s, percentile)
    cuts: list[int] = []
    last = -10**9
    for i in np.argsort(-s):
        if s[i] < thr:
            break
        if all(abs(i - c) >= min_gap for c in cuts):
            cuts.append(int(i) + 1)   # frontera ANTES del sub-segmento i
            if len(cuts) >= max(1, len(s) // min_gap):
                break
    return sorted(cuts)


def segment_topic_labels(embs: np.ndarray, cuts: list[int]) -> np.ndarray:
    """Asigna id de tópico (0,1,2,...) a cada sub-segmento según los cortes."""
    labels = np.zeros(len(embs), dtype=np.int64)
    for i in cuts:
        labels[i:] += 1
    return labels
