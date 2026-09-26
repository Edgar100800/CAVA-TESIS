# INTEGRACIÓN A2SUM-X — módulo SegLoop + VJudge (frame-awareness)

> **Pipeline gráfico:** `docs/proyecto/PIPELINE_INTEGRACION.html` (diagrama completo, fases A-E,
> renaming propuesto: A2SUM-X → **CAVA** / CERTISUM / FRAMECAST — decisión pendiente del humano;
> el stack integrado ya no es "A2Summ extendido" sino un analizador de clips certificados con
> salida multi-versión adaptativa).

> 2026-09-22 · Diseño de integración post-cierre experimental.
> Insumos: revisión del código `~/Tesis/A2Summ/a2summ_x/` (59 módulos), resultados SegLoop
> (`RESULTS.md`, `RESULTADOS_OOD_SUMM.md`), ADRs 0001-0007.

## 1. Cómo está construido A2SUM-X (revisión)

Pipeline video-céntrico, texto/audio opcionales (`a2summ_x/model.py`):

```
io/      video_loader → shot_boundary (KTS sobre features por frame)
         → shot_packager (pack_by_shot) → temporal_metadata
features/ visual (frame_sampler → encoders → TemporalClipAggregator)
          text (transcript_loader → segmenter → RoBERTa → time_mapper)
          audio (spectrogram → encoder → aggregator)          [opcional]
adapters/ ModalityAdapter (D_in → d_model, L2)
fusion/   HierarchicalFusionTransformer (frames→shots→video)
          + FlexibleCrossModalAlignment (shots ← texto/audio)
heads/    ModalityGating → FusedSceneRelevanceHead → scene_relevance [B,S]
          + ScoreCalibration (temperature scaling)
selection/ topk_select → budget → diversity → temporal_smoothing
          → playlist_builder (change_points + índices seleccionados)
generation/ scene_explainer (interpretabilidad de gating/alineación)
          caption_generator (STUB — interfaz sin implementar)
          summary_generator
```

Salida consumible: **playlist de segmentos** (`{'shot', 'start', 'end', 'score'}`) ordenada
temporalmente, con explicación de escena.

**Observaciones clave para la integración:**

1. La segmentación actual es **KTS sobre features** (`io/shot_boundary.py`) — el mismo método
   que genera los `change_points` de TVSum/SumMe. Es genérico pero ciego a semántica, y para
   videos nuevos sin benchmark requiere elegir nº de cortes a priori.
2. `selection/playlist_builder` corta **por índices de shot** sin noción de integridad
   semántica: puede partir un take continuo a mitad.
3. `heads/calibration` es temperature scaling (aprendible) — distinto del protocolo de
   certificación SegLoop (isotonic + LCB Wilson + three-state); no interfieren, se complementan.
4. `generation/caption_generator` es un **stub**: la explicación de escena por VLM es una
   pieza diseñada pero sin implementar → ahí entra naturalmente el VJudge.
5. La unidad de trabajo de A2SUM-X es el **shot/segmento**: todo el fusion y scoring operan
   sobre `shot_ids` — exactamente la unidad que SegLoop produce y certifica.

## 2. Qué aporta SegLoop + VJudge (evidencia que lo respalda)

| Aporte | Evidencia SegLoop |
|---|---|
| Segmentación de fronteras visuales portable (sin elegir nº de cortes) | TransNetV2 + features: AP 0.776 TVSum, 0.732 SumMe, 0.78 BBC zero-shot (4 dominios) |
| **Integridad de clips certificada** ("aquí NO se corta") | Continuidad precision 0.93-0.97, LCB 0.947, three-state con abstención |
| Calibración con garantías (no solo temperatura) | isotonic + Wilson LCB, fingerprints SHA-256 |
| Juez VLM frozen como explicador/sonda semántica | existence head 0.72-0.78 4 dominios; reproducibilidad determinista del stack |
| Conocimiento de límites | importancia NO codificada (ρ≈0.04-0.06 TVSum/SumMe); streams sin cortes → modo segment-level |

## 3. Contrato del módulo (`a2summ_x/io/frame_awareness.py` — adaptador nuevo)

```python
frame_awareness.analyze(video_path, *, mode="cuts"|"segments", judge=...) -> FrameAwareness

FrameAwareness:
  shots.ndjson        # schema shot_packager (compatibilidad directa con A2SUM-X)
  change_points       # [S,2] frames — drop-in para HierarchicalFusion/playlist_builder
  boundary_scores     # [S-1] calibrated_probability del ensemble frozen (ranking de cortes)
  certificates        # por frontera: CONTINUITY_CERTIFIED / CUT / ABSTAIN + LCB
  certified_spans     # intervalos "no cortar adentro" (para selection)
  fps, fingerprints   # trazabilidad
```

