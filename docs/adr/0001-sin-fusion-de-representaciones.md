# ADR-0001: Sin fusión de representaciones — tópicos por consenso de votos

- Estado: **Aceptado** (2026-09-25 — decisión fundacional de CAVA, hereda la lección de
  ADR-0007 y ADR-0008 de SegLoop)
- Contexto: diagnóstico v1 (`topicagg/video-signal-analysis.md`) + demo multimodal real

## Contexto

En A2Summ-X v1, video y texto se fundían en una representación única (alineación cruzada +
gating softmax + head sobre el blend). El resultado medido: el texto reescribía al video
(gating 0.75–0.89; colapso visual en BLiSS; importancia ρ≈0 en OOD). Cualquier agregador que
consuma un embedding fusionado hereda ese defecto: la fusión re-escribe las señales antes de
decidir.

## Decisión

CAVA **no fusiona representaciones**. Cada señal (transcript, OCR en pantalla, audio, video)
emite independientemente:

1. sus **fronteras** candidatas (percentil propio),
2. sus **etiquetas de tópico** por segmento (sus propios cortes).

El tópico emerge por **consenso de votos**, nunca por combinación de representaciones:

- **Frontera confirmada** si la suma de pesos de señales votando corte en ±tolerance_bins
  alcanza la mayoría de las señales activas.
- **Enlace (i, j)** (mismo tópico) si ≥ `link_quorum` señales agrupan i y j juntos
  (union-find, grupos con provenance por señal).

Implementación: `topicagg/multimodal_manager.py::manage`.

## Consecuencias

- La identidad de cada señal se preserva de punta a punta; el fallo de v1 queda excluido
  arquitecturalmente, no por calibración.
- Los pesos por señal son parámetros explícitos (UNTUNED): su afinado es el plan de
  granularidad (`docs/granularity-plan.md`).
- Un tópico sin soporte multi-señal puede quedar como singleton: es honesto, no se fuerza.
- Prohibido introducir embeddings o scores fusionados en cualquier punto del pipeline de
  tópicos (checklist de revisión).
