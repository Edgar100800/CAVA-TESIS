"""Figuras del capítulo de resultados. Cada figura lee solo archivos de results/
(o cifras del registro de experimentos cuando el JSON no las guarda por video)."""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Patch

from estilo import (ACENTO, CAVA, GRIS, GRIS_CLARO, SENAL, figura, guardar, plt, resultado)

NOMBRE = {"cava_abst": "CAVA", "cava_abst_r95": "CAVA (ret. 95)", "cava": "CAVA-comp",
          "cava_avg": "CAVA-prom", "cava_avg_r80": "CAVA-prom (ret. 80)",
          "cava_avg_r95": "CAVA-prom (ret. 95)", "cava_r80": "CAVA-comp (ret. 80)",
          "cava_r95": "CAVA-comp (ret. 95)", "fused": "Fusión", "contiguous": "Contiguo",
          "visual": "visual sola", "dialogue": "diálogo sola", "vjudge": "VLM sola"}


def _wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


# ---------------------------------------------------------------- R0 ablación
def r0_ablacion():
    c = resultado("exp018_test.json")["criteria"]
    filas = [("cava_abst_vs_visual", "CAVA $-$ visual sola"),
             ("cava_abst_vs_cava_avg", "CAVA $-$ CAVA-prom"),
             ("cava_avg_vs_fused", "CAVA-prom $-$ Fusión"),
             ("cava_vs_fused", "CAVA-comp $-$ Fusión"),
             ("cava_abst_vs_contiguous", "CAVA $-$ Contiguo"),
             ("cava_abst_vs_fused", "CAVA $-$ Fusión (pre-registrada)")]
    fig, ax = figura(0.9, 0.42)
    for y, (k, lab) in enumerate(filas):
        m, se, z = c[k]["mean"], c[k]["se"], c[k]["z"]
        col = CAVA if z > 2 else (ACENTO if z < -2 else GRIS)
        ax.errorbar(m, y, xerr=1.96 * se, fmt="o", color=col, ms=5, capsize=3, lw=1.2)
        ax.text(0.0215, y, f"$z = {z:.2f}$", va="center", fontsize=7.5, color=col)
    ax.axvline(0, color="black", lw=0.7)
    ax.set_yticks(range(len(filas)), [f[1] for f in filas])
    ax.set_xlim(-0.016, 0.026)
    ax.set_xlabel("diferencia de MCC por película (media $\\pm$ 1.96 EE, 47 películas)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    return guardar(fig, "r0_ablacion_exp018")


# ---------------------------------------------------------------- R1 por película
def r1_por_pelicula():
    pf = resultado("exp018_test.json")["per_film"]
    x = np.array([v["mcc_fused"] for v in pf.values()])
    y = np.array([v["mcc_cava_abst"] for v in pf.values()])
    vis = np.array([v["mcc_visual"] for v in pf.values()])
    fig, axs = figura(1.0, 0.45, ncols=2)
    for ax, xx, lab in ((axs[0], x, "Fusión"), (axs[1], vis, "visual sola")):
        lo, hi = min(xx.min(), y.min()) - 0.005, max(xx.max(), y.max()) + 0.005
        ax.plot([lo, hi], [lo, hi], color=GRIS, lw=0.7, ls="--")
        arriba = y > xx
        ax.scatter(xx[arriba], y[arriba], s=14, color=CAVA, label="CAVA mayor", zorder=3)
        ax.scatter(xx[~arriba], y[~arriba], s=14, color=ACENTO, label="CAVA menor", zorder=3)
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        ax.set_aspect("equal")
        ax.set_xlabel(f"MCC de {lab}")
        ax.set_title(f"CAVA mayor en {arriba.sum()} de {len(y)} películas", fontsize=8.5)
    axs[0].set_ylabel("MCC de CAVA")
    axs[0].legend(loc="upper left", fontsize=7)
    return guardar(fig, "r1_mcc_por_pelicula")


# ---------------------------------------------------------------- R2 estructura
def r2_estructura():
    s = resultado("exp018_test.json")["systems"]
    fig, ax = figura(0.85, 0.62)
    for k, v in s.items():
        nombre = NOMBRE.get(k, k)
        principal = k in ("cava_abst", "cava", "cava_avg", "fused", "contiguous", "visual")
        col = CAVA if k.startswith("cava") else (ACENTO if k == "fused" else GRIS)
        ax.scatter(v["n_topics"], v["link_rate"], s=30 + 3000 * max(v["mcc"], 0), color=col,
                   alpha=0.85 if principal else 0.35, ec="white", lw=0.6, zorder=3)
        if principal:
            ax.annotate(nombre, (v["n_topics"], v["link_rate"]), xytext=(6, 3),
                        textcoords="offset points", fontsize=7.5)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("número medio de tópicos por película")
    ax.set_ylabel("tasa de enlace (fracción de pares unidos)")
    ax.annotate("percolación", (4, 0.99), xytext=(7, 0.45), fontsize=7.5, color=ACENTO,
                arrowprops=dict(arrowstyle="-|>", color=ACENTO, lw=0.7))
    ax.text(0.99, 0.02, "área del punto proporcional al MCC", transform=ax.transAxes,
            ha="right", fontsize=7, color=GRIS)
    return guardar(fig, "r2_topicos_vs_enlace")


# ---------------------------------------------------------------- R3 coherencia
def r3_coherencia():
    cm = resultado("exp018_test.json")["coherence_margin"]
    sistemas = [("cava_abst", "CAVA"), ("cava_avg", "CAVA-prom"), ("fused", "Fusión"),
                ("contiguous", "Contiguo")]
    senales = [("visual", "visual"), ("dialogue", "diálogo"), ("vjudge", "VLM")]
    fig, ax = figura(0.85, 0.45)
    w = 0.2
    cols = [CAVA, "#63b3ed", ACENTO, GRIS]
    for i, (k, lab) in enumerate(sistemas):
        vals = [cm[f"{k}_{s}"]["mean"] for s, _ in senales]
        ax.bar(np.arange(3) + (i - 1.5) * w, vals, width=w * 0.92, color=cols[i], label=lab)
    ax.set_xticks(range(3), [s[1] for s in senales])
    ax.set_ylabel("margen intra $-$ inter (media)")
    ax.legend(ncol=4, loc="upper left", fontsize=7.5)
    ax.set_ylim(0, 0.19)
    return guardar(fig, "r3_coherencia")


# ---------------------------------------------------------------- R4 clips
def r4_clips():
    # z media de importancia por decil de duración (EXPERIMENT_LOG, EXP-031 corrección y EXP-038)
    tvsum = [-0.32, -0.22, -0.01, 0.25, 0.24, 0.31, 0.18, -0.01, -0.02, -0.38]
    summe = [0.13, 0.09, 0.21, 0.04, -0.10, -0.06, -0.10, 0.02, -0.14, -0.06]
    m38 = resultado("exp038_summe.json")["means"]
    fig, axs = figura(1.0, 0.4, ncols=2, gridspec_kw=dict(width_ratios=[1.15, 1]))
    x = np.arange(1, 11)
    axs[0].plot(x, tvsum, "o-", color=CAVA, ms=3.5, label="TVSum (50)")
    axs[0].plot(x, summe, "s-", color=ACENTO, ms=3.5, label="SumMe (25)")
    axs[0].axhline(0, color=GRIS, lw=0.6)
    axs[0].set_xticks(x)
    axs[0].set_xlabel("decil de la duración del video")
    axs[0].set_ylabel("importancia media ($z$)")
    axs[0].legend(fontsize=7.5)
    axs[0].set_title("Sesgo de posición de las referencias", fontsize=8.5)
    items = [("H3", m38["H3"]), ("uniforme", m38["uniform"]), ("centro", m38["center"]),
             ("azar", m38["random"]), ("política\naprendida", m38["policy"])]
    cols = [CAVA if v > 0 else ACENTO for _, v in items]
    axs[1].barh(range(len(items))[::-1], [v for _, v in items], color=cols, height=0.65)
    axs[1].set_yticks(range(len(items))[::-1], [k for k, _ in items])
    axs[1].axvline(0, color="black", lw=0.6)
    axs[1].set_xlabel("recompensa media en SumMe")
    axs[1].set_title("Política entrenada en TVSum", fontsize=8.5)
    axs[1].tick_params(axis="y", length=0)
    return guardar(fig, "r4_clips_posicion")


# ---------------------------------------------------------------- R5 voz
def r5_voz():
    d = resultado("exp028_voxconverse_test.json")
    pf = [v for v in d["per_file"].values() if v.get("ari_hand") is not None
          and v.get("ari_xvec") is not None]
    h = np.array([v["ari_hand"] for v in pf])
    x = np.array([v["ari_xvec"] for v in pf])
    ami = resultado("exp028_secondary.json")["ami_summary"]
    fig, axs = figura(1.0, 0.42, ncols=2, gridspec_kw=dict(width_ratios=[1, 1]))
    axs[0].plot([-0.2, 1], [-0.2, 1], color=GRIS, lw=0.7, ls="--")
    axs[0].scatter(h, x, s=7, color=SENAL["voz"], alpha=0.6, lw=0)
    axs[0].set_xlabel("ARI con log-mel y tono")
    axs[0].set_ylabel("ARI con WavLM-sv")
    axs[0].set_title(f"VoxConverse test ({len(pf)} archivos)", fontsize=8.5)
    axs[0].set_xlim(-0.2, 1)
    axs[0].set_ylim(-0.2, 1)
    axs[0].set_aspect("equal")
    grupos = [("VoxConverse", d["means"]["ari_hand"], d["means"]["ari_xvec"]),
              ("AMI", ami["ari_hand"], ami["ari_xvec"])]
    w = 0.35
    for i, (lab, a, b) in enumerate(grupos):
        axs[1].bar(i - w / 2, a, w * 0.92, color=GRIS, label="log-mel y tono" if i == 0 else None)
        axs[1].bar(i + w / 2, b, w * 0.92, color=SENAL["voz"], label="WavLM-sv" if i == 0 else None)
        axs[1].text(i - w / 2, a + 0.02, f"{a:.2f}", ha="center", fontsize=7)
        axs[1].text(i + w / 2, b + 0.02, f"{b:.2f}", ha="center", fontsize=7)
    axs[1].set_xticks([0, 1], [g[0] for g in grupos])
    axs[1].set_ylabel("ARI medio")
    axs[1].set_ylim(0, 0.9)
    axs[1].legend(fontsize=7.5, loc="upper left")
    return guardar(fig, "r5_identidad_voz")


# ---------------------------------------------------------------- R6 G-versión
def r6_presupuestos():
    pf = resultado("g_version_report.json")["per_film"]
    fig, ax = figura(0.85, 0.4)
    for i, (fmt, lab) in enumerate((("recap60", "recapitulación 60 s"),
                                    ("highlights10pct", "destacados 10 %"),
                                    ("threads", "hilos de tópico"))):
        r = []
        for v in pf.values():
            f = v[fmt]
            if f["budget_s"]:
                r += [t / f["budget_s"] for t in f["total_s"]]
        r = np.array(r)
        jit = np.random.default_rng(i).uniform(-0.18, 0.18, len(r))
        ax.scatter(r, i + jit, s=8, color=CAVA, alpha=0.6, lw=0)
        ax.text(1.04, i, f"{(r <= 1.0001).mean() * 100:.0f} % dentro", va="center", fontsize=7.5)
    ax.axvline(1, color=ACENTO, lw=0.8, ls="--")
    ax.set_yticks(range(3), ["recapitulación 60 s", "destacados 10 %", "hilos de tópico"])
    ax.set_xlabel("duración de la lista / presupuesto (58 películas)")
    ax.set_xlim(0, 1.2)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    return guardar(fig, "r6_presupuestos_gversion")


# ---------------------------------------------------------------- R7 G-enlace
def r7_genlace():
    lotes = [("Lote 1", resultado("g_enlace_model_review.json")),
             ("Lote 2 (pre-registrado)", resultado("g_enlace_model_review_batch2.json"))]
    fig, ax = figura(0.75, 0.45)
    for i, (lab, d) in enumerate(lotes):
        for j, (k, nom, col) in enumerate((("system", "enlaces de CAVA", CAVA),
                                           ("controls", "controles al azar", GRIS))):
            n = sum(d[k].values())
            p, lo, hi = _wilson(d[k]["yes"], n)
            x = i + (j - 0.5) * 0.3
            ax.bar(x, p, 0.27, color=col, label=nom if i == 0 else None)
            ax.errorbar(x, p, yerr=[[p - lo], [hi - p]], color="black", capsize=3, lw=0.8)
        ax.text(i, 0.97, f"Fisher $p = {d['fisher_one_sided_p']:.2f}$", ha="center", fontsize=7.5)
    ax.set_xticks([0, 1], [l for l, _ in lotes])
    ax.set_ylabel("fracción juzgada como el mismo hilo")
    ax.set_ylim(0, 1.25)
    ax.legend(fontsize=7.5, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.12))
    return guardar(fig, "r7_genlace")


