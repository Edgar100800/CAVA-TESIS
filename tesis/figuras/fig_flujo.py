"""Figura 2.1: flujo de CAVA con íconos (coordenadas en milímetros sobre 150 x 92)."""
from __future__ import annotations

from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from estilo import ACENTO, CAVA, GRIS, ICONOS, SENAL, TEXTW, guardar, imagen, plt

W, H = 150, 92
AZUL_CLARO = "#ebf4fb"
VIOLETA = "#f3eefb"
VERDE = "#eef8f1"


def caja(ax, x, y, w, h, fc, ec=CAVA, lw=0.8, r=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=2))


def icono(ax, nombre, cx, cy, s):
    img = imagen(ICONOS / f"{nombre}.png")
    if img is not None:
        ax.imshow(img, extent=(cx - s / 2, cx + s / 2, cy - s / 2, cy + s / 2), zorder=3,
                  interpolation="lanczos")


def flecha(ax, a, b, color="black", lw=0.9, rad=0.0, estilo="-|>"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=8, lw=lw, color=color,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1,
                                 shrinkA=0, shrinkB=0))


def main():
    fig = plt.figure(figsize=(TEXTW, TEXTW * H / W))
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    # encabezados de etapa
    etapas = [(9.5, "1. Entrada"), (41, "2. Señales"), (76, "3. Votación"), (102, "4. Mapa"),
              (132.5, "5. Versiones")]
    for x, t in etapas:
        ax.text(x, H - 3, t, ha="center", va="center", fontsize=8, weight="bold", color=CAVA)

    # 1. entrada
    caja(ax, 1, 52, 17, 20, VERDE)
    icono(ax, "video", 9.5, 64.5, 9)
    ax.text(9.5, 55.5, "Video largo", ha="center", va="center", fontsize=6.8)
    caja(ax, 1, 23, 17, 20, VERDE)
    icono(ax, "unidad", 9.5, 35.5, 9)
    ax.text(9.5, 26.5, "Unidades 5 s", ha="center", va="center", fontsize=6.8)
    flecha(ax, (9.5, 52), (9.5, 43))

    # 2. señales: franja sin fusión
    ax.add_patch(FancyBboxPatch((22, 4), 38, 78, boxstyle="round,pad=0,rounding_size=2",
                                fc="#fff5f5", ec=ACENTO, lw=0.8, ls=(0, (4, 2)), zorder=0))
    ax.text(41, 6.2, "sin fusión: cada señal corta\ny etiqueta por su cuenta", ha="center",
            va="bottom", fontsize=6, color=ACENTO, style="italic", linespacing=0.95)
    senales = [("transcripcion", "Transcripción", "Whisper $\\rightarrow$ bge", "diálogo"),
               ("visual", "Visual", "SigLIP por unidad", "visual"),
               ("voz", "Voz", "log-mel y tono", "voz"),
               ("vlm", "Descripción VLM", "Qwen2.5-VL, 40 s", "VLM")]
    ys = [69, 53, 37, 21]
    for (ic, t, sub, key), y in zip(senales, ys):
        caja(ax, 24, y - 6.5, 34, 13, "white", ec=SENAL[key], lw=1.0)
        icono(ax, ic, 29.5, y, 8)
        ax.text(34.5, y + 1.8, t, fontsize=6.9, va="center", color=SENAL[key])
        ax.text(34.5, y - 2.4, sub, fontsize=5.6, va="center", color=GRIS)
        flecha(ax, (18, 33), (24, y), color=GRIS, lw=0.6, rad=-0.05 if y > 33 else 0.05)
        flecha(ax, (58, y), (64, 45), color=SENAL[key], lw=0.8, rad=0.05 if y > 45 else -0.05)

    # 3. votación
    caja(ax, 64, 20, 24, 50, AZUL_CLARO, lw=1.1)
    icono(ax, "votacion", 76, 61, 10)
    lineas = [("fronteras:", "black"), ("mayoría $\\pm$1 unidad", GRIS), ("tópicos:", "black"),
              ("quórum de señales", GRIS)]
    for k, (t, c) in enumerate(lineas):
        ax.text(76, 51.5 - k * 3.4, t, ha="center", va="center", fontsize=5.9, color=c)
    icono(ax, "abstencion", 76, 32.5, 7)
    ax.text(76, 25.5, "abstención sin\nevidencia", ha="center", va="center", fontsize=5.6,
            color=GRIS, linespacing=0.95)

    # 4. mapa
    flecha(ax, (88, 45), (92, 45), lw=1.0)
    caja(ax, 92, 20, 20, 50, VIOLETA, ec="#6b46c1", lw=1.1)
    icono(ax, "mapa", 102, 61, 10)
    for k, t in enumerate(["retornos", "de tema", "", "dos niveles", "", "procedencia",
                           "por señal"]):
        ax.text(102, 51.5 - k * 3.4, t, ha="center", va="center", fontsize=5.9, color=GRIS)

    # 5. versiones
    flecha(ax, (112, 45), (116, 45), lw=1.0)
    versiones = [("capitulos", "capítulos"), ("recap", "recapitulación 60 s"),
                 ("destacados", "destacados 10 \\%"), ("hilos_topico", "hilos de tópico"),
                 ("hilos_hablante", "hilos por hablante")]
    caja(ax, 116, 8, 33, 72, "white", ec=GRIS, lw=0.8)
    for k, (ic, t) in enumerate(versiones):
        y = 72 - k * 14.5
        icono(ax, ic, 121.5, y, 7)
        ax.text(126.5, y, t, fontsize=6, va="center")

    return guardar(fig, "f21_flujo_cava")


if __name__ == "__main__":
    main()
