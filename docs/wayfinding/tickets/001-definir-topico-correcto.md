---
title: "Definir qué es un tópico correcto para el humano"
labels: ["wayfinder:grilling", "wayfinder:HITL", "wayfinder:resolved"]
assignee: edgar.chambilla
resolved: true
blocks: []
---

## Question

Antes de medir si la granularidad es correcta: ¿qué considera el humano que un
"tópico correcto" debe ser? ¿Un paso procedural, un tema macro, o intermedio?
¿Puede un tópico ser de 4 segundos? ¿Qué hacer con singletons sin soporte?

## Resolution

Resuelta en grilling 2026-09-25 con los grupos reales de 98MoyGZKHXc como
ancla. Cuatro criterios:

1. **Singletons sin soporte multi-señal → SIN TÓPICO** (etiqueta fuera de
   versiones; transiciones/aperturas, no son contenido).
2. **Granularidad: paso fino** — "aplicar freno de mano" (6s) ES un tópico
   correcto; no se fusiona en temas macro.
3. **Grupos largos (>10 segmentos): válidos pero marcados `needs_review`**
   para revisión de división potencial (no división automática).
4. **Granularidad única del sistema**: las versiones de consumidor cambian por
   selección de grupos, no por granularidad propia.

Implementada en `multimodal_manager.manage` (flags `no_topic` y
`needs_review`). Desbloquea 003 (con criterios de aceptación) y aporta a 005.
