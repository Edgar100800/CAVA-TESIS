# WAYFINDER MAP — Afinado de granularidad temática

> Tracker local-markdown (repo sin tracker remoto). Mapa: este archivo (etiqueta
> `wayfinder:map`). Tickets: `tickets/`. Sesión reclama ticket asignándolo
> antes de trabajar. Nunca resolver más de un ticket por sesión.

## Destination

Una configuración de granularidad temática validada — percentil, link_quorum y
tolerance_bins fijados con registro cuantitativo y cualitativo, aceptada por el
humano sobre los 3 videos piloto — lista para fijarse como default de CAVA y
alimentar la producción de versiones por consumidor.

## Notes

- Gestor: `topicagg/multimodal_manager.py` (ADR-0001: sin fusión; consenso de
  votos por señal). Perillas: `percentile`, `link_quorum`, `tolerance_bins`,
  pesos por señal.
- Corpus de medición: 3 videos TVSum del piloto CAVA (`data/cava_pilot/`).
- Skills de sesión: documentation-and-adrs (registros), grilling/domain-modeling
  (HITL). Regla de proyecto: toda evaluación valida por sus datos efectivos
  (lección ADR-0007 de SegLoop).
- Datos disponibles: ASR tiny por video, features SigLIP+BaSSL por shot,
  razonamiento VJudge por clip seleccionado. OCR/audio-espectro: no extraídos.

## Decisions so far

- [ADR-0001 Sin fusión de representaciones](../adr/0001-sin-fusion-de-representaciones.md):
  las señales votan; el tópico nunca emerge de un embedding combinado.

## Not yet specified

- Cómo se incorporan OCR y audio-espectro como votantes cuando se extraigan
  (cuelga de la extracción misma).
- Si la granularidad afinada debe ser única global o por-género de contenido
  (cuelga de ver la varianza entre los 3 pilotos).

## Out of scope

- Reabrir la fusión de representaciones (cerrada por ADR-0001 y el diagnóstico v1).
- Videos crudos de BLiSS (fuera del esfuerzo; requiere email al autor).
- Métricas F1 contra TVSum/SumMe como evaluación principal (ADR-0008).
