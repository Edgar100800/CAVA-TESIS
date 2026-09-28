"""Agregador adaptativo por continuidad multimodal (EXP-011 paso 1) — SIN FUSIÓN.

La longitud del tópico no la fija un percentil global: emerge de dónde las
señales siguen viendo continuidad.

  1) SegLoop propone unidades finas (cortes `init_cuts`).
  2) Cada votante juzga cada par de unidades vecinas (A, B) por su cuenta:
       embeddings  continúa si  cross(A,B) >= rho * min(coh(A), coh(B))
                   coh(A)     = coseno medio leave-one-out de los shots de A
                   cross(A,B) = media de coseno de B al centroide de A y viceversa
                   B encaja con A tan bien como A consigo misma -> continúa.
                   Contenido homogéneo sigue fusionando; heterogéneo se detiene.
                   Sin evidencia (centroide nulo, p. ej. sin diálogo) -> se abstiene.
       fronteras   continúa si score(corte entre A y B) < umbral propio.
  3) Se fusiona el par si vota "continúa" una mayoría estricta de los votantes
     activos. Se repite con las unidades nuevas hasta que nada fusiona. Cada
     ronda queda registrada: la salida es una jerarquía, no una partición.

Provenance: por fusión, qué votantes dijeron continúa / corte / se abstuvieron.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AdaptivePlan:
    n_segments: int
    cuts: list[int]                      # partición final (inicio de cada tópico > 0)
    levels: list[list[int]]              # cortes por ronda, del más fino al final
    merges: list[dict] = field(default_factory=list)


def _l2(x):
    return x / (np.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


def _unit_stats(xn, lo, hi, prior):
    """Centroide, filas y coherencia leave-one-out de xn[lo:hi]; None sin evidencia.

    Coherencia LOO: coseno de cada shot al centroide de los DEMÁS shots de la
    unidad. Con el centroide in-sample la coherencia se infla (cada shot pesa
    1/|A| en su propio centroide) y ninguna vecina parece encajar. Unidad de un
    shot: `prior` (similitud típica entre shots contiguos de esa señal)."""
    rows = xn[lo:hi]
    rows = rows[np.linalg.norm(rows, axis=1) > 0]
    if len(rows) == 0:
        return None
    total = rows.sum(axis=0)
    nc = np.linalg.norm(total)
    if nc == 0:
        return None
    if len(rows) == 1:
        coh = prior
    else:
        rest = total[None, :] - rows
        rest = rest / (np.linalg.norm(rest, axis=1, keepdims=True) + 1e-8)
        coh = float((rows * rest).sum(axis=1).mean())
    return total / nc, rows, coh


def _adjacent_prior(xn):
    a, b = xn[:-1], xn[1:]
    ok = (np.linalg.norm(a, axis=1) > 0) & (np.linalg.norm(b, axis=1) > 0)
    return float(np.median((a[ok] * b[ok]).sum(axis=1))) if ok.any() else 0.0


def aggregate(embedding_voters: dict[str, np.ndarray],
              boundary_voters: dict[str, tuple[np.ndarray, float]],
              init_cuts: list[int], n_segments: int, *,
              rho: float = 0.9, max_rounds: int = 50) -> AdaptivePlan:
    """embedding_voters: {nombre: [n, D]}; boundary_voters: {nombre: (score[n-1], umbral)}
    con score[k] = evidencia de corte entre k y k+1. init_cuts en convención 1..n-1."""
    n = n_segments
    emb = {k: _l2(np.asarray(v, np.float32)[:n]) for k, v in embedding_voters.items()}
    prior = {k: _adjacent_prior(x) for k, x in emb.items()}
    cuts = sorted({int(c) for c in init_cuts if 0 < c < n})
    levels, merges = [list(cuts)], []

    for rnd in range(max_rounds):
        bounds = [0] + cuts + [n]
        stats = {k: [_unit_stats(x, a, b, prior[k]) for a, b in zip(bounds, bounds[1:])]
                 for k, x in emb.items()}
        keep, merged_any = [], False
        for u, c in enumerate(cuts):          # par (u, u+1) separado por el corte c
            cont, stop, abst = [], [], []
            for k in emb:
                A, B = stats[k][u], stats[k][u + 1]
                if A is None or B is None:
                    abst.append(k)
                    continue
                cross = 0.5 * (float((B[1] @ A[0]).mean()) + float((A[1] @ B[0]).mean()))
                (cont if cross >= rho * min(A[2], B[2]) else stop).append(k)
            for k, (score, thr) in boundary_voters.items():
                (cont if score[c - 1] < thr else stop).append(k)
            active = len(cont) + len(stop)
            if active and len(cont) > active / 2:
                merged_any = True
                merges.append({"round": rnd, "cut": c, "continue": cont,
                               "stop": stop, "abstain": abst})
            else:
                keep.append(c)
        if not merged_any:
            break
        cuts = keep
        levels.append(list(cuts))
    return AdaptivePlan(n_segments=n, cuts=cuts, levels=levels, merges=merges)