Reglas del contrato (heredadas de ADRs):
- Certificados y features con fingerprint; reproducibilidad determinista (demostrada, job 52193
  del propio SegLoop).
- El GT jamás entra al módulo; la evaluación es externa (lección ADR-0007: validar por datos
  efectivos).
- Modo `segments` para contenido stream-like (BLiSS): grid fijo de 2s + márgenes del juez, sin
  prometer cortes.

## 4. Fases de integración (cada una con gate pre-registrado)

### Fase A — Adaptador de contrato (io) · 🟢 IMPLEMENTADA (2026-09-24)

- **Lado SegLoop:** `scripts/frame_awareness_run.py` — por video: ensemble frozen sobre todos
  los shots → `frame_awareness.json/.ndjson` (change_points frames, boundary scores,
  certificados CONTINUITY_CERTIFIED/PREDICTED_CUT/ABSTAIN, fingerprint). Modo `judge`
  (márgenes VLM) reservado en schema.
- **Lado A2Summ:** `a2summ_x/io/frame_awareness.py` — `load_frame_awareness()` (change_points
  drop-in + boundary_channel + certified_spans) y `check_playlist_integrity()`.
- **Round-trip verificado** en video TVSum real (34 shots → 3 continuidades certificadas,
  3 cortes predichos, spans certificados colapsados, 0 violaciones en playlist simulada,
  fingerprint `6773ddaf`).
- Pendiente: barrido de los 50 videos (batch) y `judge` mode con A6000.

### Fase A-orig — Adaptador de contrato (io) [diseño original]
`frame_awareness.py` envuelve SegLoop (ingest→features→ensemble) y produce `change_points`
compatibles. **Gate:** round-trip en TVSum — playlist construida con change_points de SegLoop
debe procesar 50/50 videos en A2SUM-X sin cambios de schema (ya validado indirectamente: AP
0.776 vs KTS-GT).

### Fase B — Integridad certificada en selection
`playlist_builder` extiende: dentro de `certified_spans` (continuidad certificada), un shot
se selecciona **completo o no se selecciona**; los cortes solo en fronteras no certificadas.
**Gate:** 0 violaciones de integridad en playlists TVSum/SumMe + F1/τ/ρ no peor que KTS
baseline (diferencia ≤ ruido entre splits).

### Fase C — Canal de frontera en el score head
`boundary_scores` entra como canal auxiliar por-shot al `FusedSceneRelevanceHead` vía gate
zero-init (aprende si sirve; el head conserva su rol de importancia — no mezclamos: los
hallazgos OOD demostraron que frontera ≠ importancia, así que el canal es de *integridad de
transición*, no de relevancia). **Gate:** F1 TVSum ≥ baseline ± ruido; si el canal aporta,
medirlo en ablation estándar del repo (`eval/ablation.py`).

### Fase D — VJudge como scene explainer (generation)
Implementar `caption_generator` + extender `scene_explainer` con el juez frozen (Qwen2.5-VL,
infra existente en `segloop/judge/qwen_judge.py`): descripción natural-language de cada escena
seleccionada + justificación de continuidad certificada. **Gate:** 100% de escenas de la
playlist con explicación generada; revisión cualitativa en 10 muestras.

### Fase E — BLiSS/streams (dos vías)
1. **Ejecutable YA con datos locales**: `a2summ_x` corre sobre BLiSS con features CLIP 512-d
   (d_video=512; el paper verificó el baseline A2Summ en BLiSS con Δ<0.004). Cierra la
   evaluación BLiSS pendiente del paper y ejercita el alignment-guided self-attention —
   BLiSS es el único dataset con `sentence_time` (ADR-0008, F1 nueva prioridad).
2. **Requiere videos crudos** (SegLoop VJudge/ensemble sobre streams reales): email a
   bohe@umd.edu — única vía (Behance sunset del livestreaming de usuarios).

## 5. Lo que NO entra (explícito)

- Fine-tuning del juez (ADR-0002).
- Usar `boundary_scores` como señal de importancia/relevancia (ρ≈0 medido en TVSum/SumMe).
- Iteración 2 del bucle dentro de A2SUM-X (el bucle vive en SegLoop; A2SUM-X consume su salida).

## 6. Orden de trabajo propuesto

1. Fase A (adaptador + round-trip TVSum) — ~1 sesión, sin GPU pesada.
2. Fase B (selection certificada) — ~1 sesión + gate.
3. Fase D (VJudge explainer) — reusa infra SegLoop; stub ya existe.
4. Fase C (canal auxiliar) — después, con entrenamiento A2SUM-X andando.
5. Fase E — al recibir URLs de BLiSS.
