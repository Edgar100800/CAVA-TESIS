"""Caso ilustrativo del marco teórico: un documental de 4 minutos con 6 escenas.

Escenas de 8 unidades (5 s cada una, 40 s por escena): leones (A), cachorros (A), arrecife (B),
ballena (B), río al atardecer sin narración (C) y leones al atardecer (retorno de A).
Las señales se generan con un prototipo por tema más ruido y se pasan por el gestor
real de CAVA (topicagg.multimodal_manager.manage). Los datos son sintéticos.
"""
from __future__ import annotations

import numpy as np

from topicagg.multimodal_manager import manage

UNIT_S = 5
SCENES = [  # (ilustración, tema, etiqueta)
    ("e1_leones_amanecer", "A", "leones"),
    ("e2_cachorros", "A", "cachorros"),
    ("e3_arrecife", "B", "arrecife"),
    ("e4_ballena", "B", "ballena"),
    ("e5_rio_atardecer", "C", "río"),
    ("e6_leones_descanso", "A", "leones"),
]
PER_SCENE = 8
N = PER_SCENE * len(SCENES)
SILENT = range(32, 40)          # el río no tiene narración: el diálogo no tiene evidencia
VLM_BLOCK = 8                   # el VLM describe bloques de 40 s
D = 48
SEED = 1
KW = dict(percentile=90, min_gap=3, return_percentile=90, link_quorum=2)


def topic_truth() -> np.ndarray:
    return np.array([SCENES[i // PER_SCENE][1] for i in range(N)])


def signals(seed: int = SEED) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)

    def unit():
        v = rng.normal(size=D)
        return v / np.linalg.norm(v)

    topic = topic_truth()
    scene = np.arange(N) // PER_SCENE
    # visual: cada escena tiene su aspecto propio, cercano al de su tema
    tv = {t: unit() for t in "ABC"}
    sv = [unit() for _ in SCENES]
    visual = np.stack([tv[topic[i]] + 0.35 * sv[scene[i]] + 0.15 * unit() for i in range(N)])
    # diálogo: la narración sigue el tema; fila nula donde no hay narración
    td = {t: unit() for t in "ABC"}
    dialogo = np.stack([td[topic[i]] + 0.15 * unit() for i in range(N)])
    dialogo[list(SILENT)] = 0.0
    # VLM: una descripción por bloque, constante dentro del bloque
    tm = {t: unit() for t in "ABC"}
    vlm = np.zeros((N, D))
    for b0 in range(0, N, VLM_BLOCK):
        blk = list(range(b0, min(N, b0 + VLM_BLOCK)))
        t = max(set(topic[blk]), key=list(topic[blk]).count)
        vlm[blk] = tm[t] + 0.2 * unit()
    return {"visual": visual, "diálogo": dialogo, "VLM": vlm}


def run(**extra):
    return manage(signals(), **(KW | extra))
