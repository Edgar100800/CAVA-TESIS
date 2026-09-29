"""Mapa de tópicos de un video: la salida de CAVA que consumen los formatos.

Toma los planes de `manage()` (retornos + consenso promedio, sin fusión) y
produce un documento JSON-serializable:

  video       id, nº de unidades, duración
  levels      granularidades del mismo video: "fine" (quorum = todas las
              señales: tópicos cortos) y "default" (quorum 2: tópicos largos)
  topics      por nivel, cada tópico con:
    shots        índices de unidad (pueden ser NO contiguos: el tema se retoma)
    spans        tramos contiguos [t0, t1] en segundos
    duration_s   suma de los tramos
    returns      nº de veces que el tópico reaparece tras una ausencia
    label        resumen VJudge de la unidad que más shots aporta al tópico
    provenance   por señal: soporte (fracción de shots que la señal agrupa con
                 otro shot del tópico) y coherencia (coseno intra − inter)
    flags        no_topic / needs_review (ticket 001)
Ninguna señal se fusiona: la provenance muestra cuáles sostienen cada tópico.
"""
from __future__ import annotations

import numpy as np

from .multimodal_manager import TopicPlan, manage


def _spans(shots: list[int]) -> list[tuple[int, int]]:
    runs, start, prev = [], shots[0], shots[0]
    for s in shots[1:]:
        if s != prev + 1:
            runs.append((start, prev))
            start = s
        prev = s
    runs.append((start, prev))
    return runs


def _coherence(x: np.ndarray, members: list[int]) -> float | None:
    rows = x[members]
    rows = rows[np.linalg.norm(rows, axis=1) > 0]
    if len(rows) < 2:
        return None
    rows = rows / np.linalg.norm(rows, axis=1, keepdims=True)
    c = rows.sum(0)
    rest = c[None, :] - rows
    rest /= np.linalg.norm(rest, axis=1, keepdims=True) + 1e-8
    return float((rows * rest).sum(1).mean())  # leave-one-out, sin inflar


def topics_from_plan(plan: TopicPlan, shot_times: list[list[float]],
                     signals: dict[str, np.ndarray],
                     unit_summaries: list[dict] | None = None) -> list[dict]:
    out = []
    for g in plan.groups:
        members = sorted(g.segment_indices)
        spans = _spans(members)
        label = None
        if unit_summaries:
            counts = {}
            for u_i, u in enumerate(unit_summaries):
                k = sum(1 for m in members if u["lo"] <= m < u["hi"])
                if k:
                    counts[u_i] = k
            if counts:
                label = unit_summaries[max(counts, key=counts.get)]["summary"]
        out.append({
            "topic_id": int(g.topic_id),
            "shots": members,
            "spans": [[round(shot_times[a][0], 2), round(shot_times[b][1], 2)] for a, b in spans],
            "duration_s": round(sum(shot_times[b][1] - shot_times[a][0] for a, b in spans), 2),
            "returns": len(spans) - 1,
            "label": label,
            "provenance": {k: {"support": g.signal_support.get(k),
                               "coherence": _coherence(signals[k], members)
                               if k in signals else None}
                           for k in g.signal_support},
            "flags": {"no_topic": bool(getattr(g, "no_topic", False)),
                      "needs_review": bool(getattr(g, "needs_review", False))},
        })
    out.sort(key=lambda t: t["shots"][0])
    return out


def build_topic_map(video_id: str, signals: dict[str, np.ndarray],
                    shot_times: list[list[float]], *,
                    unit_summaries: list[dict] | None = None,
                    boundary_signals: dict[str, np.ndarray] | None = None,
                    percentile: float = 80, return_percentile: float = 90,
                    link_quorum: int = 2) -> dict:
    """Mapa de tópicos en dos granularidades con los parámetros pre-registrados
    de EXP-017b (percentile 80, return_percentile 90, link_mode average)."""
    n = min(len(v) for v in signals.values())
    n = min(n, len(shot_times))
    signals = {k: np.asarray(v, np.float32)[:n] for k, v in signals.items()}
    n_voters = len(signals) + len(boundary_signals or {})
    levels = {"default": link_quorum, "fine": max(link_quorum, n_voters)}
    doc = {"video_id": video_id, "n_units": n,
           "duration_s": round(shot_times[n - 1][1] - shot_times[0][0], 2),
           "signals": sorted(signals) + sorted(boundary_signals or {}),
           "params": {"percentile": percentile, "return_percentile": return_percentile,
                      "link_mode": "average", "quorum_by_level": levels},
           "levels": {}}
    for name, q in levels.items():
        plan = manage(signals, n_segments=n, percentile=percentile, link_quorum=q,
                      return_percentile=return_percentile, link_mode="average",
                      boundary_signals=boundary_signals)
        topics = topics_from_plan(plan, shot_times, signals, unit_summaries)
        doc["levels"][name] = {"n_topics": len(topics),
                               "n_returning": sum(1 for t in topics if t["returns"]),
                               "topics": topics}
    return doc
