"""Figuras del marco teórico sobre el caso ilustrativo (datos sintéticos, gestor real).

M1 fronteras por señal, M2 consenso de fronteras, M3 matriz de votos con y sin
abstención, M4 percolación del enlace simple y M5 mapa de tópicos final.
"""
from __future__ import annotations

import matplotlib.ticker as mticker
import numpy as np
from matplotlib.patches import FancyArrowPatch, Rectangle
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial.distance import squareform

import caso_sintetico as caso
from estilo import (GRIS, GRIS_CLARO, ILUSTRACIONES, SENAL, TEMA, figura, guardar, imagen,
                    minuto, plt)

U = caso.UNIT_S
T = caso.N * U
SIG = ["visual", "diálogo", "VLM"]
TRUTH = caso.topic_truth()


def _thumb(path, ancho=480):
    img = imagen(path)
    if img is None:
        return None
    h, w = img.shape[:2]
    step = max(1, w // ancho)
    return img[::step, ::step]


def tira_fotogramas(ax, etiquetas=True):
    """Dibuja las 6 escenas sobre el eje de tiempo, con el color de su tema."""
    for k, (archivo, tema, nombre) in enumerate(caso.SCENES):
        x0, x1 = k * caso.PER_SCENE * U, (k + 1) * caso.PER_SCENE * U
        img = _thumb(ILUSTRACIONES / f"{archivo}.jpg")
        pad = 1.2
        if img is not None:
            ax.imshow(img, extent=(x0 + pad, x1 - pad, 0.12, 1.0), aspect="auto",
                      interpolation="bilinear", zorder=1)
        else:
            ax.add_patch(Rectangle((x0 + pad, 0.12), x1 - x0 - 2 * pad, 0.88, color=GRIS_CLARO))
        ax.add_patch(Rectangle((x0 + pad, 0.0), x1 - x0 - 2 * pad, 0.09, color=TEMA[tema],
                               lw=0, zorder=2))
        if etiquetas:
            ax.text((x0 + x1) / 2, -0.06, f"{tema} · {nombre}", ha="center", va="top", fontsize=7.5)
    ax.set_xlim(0, T)
    ax.set_ylim(0, 1)
    ax.axis("off")


def _eje_tiempo(ax):
    ax.xaxis.set_major_locator(mticker.MultipleLocator(40))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(minuto))
    ax.set_xlim(0, T)


def _silencio(ax, y0=0, y1=1, texto=True):
    a, b = caso.SILENT.start * U, caso.SILENT.stop * U
    ax.axvspan(a, b, ymin=y0, ymax=y1, color=GRIS_CLARO, lw=0, zorder=0)
    if texto:
        ax.text((a + b) / 2, 0.96, "sin narración", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7, color=GRIS, style="italic")


# ---------------------------------------------------------------------- M1
def m1_fronteras(plan):
    fig = plt.figure(figsize=(15 / 2.54, 15 / 2.54 * 0.78))
    gs = fig.add_gridspec(4, 1, height_ratios=[1.25, 1, 1, 1], hspace=0.38)
    tira_fotogramas(fig.add_subplot(gs[0]))
    t = (np.arange(caso.N - 1) + 1) * U
    for r, s in enumerate(SIG):
        ax = fig.add_subplot(gs[r + 1])
        b = plan.per_signal_boundary[s]
        thr = np.percentile(b, caso.KW["percentile"])
        if s == "diálogo":
            _silencio(ax)
        ax.plot(t, b, color=SENAL[s], lw=1.1)
        ax.axhline(thr, color=SENAL[s], lw=0.7, ls="--", alpha=0.8)
        for c in plan.per_signal_cuts[s]:
            ax.plot(c * U, b[c - 1], marker="v", color=SENAL[s], ms=6, mec="white", mew=0.6,
                    zorder=3)
        ax.set_ylabel(s, rotation=0, ha="right", va="center", color=SENAL[s])
        ax.set_yticks([])
        ax.set_ylim(0, 1.12)
        _eje_tiempo(ax)
        if r < 2:
            ax.set_xticklabels([])
        ax.spines["left"].set_visible(False)
    ax.set_xlabel("tiempo (min:s)")
    fig.text(0.92, 0.66, "línea discontinua:\npercentil 90 de\ncada señal\n\n$\\blacktriangledown$ corte propio",
             fontsize=7, color=GRIS, va="top")
    return guardar(fig, "m1_fronteras_por_senal")


