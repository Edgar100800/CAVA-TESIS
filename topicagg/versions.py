"""Versiones por consumidor a partir del mapa de tópicos (gate G-versión).

Perfiles (los del piloto CAVA + uno que solo existe con tópicos que retornan):
  full_chapters     un clip por tópico (su tramo más largo), en orden temporal:
                    vista completa del video capitulada por tema
  recap60           tramos más largos de los tópicos de mayor duración hasta 60 s
  highlights10pct   igual, con presupuesto = 10 % de la duración del video
  threads           los 3 tópicos con más retornos, cada uno como una playlist
                    que sigue ese hilo por todas sus apariciones (con tope de
                    duración por hilo)
Todos los clips son tramos de tópico, alineados a fronteras de unidad (shot):
nunca se corta dentro de un shot. Si el tramo más largo de un tópico no cabe en
el presupuesto restante, se recorta al prefijo de shots que sí cabe (en vez de
descartar el tópico).
"""
from __future__ import annotations


def _longest_span(topic):
    return max(topic["spans"], key=lambda s: s[1] - s[0])


def _clip(topic, span):
    return {"t0": span[0], "t1": span[1], "topic_id": topic["topic_id"],
            "label": topic["label"]}


def _trim(topic, span, room, unit_times):
    """Prefijo del tramo alineado a shots que cabe en `room` segundos."""
    if span[1] - span[0] <= room:
        return span
    end = None
    for u in sorted(topic["shots"]):
        a, b = unit_times[u]
        if a >= span[0] - 1e-6 and b <= span[1] + 1e-6:
            if b - span[0] > room:
                break
            end = b
    return [span[0], end] if end is not None else None


def _fill(topics, budget_s, unit_times):
    out, acc = [], 0.0
    for t in topics:
        s = _trim(t, _longest_span(t), budget_s - acc, unit_times)
        if s is None:
            continue
        out.append(_clip(t, s))
        acc += s[1] - s[0]
    return sorted(out, key=lambda c: c["t0"])


def build_versions(topic_map: dict, level: str = "default", *,
                   recap_s: float = 60.0, highlight_frac: float = 0.10,
                   n_threads: int = 3, thread_cap_frac: float = 0.10) -> dict:
    topics = [t for t in topic_map["levels"][level]["topics"] if not t["flags"]["no_topic"]]
    by_dur = sorted(topics, key=lambda t: -t["duration_s"])
    dur = topic_map["duration_s"]
    budgets = {"recap60": recap_s, "highlights10pct": highlight_frac * dur}
    versions = {
        "full_chapters": {"budget_s": None, "playlists": [
            sorted((_clip(t, _longest_span(t)) for t in topics), key=lambda c: c["t0"])]},
        "recap60": {"budget_s": budgets["recap60"], "playlists": [_fill(by_dur, budgets["recap60"], topic_map["unit_times"])]},
        "highlights10pct": {"budget_s": budgets["highlights10pct"],
                            "playlists": [_fill(by_dur, budgets["highlights10pct"], topic_map["unit_times"])]},
    }
    cap = thread_cap_frac * dur
    threads = []
    for t in sorted((t for t in topics if t["returns"] > 0),
                    key=lambda t: (-t["returns"], -t["duration_s"]))[:n_threads]:
        pl, acc = [], 0.0
        for s in t["spans"]:
            s = _trim(t, s, cap - acc, topic_map["unit_times"])
            if s is None:
                break
            pl.append(_clip(t, s))
            acc += s[1] - s[0]
        if pl:
            threads.append(pl)
    versions["threads"] = {"budget_s": cap, "playlists": threads}
    return versions


def check_versions(versions: dict) -> dict:
    """G-versión: cada perfil tiene ≥1 playlist no vacía y respeta su presupuesto."""
    report = {}
    for name, v in versions.items():
        pls = [p for p in v["playlists"] if p]
        totals = [round(sum(c["t1"] - c["t0"] for c in p), 2) for p in pls]
        within = v["budget_s"] is None or all(t <= v["budget_s"] + 1e-6 for t in totals)
        report[name] = {"n_playlists": len(pls), "total_s": totals,
                        "budget_s": v["budget_s"], "ok": bool(pls) and within}
    report["G_version"] = all(r["ok"] for k, r in report.items() if k != "G_version")
    return report
