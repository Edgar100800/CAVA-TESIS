"""Gestor multimodal de tópicos (v2.1) — SIN FUSIÓN DE REPRESENTACIONES.

Principio (lección v1): fusionar señales en un embedding/score único re-escribe
unas señales con otras antes de decidir. Aquí cada señal decide POR SU CUENTA y
el tópico emerge por CONSENSO DE VOTOS:

  1) por señal: scores de frontera propios + cortes propios (percentil propio)
  2) frontera confirmada si ≥ quorum de señales votan corte en ±tol bins
  3) por señal: etiquetas de tópico por segmento (sus propios cortes)
  4) enlace (i,j) mismo tópico si ≥ quorum de señales los agrupan juntos
     (union-find) — grupos con PROVENANCE: qué señales soportan cada uno

Sin embeddings fusionados. Sin scores fusionados. Identidad de señal preservada.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from .topic_segmenter import boundary_scores, segment_topic_labels
from .topic_aggregator import TopicGroup


def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / (n + 1e-8)


def signal_boundary(embs: np.ndarray, w: int = 2) -> np.ndarray:
    s = boundary_scores(_l2(np.asarray(embs, dtype=np.float32)), w=w)
    mx = s.max()
    return s / mx if mx > 0 else s


def speech_density_boundaries(times: list[list[float]], n_bins: int,
                              bin_s: float = 2.0) -> np.ndarray:
    """Señal audio-lite: caída de densidad de habla = pausa = cambio de tema."""
    dens = np.zeros(n_bins, dtype=np.float32)
    for a, b in times:
        i0 = int(a / bin_s); i1 = min(int(np.ceil(b / bin_s)), n_bins)
        if i1 > i0:
            dens[i0:i1] += 1.0
    s = np.zeros(max(0, n_bins - 1), dtype=np.float32)
    for i in range(1, n_bins):
        s[i - 1] = max(0.0, dens[i - 1] - dens[i])
    mx = s.max()
    return s / mx if mx > 0 else s


def _signal_cuts(score: np.ndarray, percentile: float, min_gap: int) -> list[int]:
    if len(score) == 0:
        return []
    thr = np.percentile(score, percentile)
    cuts: list[int] = []
    for i in np.argsort(-score):
        if score[i] < thr:
            break
        if all(abs(int(i) - c) >= min_gap for c in cuts):
            cuts.append(int(i) + 1)
    return sorted(cuts)


@dataclass
class TopicPlan:
    n_segments: int
    consensus_cuts: list[int]
    per_signal_cuts: dict
    labels: np.ndarray
    groups: list
    quorum: int
    weights: dict
    per_signal_boundary: dict = field(default_factory=dict)
    per_signal_labels: dict = field(default_factory=dict)


def manage(signals: dict[str, np.ndarray], *,
           speech_times: list[list[float]] | None = None,
           n_segments: int | None = None,
           weights: dict | None = None,
           percentile: float = 80.0,
           min_gap: int = 2,
           link_quorum: int = 2,   # señales que deben coincidir para enlazar
           tolerance_bins: int = 1) -> TopicPlan:
    """signals: {nombre: [n, D]} embeddings POR SEÑAL (nunca fusionados).
    link_quorum: nº de señales que deben agrupar un par para enlazarlo."""
    n = n_segments or min(len(v) for v in signals.values())
    signals = {k: np.asarray(v, dtype=np.float32)[:n] for k, v in signals.items()}
    w = {"transcript": 1.0, "visual": 1.0, "ocr": 1.0, "audio": 0.5, **(weights or {})}

    per_boundary, per_cuts, per_labels = {}, {}, {}
    for name, embs in signals.items():
        s = signal_boundary(embs)
        per_boundary[name] = s
        per_cuts[name] = _signal_cuts(s, percentile, min_gap)
        per_labels[name] = segment_topic_labels(np.zeros((n, 1)),
                                                per_cuts[name]) if per_cuts[name] \
            else np.zeros(n, dtype=np.int64)
    if speech_times is not None:
        s = speech_density_boundaries(speech_times, n)
        per_boundary["audio"] = s
        per_cuts["audio"] = _signal_cuts(s, percentile, min_gap)
        per_labels["audio"] = segment_topic_labels(np.zeros((n, 1)),
                                                   per_cuts["audio"]) \
            if per_cuts["audio"] else np.zeros(n, dtype=np.int64)
        w.setdefault("audio", 0.5)

    # consenso de fronteras: votos ponderados en ±tolerance_bins
    votes = np.zeros(max(0, n - 1), dtype=np.float32)
    for name, cuts in per_cuts.items():
        for c in cuts:
            lo = max(0, c - tolerance_bins)
            hi = min(len(votes), c + tolerance_bins + 1)
            votes[lo:hi] += w.get(name, 1.0)
    total_w = sum(w.get(k, 1.0) for k in per_cuts) or 1.0
    majority = max(1.0, int(np.ceil(total_w / 2)))   # mayoría de señales activas
    consensus = [int(i) for i in range(len(votes))
                 if votes[i] >= majority]

    # consenso de enlace: quorum de señales agrupando el par (union-find)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    link_votes: dict[tuple, float] = defaultdict(float)
    for name, labs in per_labels.items():
        root_members: dict[int, list[int]] = defaultdict(list)
        for i, lab in enumerate(labs):
            root_members[int(lab)].append(i)
        for lab, members in root_members.items():
            wsig = w.get(name, 1.0)
            for a_i, i in enumerate(members):
                for j in members[a_i + 1:]:
                    link_votes[(min(i, j), max(i, j))] += wsig

    for (i, j), v in link_votes.items():
        if v >= link_quorum:
            union(i, j)

    comp: dict[int, list[int]] = {}
    for i in range(n):
        comp.setdefault(find(i), []).append(i)

    groups = []
    for gid, root in enumerate(sorted(comp, key=lambda r: comp[r][0])):
        members = comp[root]
        support = {}
        for name, labs in per_labels.items():
            inside = sum(1 for i in members
                         if any(labs[i] == labs[j] for j in members if j != i))
            support[name] = round(inside / len(members), 3)
        g = TopicGroup(topic_id=gid, segment_indices=sorted(members),
                       centroid=np.zeros(1), coherence=0.0)
        g.signal_support = support
        groups.append(g)

    labels = np.array([find(i) for i in range(n)])
    return TopicPlan(n_segments=n, consensus_cuts=consensus,
                     per_signal_cuts=per_cuts, labels=labels, groups=groups,
                     quorum=max(1, int(np.ceil(0.5 * len(per_cuts)))),
                     weights=w, per_signal_boundary=per_boundary,
                     per_signal_labels=per_labels)