# ---------------------------------------------------------------------- M2
def m2_consenso(plan):
    tol = 1
    n1 = caso.N - 1
    pres = {}
    for s in SIG:
        p = np.zeros(n1, bool)
        for c in plan.per_signal_cuts[s]:
            p[max(0, c - tol):min(n1, c + tol + 1)] = True
        pres[s] = p
    votes = sum(pres[s].astype(int) for s in SIG)
    mayoria = int(np.ceil(len(SIG) / 2))

    fig = plt.figure(figsize=(15 / 2.54, 15 / 2.54 * 0.46))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.1, 1], hspace=0.15)
    ax = fig.add_subplot(gs[0])
    for r, s in enumerate(SIG):
        y = len(SIG) - 1 - r
        for k in np.flatnonzero(pres[s]):
            ax.add_patch(Rectangle((k * U - U / 2, y + 0.15), U, 0.7, color=SENAL[s], alpha=0.35,
                                   lw=0))
        for c in plan.per_signal_cuts[s]:
            ax.plot([c * U] * 2, [y + 0.1, y + 0.9], color=SENAL[s], lw=1.6)
        ax.text(-4, y + 0.5, s, ha="right", va="center", color=SENAL[s])
    ax.set_xlim(0, T)
    ax.set_ylim(0, len(SIG))
    ax.axis("off")
    ax.set_title("Cortes propios de cada señal y su tolerancia de $\\pm$1 unidad", loc="left",
                 fontsize=8.5)

    ax2 = fig.add_subplot(gs[1])
    x = np.arange(n1) * U
    col = [SENAL["consenso"] if v >= mayoria else GRIS for v in votes]
    ax2.bar(x, votes, width=U * 0.85, color=col, lw=0)
    ax2.axhline(mayoria - 0.5, color="#c53030", lw=0.8, ls="--")
    ax2.text(T, mayoria - 0.45, " mayoría", color="#c53030", fontsize=7, va="bottom", ha="right")
    for c in plan.consensus_cuts:
        ax2.annotate("corte", (c * U, votes[c] + 0.05), xytext=(c * U, 3.55), ha="center",
                     fontsize=7, arrowprops=dict(arrowstyle="-|>", lw=0.6, color="black"))
    ax2.set_ylim(0, 4)
    ax2.set_yticks([0, 1, 2, 3])
    ax2.set_ylabel("votos")
    _eje_tiempo(ax2)
    ax2.set_xlabel("tiempo (min:s)")
    return guardar(fig, "m2_consenso_fronteras")


# ---------------------------------------------------------------------- M3
def _matrices(labels: dict[str, np.ndarray], abstain: bool):
    n = caso.N
    V = np.zeros((n, n))
    A = np.zeros((n, n))
    for s in SIG:
        lab = labels[s]
        act = lab >= 0 if abstain else np.ones(n, bool)
        both = act[:, None] & act[None, :]
        V += (lab[:, None] == lab[None, :]) & both
        A += both
    return V, A