# ---------------------------------------------------------------- R8 BBC
def r8_bbc():
    m = resultado("exp025_criteria.json")["means_conf"]
    ps = [70, 80, 90, 95]
    fig, ax = figura(0.75, 0.48)
    ax.plot(ps, [m[f"m_local_cava_p{p}"] for p in ps], "o-", color=CAVA, label="estructura (M local)")
    ax.plot(ps, [m[f"f1b_cava_p{p}"] for p in ps], "s-", color=SENAL["VLM"], label="F1 de fronteras")
    ax.axhline(m["ceiling_m_local"], color=CAVA, lw=0.8, ls="--")
    ax.axhline(m["ceiling_f1_b"], color=SENAL["VLM"], lw=0.8, ls=":")
    ax.text(95.4, m["ceiling_m_local"], "acuerdo entre\nanotadores", fontsize=7, va="center")
    ax.axvline(90, color=GRIS_CLARO, lw=6, zorder=0)
    ax.text(90, 0.05, "perfil\nelegido", ha="center", fontsize=7, color=GRIS)
    ax.set_xticks(ps, [f"p{p}" for p in ps])
    ax.set_xlabel("percentil de corte")
    ax.set_ylim(0, 0.75)
    ax.set_xlim(68, 99)
    ax.legend(fontsize=7.5, loc="lower left")
    return guardar(fig, "r8_bbc_documental")


