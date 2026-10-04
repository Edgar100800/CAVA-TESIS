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
    provenance   por señal: agreement (fracción de pares de shots del tópico que
                 la señal pone en su mismo tópico propio), support (v2.1:
                 fracción de shots que comparten etiqueta con otro) y coherencia
                 leave-one-out de sus embeddings
    flags        no_topic / needs_review (ticket 001)
    context      por tramo (clip): qué vio el VJudge (resúmenes de las unidades
                 que solapan el tramo) y qué se dice (diálogo de esos shots).
                 Sale de las señales propias de CAVA, no de GT.
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


def _agreement(labels: np.ndarray, members: list[int]) -> float | None:
    if len(members) < 2:
        return None
    lab = labels[members]
    _, counts = np.unique(lab, return_counts=True)
    same = float((counts * (counts - 1)).sum()) / 2
    return round(same / (len(members) * (len(members) - 1) / 2), 3)


def _span_context(a, b, unit_summaries, unit_texts):
    seen = []
    for u in unit_summaries or []:
        if u["lo"] <= b and u["hi"] > a and u["summary"] not in seen:
            seen.append(u["summary"])
    lines = []
    for k in range(a, b + 1):
        if unit_texts and k < len(unit_texts) and unit_texts[k] and unit_texts[k] not in lines:
            lines.append(unit_texts[k])
    return {"seen": seen, "said": " ".join(lines)[:1500]}


def topics_from_plan(plan: TopicPlan, shot_times: list[list[float]],
                     signals: dict[str, np.ndarray],
                     unit_summaries: list[dict] | None = None,
                     unit_texts: list[str] | None = None) -> list[dict]:
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
            "provenance": {k: {"agreement": _agreement(plan.per_signal_labels[k], members),
                               "support": g.signal_support.get(k),
                               "coherence": _coherence(signals[k], members)
                               if k in signals else None}
                           for k in g.signal_support},
            "flags": {"no_topic": bool(getattr(g, "no_topic", False)),
                      "needs_review": bool(getattr(g, "needs_review", False))},
            "context": [_span_context(a, b, unit_summaries, unit_texts) for a, b in spans],
        })
    out.sort(key=lambda t: t["shots"][0])
    return out


def snap_boundaries(lab: np.ndarray, ref_lab: np.ndarray, ends: np.ndarray, R: float) -> np.ndarray:
    """EXP-027: mueve cada frontera de `lab` a la frontera de `ref_lab` (la señal visual)
    más cercana si está a <= R segundos; las unidades intermedias pasan al tópico del
    lado que se extiende. Usa las fronteras de UNA señal, no fusiona representaciones."""
    lab = np.asarray(lab).copy()
    ref_lab = np.asarray(ref_lab)
    vb = np.where(ref_lab[1:] != ref_lab[:-1])[0]
    if not len(vb):
        return lab
    for b in np.where(lab[1:] != lab[:-1])[0]:
        k = vb[np.argmin(np.abs(ends[vb] - ends[b]))]
        if k != b and abs(ends[k] - ends[b]) <= R:
            if k > b:
                lab[b + 1:k + 1] = lab[b]
            else:
                lab[k + 1:b + 1] = lab[b + 1]
    return lab


def _apply_snap(plan, new_labels):
    """Reasigna los miembros de cada grupo según las etiquetas tras el snap y recalcula el soporte."""
    by_label = {int(min(g.segment_indices)): g for g in plan.groups}
    groups = []
    for lv, g in by_label.items():
        members = [int(i) for i in np.where(new_labels == lv)[0]]
        if not members:
            continue
        g.segment_indices = members
        support = {}
        for name, labs in plan.per_signal_labels.items():
            lm = labs[members]
            _, inv, counts = np.unique(lm, return_inverse=True, return_counts=True)
            support[name] = round(int(((counts[inv] > 1) & (lm >= 0)).sum()) / len(members), 3)
        g.signal_support = support
        groups.append(g)
    plan.groups = groups
    plan.labels = new_labels
    return plan


def build_topic_map(video_id: str, signals: dict[str, np.ndarray],
                    shot_times: list[list[float]], *,
                    unit_summaries: list[dict] | None = None,
                    boundary_signals: dict[str, np.ndarray] | None = None,
                    percentile: float = 80, return_percentile: float = 90,
                    link_quorum: int = 2, abstain: bool = False,
                    unit_texts: list[str] | None = None,
                    snap_visual_s: float | None = None) -> dict:
    """Mapa de tópicos en dos granularidades con los parámetros pre-registrados
    de EXP-017b (percentile 80, return_percentile 90, link_mode average).
    snap_visual_s: EXP-027, fronteras ajustadas a las de la señal visual a <= R s
    (None = sin snap; validado en film y documental con R = 30, no en reuniones)."""
    n = min(len(v) for v in signals.values())
    n = min(n, len(shot_times))
    signals = {k: np.asarray(v, np.float32)[:n] for k, v in signals.items()}
    n_voters = len(signals) + len(boundary_signals or {})
    levels = {"default": link_quorum, "fine": max(link_quorum, n_voters)}
    doc = {"video_id": video_id, "n_units": n,
           "duration_s": round(shot_times[n - 1][1] - shot_times[0][0], 2),
           "signals": sorted(signals) + sorted(boundary_signals or {}),
           "unit_times": [[round(a, 2), round(b, 2)] for a, b in shot_times[:n]],
           "params": {"percentile": percentile, "return_percentile": return_percentile,
                      "link_mode": "average", "abstain": abstain, "quorum_by_level": levels,
                      "snap_visual_s": snap_visual_s if "visual" in signals else None},
           "levels": {}}
    for name, q in levels.items():
        plan = manage(signals, n_segments=n, percentile=percentile, link_quorum=q,
                      return_percentile=return_percentile, link_mode="average",
                      boundary_signals=boundary_signals, abstain=abstain)
        if snap_visual_s and "visual" in signals:
            ref = manage({"visual": signals["visual"]}, n_segments=n, percentile=percentile, link_quorum=1,
                         return_percentile=return_percentile, link_mode="average", abstain=abstain).labels
            ends = np.array([b for _, b in shot_times[:n]], float)
            plan = _apply_snap(plan, snap_boundaries(plan.labels, ref, ends, snap_visual_s))
        topics = topics_from_plan(plan, shot_times, signals, unit_summaries, unit_texts)
        doc["levels"][name] = {"n_topics": len(topics),
                               "n_returning": sum(1 for t in topics if t["returns"]),
                               "topics": topics}
    return doc
