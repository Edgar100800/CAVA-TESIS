# PLAN — Afinado de granularidad temática (quant + qual)

> Abierto 2026-09-25 tras migrar a CAVA. Protocolo de medición por definir
> (compromiso: registro cuantitativo Y cualitativo de cada configuración).

## El parámetro en cuestión

La granularidad de tópicos depende de 3 perillas del gestor (`multimodal_manager.manage`):

| Perilla | Qué controla | Rango explorado |
|---|---|---|
| `percentile` (por señal) | cuántos cortes candidatos emite cada señal | 60–90 |
| `link_quorum` | señales que deben coincidir para enlazar segmentos | 1–n_señales |
| `tolerance_bins` | ventana de consenso para confirmar frontera | 0–2 bins (0–4s) |

## Scores cuantitativos (a registrar por configuración)

- **Nº de grupos** y distribución de tamaños (min/med/max).
- **Coherencia intra-tópico** (coseno medio de embeddings por grupo, por señal).
- **Separación inter-tópico** (1 − coseno entre centroides vecinos).
- **Provenance** (soporte por señal por grupo — qué señal sostiene qué).
- **Cortes confirmados vs candidatos** (tasa de confirmación por quorum).

## Scores cualitativos (a registrar por configuración)

- **Revisión humana por muestra**: ¿el grupo es UN tema? sí/no/parcial (n≥10 grupos por config).
- **Juez frozen como juez**: pairwise "¿estos dos clips son el mismo tópico?" sobre pares
  dentro/fuera de grupo (mismo mecanismo que las captions ya probadas).
- **Notas de fallo tipado**: sobre-segmentación / bajo-segmentación / tema mezclado.

## Pendiente de diseño (próxima sesión)

1. Definir el set de configuraciones a barrer (grid o incremental).
2. Definir el corpus de medición (3 videos TVSum piloto + BLiSS transcripts).
3. Umbral de aceptación: consistencia entre videos (misma config no debe variar ±X).
4. Plantilla de registro: `results/granularidad_<config>.json` + notas cualitativas.
