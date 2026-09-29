"""Gestor multimodal de tópicos (v2.1) — SIN FUSIÓN DE REPRESENTACIONES.

Principio (lección v1): fusionar señales en un embedding/score único re-escribe
unas señales con otras antes de decidir. Aquí cada señal decide POR SU CUENTA y
el tópico emerge por CONSENSO DE VOTOS:

  1) por señal: scores de frontera propios + cortes propios (percentil propio)
  2) frontera confirmada si ≥ quorum de señales votan corte en ±tol bins
  3) por señal: etiquetas de tópico por segmento (sus propios cortes). Con
     `return_percentile`, cada señal de embeddings puede además devolver un
     segmento suyo posterior a un tópico suyo anterior ("el tema se retoma"),
     por su propio percentil de similitud: tópicos NO contiguos por señal.
  4) enlace (i,j) mismo tópico si ≥ quorum de señales los agrupan juntos
     (componentes conexas) — grupos con PROVENANCE: qué señales soportan cada uno

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
        if score[i] < thr or score[i] <= 0:  # score 0 = la señal no ve nada
            break
        if all(abs(int(i) + 1 - c) >= min_gap for c in cuts):  # cut = i+1
            cuts.append(int(i) + 1)
    return sorted(cuts)


def _collapse_runs(passing: np.ndarray, votes: np.ndarray) -> list[int]:
    """Una racha contigua de índices que pasan el quorum = un solo corte, en el
    pico de votos (empate: centro de la meseta)."""
    cuts, i, m = [], 0, len(passing)
    while i < m:
        if not passing[i]:
            i += 1
            continue
        j = i
        while j + 1 < m and passing[j + 1]:
            j += 1
        run = np.arange(i, j + 1)
        peak = run[votes[run] == votes[run].max()]
        cuts.append(int(peak[len(peak) // 2]))
        i = j + 1
    return cuts


def _return_labels(embs: np.ndarray, cuts: list[int], pct: float) -> np.ndarray:
    """Etiquetas de tópico de UNA señal permitiendo retornos no contiguos.

    Segmentos = tramos entre los cortes propios de la señal. En orden temporal,
    cada segmento se une al tópico anterior con el que tenga mayor similitud
    (coseno máximo a cualquiera de sus segmentos) si esa similitud está en el
    percentil `pct` de las similitudes entre segmentos no adyacentes de ESTA
    señal; si no, abre tópico nuevo. Nunca vuelve al tópico del que se acaba de
    cortar (su último segmento es el inmediatamente anterior), y cada segmento
    se une a un solo tópico existente (sin fusionar tópicos entre sí).
    Segmentos sin evidencia (filas nulas) no se enlazan."""
    n = len(embs)
    bounds = [0] + sorted(cuts) + [n]
    x = _l2(np.asarray(embs, dtype=np.float32))
    cents = []
    for a, b in zip(bounds, bounds[1:]):
        rows = x[a:b][np.linalg.norm(x[a:b], axis=1) > 0]
        c = rows.mean(axis=0) if len(rows) else None
        cents.append(c / np.linalg.norm(c) if c is not None and np.linalg.norm(c) > 0 else None)
    m = len(cents)
    ok = [k for k in range(m) if cents[k] is not None]
    seg_topic = np.full(m, -1, dtype=np.int64)
    if len(ok) >= 3:
        C = np.stack([cents[k] for k in ok])
        S = C @ C.T
        pos = {k: i for i, k in enumerate(ok)}
        vals = [S[pos[a], pos[b]] for a in ok for b in ok if b < a - 1]
        thr = float(np.percentile(vals, pct)) if vals else np.inf
    else:
        S, pos, thr = None, {}, np.inf
    topics: list[list[int]] = []
    for k in range(m):
        best, best_s = None, -np.inf
        if cents[k] is not None and S is not None:
            for t, members in enumerate(topics):
                if members[-1] == k - 1:
                    continue
                sims = [S[pos[k], pos[j]] for j in members if j in pos]
                if sims and max(sims) > best_s:
                    best, best_s = t, max(sims)
        if best is not None and best_s >= thr:
            topics[best].append(k)
            seg_topic[k] = best
        else:
            topics.append([k])
            seg_topic[k] = len(topics) - 1
    labels = np.zeros(n, dtype=np.int64)
    for k, (a, b) in enumerate(zip(bounds, bounds[1:])):
        labels[a:b] = seg_topic[k]
    return labels


@dataclass
class TopicPlan:
    n_segments: int
    consensus_cuts: list[int]
    per_signal_cuts: dict
    labels: np.ndarray
    groups: list
    quorum: int
    weights: dict
    cut_quorum: int | None = None
    per_signal_boundary: dict = field(default_factory=dict)
    per_signal_labels: dict = field(default_factory=dict)


def manage(signals: dict[str, np.ndarray], *,
           speech_times: list[list[float]] | None = None,
           n_segments: int | None = None,
           weights: dict | None = None,
           percentile: float = 80.0,
           min_gap: int = 2,
           link_quorum: int = 2,   # señales que deben coincidir para enlazar
           max_group_segments: int = 10,  # ticket 001: >N segs = needs_review
           cut_quorum: int | None = None,  # señales que deben votar un corte
                                          # (None = mayoría ponderada; int = intersección)
           tolerance_bins: int = 1,
           boundary_signals: dict[str, np.ndarray] | None = None,
           return_percentile: float | None = None) -> TopicPlan:
    """signals: {nombre: [n, D]} embeddings POR SEÑAL (nunca fusionados).
    link_quorum: nº de señales que deben agrupar un par para enlazarlo.
    boundary_signals: {nombre: score[n-1]} votantes que solo aportan fronteras
      (p. ej. SegLoop): cortes por su propio percentil, etiquetas contiguas.
    return_percentile: None = etiquetas por señal contiguas (v2.1). Con valor,
      cada señal de embeddings permite retornos de tópico (ver _return_labels)."""
    n = n_segments or min(len(v) for v in signals.values())
    signals = {k: np.asarray(v, dtype=np.float32)[:n] for k, v in signals.items()}
    w = {"transcript": 1.0, "visual": 1.0, "ocr": 1.0, "audio": 0.5, **(weights or {})}

    per_boundary, per_cuts, per_labels = {}, {}, {}
    for name, embs in signals.items():
        s = signal_boundary(embs)
        per_boundary[name] = s
        per_cuts[name] = _signal_cuts(s, percentile, min_gap)
        if return_percentile is not None:
            per_labels[name] = _return_labels(embs, per_cuts[name], return_percentile)
        else:
            per_labels[name] = segment_topic_labels(np.zeros((n, 1)),
                                                    per_cuts[name]) if per_cuts[name] \
                else np.zeros(n, dtype=np.int64)
    for name, score in (boundary_signals or {}).items():
        s = np.asarray(score, dtype=np.float32)[:max(0, n - 1)]
        mx = s.max() if len(s) else 0.0
        s = s / mx if mx > 0 else s
        per_boundary[name] = s
        per_cuts[name] = _signal_cuts(s, percentile, min_gap)
        per_labels[name] = segment_topic_labels(np.zeros((n, 1)), per_cuts[name]) \
            if per_cuts[name] else np.zeros(n, dtype=np.int64)
    if speech_times is not None:
        s = speech_density_boundaries(speech_times, n)
        per_boundary["audio"] = s
        per_cuts["audio"] = _signal_cuts(s, percentile, min_gap)
        per_labels["audio"] = segment_topic_labels(np.zeros((n, 1)),
                                                   per_cuts["audio"]) \
            if per_cuts["audio"] else np.zeros(n, dtype=np.int64)
        w.setdefault("audio", 0.5)

    # consenso de fronteras: votos ponderados en ±tolerance_bins.
    # Cada señal vota como mucho una vez por índice (presence), y cada racha de
    # índices contiguos que alcanza el quorum colapsa en UN corte (pico de votos).
    presence = {name: np.zeros(max(0, n - 1), dtype=bool)
                for name in per_cuts}
    for name, cuts in per_cuts.items():
        for c in cuts:
            lo = max(0, c - tolerance_bins)
            hi = min(len(presence[name]), c + tolerance_bins + 1)
            presence[name][lo:hi] = True
    votes = np.zeros(max(0, n - 1), dtype=np.float32)
    cnt = np.zeros(max(0, n - 1), dtype=np.float32)
    for name, pres in presence.items():
        votes += w.get(name, 1.0) * pres
        cnt += pres
    total_w = sum(w.get(k, 1.0) for k in per_cuts) or 1.0
    if cut_quorum is not None:
        passing = cnt >= cut_quorum
    else:
        majority = max(1.0, int(np.ceil(total_w / 2)))  # mayoría de señales activas
        passing = votes >= majority
    consensus = _collapse_runs(passing, votes)

    # consenso de enlace: quorum de señales agrupando el par -> componentes conexas
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    V = np.zeros((n, n), dtype=np.float32)
    for name, labs in per_labels.items():
        V += w.get(name, 1.0) * (labs[:, None] == labs[None, :])
    np.fill_diagonal(V, 0.0)
    _, comp_id = connected_components(csr_matrix(V >= link_quorum), directed=False)
    comp: dict[int, list[int]] = {}
    for i in range(n):
        comp.setdefault(int(comp_id[i]), []).append(i)

    groups = []
    for gid, root in enumerate(sorted(comp, key=lambda r: comp[r][0])):
        members = comp[root]
        support = {}
        for name, labs in per_labels.items():
            _, inv, counts = np.unique(labs[members], return_inverse=True, return_counts=True)
            inside = int((counts[inv] > 1).sum())  # miembros que comparten etiqueta con otro
            support[name] = round(inside / len(members), 3)
        g = TopicGroup(topic_id=gid, segment_indices=sorted(members),
                       centroid=np.zeros(1), coherence=0.0)
        g.signal_support = support
        # Ticket 001 (resuelto): criterios de tópico correcto
        # - singleton sin NINGÚN soporte multi-señal -> SIN TÓPICO (no es contenido)
        # - grupo largo (> max_group_segments) -> válido pero needs_review
        max_support = max(support.values()) if support else 0.0
        if len(members) == 1 and max_support == 0.0:
            g.no_topic = True
        if len(members) > max_group_segments:
            g.needs_review = True
        groups.append(g)

    first = {cid: min(ms) for cid, ms in comp.items()}
    labels = np.array([first[int(comp_id[i])] for i in range(n)])
    return TopicPlan(n_segments=n, consensus_cuts=consensus,
                     per_signal_cuts=per_cuts, labels=labels, groups=groups,
                     quorum=max(1, int(np.ceil(0.5 * len(per_cuts)))),
                     cut_quorum=cut_quorum,
                     weights=w, per_signal_boundary=per_boundary,
                     per_signal_labels=per_labels)
