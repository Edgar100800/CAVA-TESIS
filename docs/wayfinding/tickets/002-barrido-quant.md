---
title: "Barrido de configuraciones con registro cuantitativo"
labels: ["wayfinder:task", "wayfinder:AFK", "wayfinder:resolved"]
assignee: edgar.chambilla
resolved: true
blocks: ["005-decidir-default"]
---

## Question

_(ticket de ejecución)_: correr `manage()` sobre los 3 videos piloto en el
grid percentile × link_quorum × tolerance_bins, registrando cuantitativa.

## Resolution

**v2 — ESCALA MOVIENET (34 películas, GT escenas narrativas):**
mejor F1 **0.391 (p90_q2)** y 0.381 (p80_q2); P 0.60 (p90_q1) con R 0.07;
baseline aleatorio **P≈0.225**. tolerancia_bins no afecta el agrupamiento.
Conclusión: el consenso sube P por encima del azar (+46% en p90_q1) pero la
señal por-shot (TF-IDF + SigLIP de un keyframe) lleva poca estructura narrativa
a esta escala — el over-segmentation (R≈1 con señales solas) es el defecto
dominante. F1 máx 0.39 vs need.

v1 (3 videos TVSum, 2026-09-26): 12 configuraciones; hallazgos: link_quorum
domina (q1 colapsa en mega-grupo); percentile ajusta granularidad (p70_q2 = 15
grupos intra 0.91); tolerance_bins no cambia agrupamiento. `results/granularidad/sweep.json`.
`results/granularidad/sweep.json` + `sweep.md`. Hallazgos:

1. **link_quorum domina**: q1 colapsa el video en ~1 mega-grupo (una señal
   basta para enlazar todo transitivamente). q2 produce 8-15 grupos.
2. **percentile ajusta la granularidad fina** (con q2): p70 → 15 grupos con
   coherencia transcript 0.91; p80 → 11.3 con 0.83; p90 → 8.3 con 0.76.
   Trade-off claro: más grupos = más coherentes.
3. **tolerance_bins no cambia el agrupamiento** (solo confirm_rate de cortes):
   correcto por diseño — es umbral de confirmación, no de agrupación.
4. no_topic y needs_review = 0 en el grid (los singletons sin soporte ya
   quedaron fuera por el fix del ticket 001).

Candidatos para revisión cualitativa (003): **p70_q2** (fino, 15 grupos,
intra 0.91) y **p80_q2** (medio, 11.3 grupos, intra 0.83).