def m3_votos(plan_abst, plan_sin):
    V0, _ = _matrices(plan_sin.per_signal_labels, abstain=False)
    V1, A1 = _matrices(plan_abst.per_signal_labels, abstain=True)
    sin = V0 / len(SIG)
    con = np.where(A1 >= caso.KW["link_quorum"], V1 / np.maximum(A1, 1), np.nan)

    fig, axs = figura(1.0, 0.47, ncols=2)
    cmap = plt.get_cmap("Blues").copy()
    cmap.set_bad("#f7fafc")
    lim = [0, caso.N]
    for ax, M, tit in ((axs[0], sin, "Sin abstención: $V_{ij}/S$"),
                       (axs[1], con, "Con abstención: $V_{ij}/A_{ij}$")):
        im = ax.imshow(M, cmap=cmap, vmin=0, vmax=1, origin="upper",
                       extent=(0, caso.N, caso.N, 0), interpolation="nearest")
        ax.set_title(tit, fontsize=8.5)
        edges = [0, 16, 32, 40, 48]
        mids = [(a + b) / 2 for a, b in zip(edges, edges[1:])]
        ax.set_xticks(mids, ["A", "B", "C", "A"])
        ax.set_yticks(mids, ["A", "B", "C", "A"])
        for e in edges[1:-1]:
            ax.axhline(e, color="white", lw=0.8)
            ax.axvline(e, color="white", lw=0.8)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_xlim(lim)
        ax.set_ylim(lim[::-1])
        a, b = caso.SILENT.start, caso.SILENT.stop
        ax.add_patch(Rectangle((a, a), b - a, b - a, fill=False, ec="#c53030", lw=0.9, ls="--"))
    cb = fig.colorbar(im, ax=axs, fraction=0.03, pad=0.02)
    cb.set_label("fracción de señales que agrupan el par")
    cb.outline.set_visible(False)
    return guardar(fig, "m3_matriz_votos")


# ---------------------------------------------------------------------- M4
def m4_percolacion():
    """Cadena de 6 segmentos: cada par vecino de la cadena tiene quórum, los extremos no."""
    n = 6
    S = 3
    V = np.zeros((n, n))
    pares = {(0, 1): 3, (1, 2): 2, (2, 3): 2, (3, 4): 2, (4, 5): 3, (0, 2): 1, (3, 5): 1,
             (1, 3): 1, (2, 4): 1}
    for (i, j), v in pares.items():
        V[i, j] = V[j, i] = v
    q = 2
    _, comp = connected_components(csr_matrix(V >= q), directed=False)
    D = 1 - V / S
    np.fill_diagonal(D, 0)
    prom = fcluster(linkage(squareform(D, checks=False), "average"), t=1 - q / S + 1e-9,
                    criterion="distance") - 1

    pos = np.array([[0, 0], [1, 0.55], [2, 0], [3, 0.55], [4, 0], [5, 0.55]], float)
    fig, axs = figura(1.0, 0.3, ncols=2)
    paleta = ["#d69e2e", "#3182ce", "#805ad5", "#2f855a", "#c05621", "#718096"]
    for ax, grupos, tit in ((axs[0], comp, "Componentes conexas: un solo tópico"),
                            (axs[1], prom, "Enlace promedio: la cadena se corta")):
        for (i, j), v in pares.items():
            ok = v >= q
            ax.plot(*pos[[i, j]].T, color="black" if ok else GRIS_CLARO, lw=1.6 if ok else 0.9,
                    zorder=1)
            if ok or (i, j) in ((0, 2),):
                m = pos[[i, j]].mean(0)
                ax.text(*m, f"{v}", fontsize=7, ha="center", va="center", zorder=3,
                        bbox=dict(boxstyle="circle,pad=0.15", fc="white", ec="none"))
        _, idx = np.unique(grupos, return_inverse=True)
        for k, (x, y) in enumerate(pos):
            ax.scatter(x, y, s=260, color=paleta[idx[k]], zorder=2, ec="white", lw=1)
            ax.text(x, y, f"$s_{k + 1}$", ha="center", va="center", fontsize=7.5, color="white",
                    zorder=4)
        ax.set_title(tit, fontsize=8.5)
        ax.set_xlim(-0.5, 5.5)
        ax.set_ylim(-0.45, 1.0)
        ax.axis("off")
    fig.text(0.5, -0.04, "Número sobre cada arista: señales que agrupan el par (de 3). "
             "Quórum: 2. Aristas grises: pares sin quórum.", ha="center", fontsize=7, color=GRIS)
    return guardar(fig, "m4_percolacion")