# ---------------------------------------------------------------- R9 inventario
def r9_inventario():
    estados = [("validado", 10, CAVA), ("acotado", 2, "#63b3ed"), ("parcial", 3, "#d69e2e"),
               ("no validado", 6, ACENTO), ("en producto sin compuerta", 4, GRIS),
               ("sin evaluación", 1, GRIS_CLARO)]
    fig, ax = figura(1.0, 0.13)
    x = 0
    for lab, n, col in estados:
        ax.barh(0, n, left=x, color=col, ec="white", lw=1.2, height=0.6)
        ax.text(x + n / 2, 0, str(n), ha="center", va="center", fontsize=8,
                color="white" if col not in (GRIS_CLARO,) else "black")
        x += n
    ax.set_xlim(0, 26)
    ax.axis("off")
    ax.legend(handles=[Patch(color=c, label=l) for l, _, c in estados], ncol=6,
              loc="upper center", bbox_to_anchor=(0.5, -0.05), fontsize=7, handlelength=1)
    return guardar(fig, "r9_inventario")


# ---------------------------------------------------------------- R10 ASR
def r10_asr():
    d = resultado("exp030.json")
    m, ami = d["means"], d["c3_ami_means"]
    paneles = [("habla omitida", m["miss_whisper"], m["miss_parakeet"], "{:.1%}"),
               ("habla falsa", m["fsr_whisper"], m["fsr_parakeet"], "{:.2f}"),
               ("MCC en AMI", ami["mcc_whisper"], ami["mcc_parakeet"], "{:.2f}")]
    fig, axs = figura(0.85, 0.3, ncols=3)
    for ax, (t, a, b, fmt) in zip(axs, paneles):
        ax.bar([0, 1], [a, b], color=[CAVA, GRIS], width=0.6)
        for i, v in enumerate((a, b)):
            ax.text(i, v, fmt.format(v).replace("%", "\\%"), ha="center", va="bottom", fontsize=7)
        ax.set_xticks([0, 1], ["Whisper", "Parakeet"])
        ax.set_title(t, fontsize=8.5)
        ax.set_yticks([])
        ax.spines["left"].set_visible(False)
        ax.set_ylim(0, max(a, b) * 1.3)
    return guardar(fig, "r10_asr")


def main():
    for f in (r0_ablacion, r1_por_pelicula, r2_estructura, r3_coherencia, r4_clips, r5_voz,
              r6_presupuestos, r7_genlace, r8_bbc, r9_inventario, r10_asr):
        f()


if __name__ == "__main__":
    main()
