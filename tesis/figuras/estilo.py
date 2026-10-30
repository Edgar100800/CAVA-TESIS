"""Estilo común de las figuras de la tesis.

Las figuras se compilan con el backend pgf de matplotlib y pdflatex, de modo que usan
la misma tipografía que el documento. Los tamaños se expresan como fracción del ancho
de texto (15 cm: A4 con márgenes de 3 cm).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("pgf")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

TESIS = Path(__file__).resolve().parents[1]
ROOT = TESIS.parent
RESULTS = ROOT / "results"
OUT = TESIS / "images" / "generadas"
ICONOS = TESIS / "images" / "iconos"
ILUSTRACIONES = TESIS / "images" / "ilustraciones"

TEXTW = 15 / 2.54  # pulgadas

# Paleta: una por señal, una por tema del caso ilustrativo y tonos neutros
SENAL = {"visual": "#2b6cb0", "diálogo": "#2f855a", "voz": "#b7791f", "VLM": "#c05621",
         "consenso": "#1a202c"}
TEMA = {"A": "#d69e2e", "B": "#3182ce", "C": "#805ad5"}
GRIS = "#718096"
GRIS_CLARO = "#e2e8f0"
ACENTO = "#c53030"
CAVA = "#1f4e79"

plt.rcParams.update({
    "pgf.texsystem": "pdflatex",
    "pgf.rcfonts": False,
    "pgf.preamble": r"\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage{amsmath}\usepackage{amssymb}",
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "lines.linewidth": 1.2,
    "legend.frameon": False,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
})


def figura(ancho: float = 1.0, alto: float = 0.45, **kw):
    """Crea una figura con ancho en fracción de \\textwidth y alto en fracción del ancho."""
    w = TEXTW * ancho
    return plt.subplots(figsize=(w, w * alto), **kw)


def guardar(fig, nombre: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{nombre}.pdf"
    fig.savefig(p)
    plt.close(fig)
    print(f"ok {p.relative_to(TESIS)}")
    return p


def resultado(nombre: str) -> dict:
    return json.loads((RESULTS / nombre).read_text())


def imagen(path: Path):
    """Lee una imagen si existe; si no, devuelve None (la figura dibuja un marcador)."""
    if not path.exists():
        return None
    return plt.imread(path)


def minuto(x, _pos=None):
    m, s = divmod(int(round(x)), 60)
    return f"{m}:{s:02d}"


def z_txt(z: float) -> str:
    return f"$z = {z:.2f}$".replace("-", "-")


__all__ = ["plt", "np"]