# ---------------------------------------------------------------------- M5
def _fila_etiquetas(ax, y, labels, colores, alto=0.7, abst_color=GRIS_CLARO):
    for i, l in enumerate(labels):
        c = abst_color if l < 0 else colores[l]
        ax.add_patch(Rectangle((i * U, y), U, alto, color=c, lw=0))
        if l < 0:
            ax.add_patch(Rectangle((i * U, y), U, alto, fill=False, hatch="////", ec=GRIS, lw=0))


def _color_por_tema(labels):
    """Asigna a cada etiqueta el color del tema mayoritario entre sus unidades."""
    col = {}
    for l in np.unique(labels):
        if l < 0:
            continue
        temas = TRUTH[labels == l]
        col[l] = TEMA[max(set(temas), key=list(temas).count)]
    return col


def m5_mapa(plan):
    fig = plt.figure(figsize=(15 / 2.54, 15 / 2.54 * 0.62))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.2, 1.95, 0.95], hspace=0.12)
    tira_fotogramas(fig.add_subplot(gs[0]), etiquetas=False)

    ax = fig.add_subplot(gs[1])
    filas = [(s, plan.per_signal_labels[s]) for s in SIG]
    for r, (s, lab) in enumerate(filas):
        y = 3.3 - r * 0.9
        _fila_etiquetas(ax, y, lab, _color_por_tema(lab))
        ax.text(-4, y + 0.35, s, ha="right", va="center", color=SENAL[s], fontsize=8)
    final = plan.labels
    _fila_etiquetas(ax, 0, final, _color_por_tema(final), alto=0.9)
    ax.text(-4, 0.45, "mapa", ha="right", va="center", fontsize=8, weight="bold")
    for c in plan.consensus_cuts:
        ax.plot([c * U] * 2, [0, 4.1], color="black", lw=0.6, ls=":")
    # arco del retorno: mismo grupo en dos tramos no contiguos
    runs = []
    for i, l in enumerate(final):
        if not runs or runs[-1][0] != l:
            runs.append([l, i, i])
        runs[-1][2] = i
    for a in range(len(runs)):
        for b in range(a + 1, len(runs)):
            if runs[a][0] == runs[b][0]:
                xa = (runs[a][1] + runs[a][2] + 1) / 2 * U
                xb = (runs[b][1] + runs[b][2] + 1) / 2 * U
                ax.add_patch(FancyArrowPatch((xa, -0.08), (xb, -0.08),
                                             connectionstyle="arc3,rad=0.12",
                                             arrowstyle="-", lw=1.2, color="black"))
                ax.text((xa + xb) / 2, -1.25, "retorno del tema A: el mismo grupo en dos tramos",
                        ha="center", va="center", fontsize=7.5)
    ax.set_xlim(0, T)
    ax.set_ylim(-1.55, 4.15)
    ax.axis("off")

    # procedencia por grupo
    ax3 = fig.add_subplot(gs[2])
    grupos = [g for g in plan.groups if len(g.segment_indices) > 1]
    w = 0.25
    for k, g in enumerate(grupos):
        tema = TRUTH[g.segment_indices[0]]
        for j, s in enumerate(SIG):
            ax3.bar(k + (j - 1) * w, g.signal_support[s], width=w * 0.92, color=SENAL[s],
                    label=s if k == 0 else None)
        ax3.text(k, -0.32, f"grupo {tema}\n({len(g.segment_indices) * U} s)", ha="center",
                 va="top", fontsize=7)
    ax3.set_xticks([])
    ax3.set_ylim(0, 1.05)
    ax3.set_yticks([0, 0.5, 1])
    ax3.set_ylabel("soporte", fontsize=8)
    ax3.set_xlim(-0.6, len(grupos) - 0.4)
    ax3.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.5, title="procedencia",
               title_fontsize=7.5)
    return guardar(fig, "m5_mapa_topicos")


def main():
    plan = caso.run(link_mode="average", abstain=True)
    plan_sin = caso.run(link_mode="average")
    m1_fronteras(plan)
    m2_consenso(plan)
    m3_votos(plan, plan_sin)
    m4_percolacion()
    m5_mapa(plan)


if __name__ == "__main__":
    main()
