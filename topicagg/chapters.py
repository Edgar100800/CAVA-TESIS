"""Nivel de capítulo sobre el mapa CAVA (EXP-033): capítulos contiguos con las N fronteras más fuertes del mapa.

Fuerza de una frontera del mapa = media, sobre las señales, del rango percentil de la puntuación de frontera
propia de cada señal en ese índice (votos por señal; ADR-0001). N = round(duración / L), sin GT.
"""
import numpy as np

from .multimodal_manager import signal_boundary


def boundary_strength(signals: dict[str, np.ndarray], n: int) -> np.ndarray:
    ranks = []
    for embs in signals.values():
        s = signal_boundary(np.asarray(embs, np.float32)[:n])
        ranks.append(np.argsort(np.argsort(s)) / max(len(s) - 1, 1))
    return np.mean(ranks, 0)


def top_n_boundaries(cands: np.ndarray, strength: np.ndarray, n_keep: int, min_gap: int = 2) -> list[int]:
    keep: list[int] = []
    for b in cands[np.argsort(-strength[cands], kind="stable")]:
        if len(keep) >= n_keep:
            break
        if all(abs(int(b) - k) >= min_gap for k in keep):
            keep.append(int(b))
    return sorted(keep)


def labels_from_boundaries(n: int, bounds: list[int]) -> np.ndarray:
    lab = np.zeros(n, int)
    for b in bounds:          # frontera b = entre la unidad b y b+1
        lab[b + 1:] += 1
    return lab


def chapters(map_labels: np.ndarray, signals: dict[str, np.ndarray], duration_s: float, L: float) -> np.ndarray:
    lab = np.asarray(map_labels)
    n = len(lab)
    cands = np.where(lab[1:] != lab[:-1])[0]
    n_keep = max(0, int(round(duration_s / L)) - 1)
    return labels_from_boundaries(n, top_n_boundaries(cands, boundary_strength(signals, n), n_keep))
