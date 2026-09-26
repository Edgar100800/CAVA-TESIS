"""Agregador de tópicos: ENLAZA segmentos no adyacentes del mismo tema.

El mecanismo que resuelve el caso TPU: un sub-segmento temprano y otro tardío
sobre el mismo tema quedan agrupados en un `TopicGroup` aunque estén separados
en el tiempo — por similitud de sus embeddings temáticos (transcript/OCR), no
por adyacencia temporal ni por cortes visuales.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

from .topic_segmenter import segment_topic_labels


@dataclass
class TopicGroup:
    topic_id: int
    segment_indices: list[int]          # índices de sub-segmento (no adyacentes ok)
    centroid: np.ndarray
    coherence: float                    # sim coseno media intra-grupo
    representative_sentences: list[str] = field(default_factory=list)


def topic_centroids(embs: np.ndarray, labels: np.ndarray) -> dict[int, np.ndarray]:
    out = {}
    for t in np.unique(labels):
        c = embs[labels == t].mean(axis=0)
        n = np.linalg.norm(c)
        out[int(t)] = c / n if n > 0 else c
    return out


def _coherence(embs: np.ndarray, idx: list[int], centroid: np.ndarray) -> float:
    if len(idx) < 2:
        return 1.0
    x = embs[idx] / (np.linalg.norm(embs[idx], axis=1, keepdims=True) + 1e-8)
    return float((x @ centroid).mean())


def aggregate_by_topic(embs: np.ndarray, cuts: list[int], *,
                       link_threshold: float = 0.55) -> list[TopicGroup]:
    """Agrupa sub-segmentos por tópico.

    1) segmenta por cortes (contiguo), 2) calcula centroides de cada tópico,
    3) ENLAZA sub-segmentos no adyacentes cuyo embedding esté a coseno >=
    `link_threshold` del centroide de un tópico existente (conecta el "se retoma
    el tema" a través del tiempo).
    """
    labels = segment_topic_labels(embs, cuts)
    centroids = topic_centroids(embs, labels)
    groups: dict[int, list[int]] = {t: [] for t in centroids}
    outliers: list[int] = []

    for i in range(len(embs)):
        x = embs[i] / (np.linalg.norm(embs[i]) + 1e-8)
        best_t, best_s = None, -1.0
        for t, c in centroids.items():
            s = float(x @ c)
            if s > best_s:
                best_t, best_s = t, s
        if best_s >= link_threshold:
            groups[best_t].append(i)
        else:
            outliers.append(i)

    out = []
    for t in sorted(groups):
        idx = sorted(groups[t])
        if not idx:
            continue
        c = centroids[t]
        out.append(TopicGroup(
            topic_id=t, segment_indices=idx, centroid=c,
            coherence=_coherence(embs, idx, c)))
    if outliers:
        out.append(TopicGroup(topic_id=-1, segment_indices=sorted(outliers),
                              centroid=np.zeros(embs.shape[1], dtype=np.float32),
                              coherence=0.0,
                              representative_sentences=[]))
    return [g for g in out if g.topic_id != -1 or len(g.segment_indices) >= 2]
