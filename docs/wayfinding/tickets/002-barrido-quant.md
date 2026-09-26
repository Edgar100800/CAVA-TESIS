---
title: "Barrido de configuraciones con registro cuantitativo"
labels: ["wayfinder:task", "wayfinder:AFK"]
assignee: 
blocks: ["005-decidir-default"]
---

## Question

_(ticket de ejecución: nada que decidir, solo registrar)_

Correr `manage()` sobre los 3 videos piloto en el grid:
percentile ∈ {70, 80, 90} × link_quorum ∈ {1, 2} × tolerance_bins ∈ {0, 1},
registrando por configuración: nº de grupos, tamaños (min/med/max), coherencia
intra por señal, separación inter, provenance, tasa de cortes confirmados.

## Resolution

Resultados en `results/granularidad/` (un JSON por configuración + tabla
resumen). Registrado 2026-09-2X.
