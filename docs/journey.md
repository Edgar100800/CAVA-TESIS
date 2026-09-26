# Jornada de implementación — CAVA

> Registro narrativo de cómo llegamos al diseño actual. Cada sección es una
> decisión con su evidencia; los detalles técnicos viven en los documentos
> pilar referenciados al final.

## 1. Punto de partida: A2Summ-X v1

La arquitectura v1 (`~/Tesis/A2Summ/a2summ_x`, congelada tras el paper) era un
pipeline multimodal frame-by-frame: KTS segmentaba por features, video y texto
se adaptaban a un espacio común, la alineación cruzada inyectaba el transcript
sobre cada shot, y un gating softmax competía modalidades hacia un score único.

El paper cerró una pregunta: en TVSum, la intervención arquitectónica (rama de
texto, ΔF1 +0.033, p=0.014) movió el desempeño donde el cambio de representación
(V-JEPA-2, p=0.82) no lo hizo.

## 2. El diagnóstico: la señal visual muere por diseño

El análisis mecánico (`topicagg/video-signal-analysis.md`) identificó tres
puntos donde el texto reescribe al video: la alineación inyecta el transcript
sobre la query visual, el gating softmax compite en peso cero-suma, y la cabeza
lee el blend. Cuatro fuentes independientes convergieron: gating texto
0.75–0.89; colapso visual de GraphVSum en BLiSS; importancia ρ≈0 en TVSum/SumMe;
streams sin cortes.

Conclusión: no era un bug. Fusionar señales en una representación única
**re-escribe unas con otras antes de decidir**.

## 3. La regla fundacional de v2: sin fusión

El rediseño excluye la fusión a nivel arquitectura: cada señal (transcripción,
texto en pantalla, voz, imagen) emite sus propias fronteras y sus propios
grupos, y el tópico emerge por **consenso de votos** (mayoría ponderada,
union-find, provenance por señal). Núcleo: `topicagg/multimodal_manager.py`.

## 4. Pilotos

- **BLiSS (transcripts reales):** el mecanismo funciona; hallazgo de calibración
  (RoBERTa domina por locutor → sobre-fragmentación; tuning pendiente).
- **TVSum real (3 videos):** transcript ASR + visual SigLIP/BaSSL + densidad de
  voz → los grupos resultantes son **pasos procedurales del contenido**
  (seguridad → evaluar → inflar → troubleshooting). Outputs en
  `data/cava_pilot/<video>/topics_multimodal.json`.
- **Validación OOD paralela:** fronteras robustas en 4 dominios (AP 0.73–0.78);
  importancia humana ρ≈0 → la frontera no es importancia (diseño, no defecto).

## 5. El juez como razonamiento por clip

Cada clip seleccionado recibe del juez frozen (Qwen2.5-VL, zero-shot) una
explicación: qué pasa y qué tópico trata, combinando imagen y transcript. Estas
explicaciones son la **señal textual base del aprendizaje de agregación**: los
embeddings de los razonamientos —no de los frames crudos— permiten enlazar el
clip donde el tema aparece con el clip donde se retoma.

## 6. Integración con el analizador

Contrato `frame_awareness` entre repos (change_points + scores + certificados +
spans, con fingerprint). Fase A verificada con round-trip sobre video real.
La selección del analizador incorpora integridad certificada: dentro de un span
certificado, un clip se toma completo o no se toma. Detalle:
`docs/integration-cava.md`.

## 7. Dónde estamos

- Gestor multimodal sin fusión: implementado y verificado (sintético + real).
- Captions VJudge: generadas sobre el piloto.
- Abierto: **afinado de granularidad** con registro cuantitativo y cualitativo
  (`docs/granularity-plan.md`), y señales OCR/audio por extraer.
