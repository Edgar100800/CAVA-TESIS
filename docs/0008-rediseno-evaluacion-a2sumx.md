# ADR-0008: Los benchmarks actuales no miden el propósito de A2SUM-X — rediseño de evaluación

- Estado: **Aceptado** (2026-09-22)
- Contexto: integración A2SUM-X · motivado por la revisión del propósito real de la arquitectura

## El desalineamiento (por qué los datasets actuales no son truthful)

El propósito de A2SUM-X es **segmentar el video en clips con contexto y producir múltiples
iteraciones/versiones del contenido en formatos que se adaptan al consumidor**. La
implementación lo refleja (`a2summ_x/`):

- `selection/budget.py` — knapsack por **presupuesto de duración** (restricción del consumidor)
- `selection/diversity.py` — MMR anti-redundancia (versiones no repetitivas)
- `selection/playlist_builder` — playlists consumibles ordenadas
- `generation/` — captions/explicaciones por escena + resumen textual multimodal (contexto)

Pero la evaluación que veníamos corriendo mide **otra cosa**:

| Benchmark | Qué mide de verdad | Qué NO mide del propósito |
|---|---|---|
| TVSum/SumMe | F1 del ranking vs importancia crowd en shots de 2s | Integridad de clips, contexto, multi-versión, adaptación |
| MovieNet/BBC | AP de fronteras vs escenas GT | Lo mismo + un solo output fijo |
| KTS change_points | Pre-procesamiento, no propósito | — |
| BLiSS | Summaries + importancia en streams | Sin videos crudos (corto plazo) |

Un sistema que produzca **una** versión con F1 alto contra **una** GT puede fallar el
propósito completo: partir clips a mitad, no generar contexto, no adaptarse a ningún
consumidor. La evidencia OOD ya lo insinuó (cortes ≠ importancia, streams sin cortes).

## Decisión: qué debe medir la evaluación A2SUM-X (P1-P4)

- **P1 Integridad de segmentación**: los clips son unidades coherentes (no cortan a mitad de
  acción); cobertura de la línea de tiempo por segmentos certificados.
- **P2 Contexto por segmento**: calidad de captions/explicaciones generadas
  (`generation/`) — precisión vs el contenido visual/transcript.
- **P3 Multi-versión adaptativa**: mismo input → versiones distintas bajo restricciones de
  consumidor (presupuestos 15s/30s/60s, perfiles) — cumplimiento de presupuesto, cobertura
  del contenido núcleo, diversidad entre versiones, consistencia entre presupuestos.
- **P4 Multi-GT**: comparar contra la POBLACIÓN de resúmenes humanos (varios GT por video),
  no contra una sola GT (la literatura de multi-summary ya lo hace así).

## Datasets truthful al propósito

| Dataset | Qué aporta | Estado |
|---|---|---|
| **VideoXum** (HF `jylins/videoxum`) | ~6k videos, ~52k resúmenes multi-GT (visuales + textuales por CLIPScore) — el GT multi-versión natural | **Descargar (público, sin trabas)** |
| **BLiSS local** | Streams con importancia por segmento + summaries abstractivos + transcripts → contexto en streams | ✅ en local (sin videos crudos; eval de contexto text-side sí) |
| **Consumer-profile benchmark** (sintético, construido sobre nuestros corpora) | Perfiles de consumidor con restricciones reales (Shorts 15-60s vertical, recap 2min, highlights 10%) | a construir sobre TVSum/SumMe/BLiSS videos |
| QFVS/ViSHA (query-focused) | Intención del consumidor como condición | opcional, fase posterior |

TVSum/SumMe quedan como **sanity checks de compatibilidad** (que el sistema sigue procesándolos),
NO como evaluación principal.

## Métricas (pre-registrables por propósito)

- **M1 (P1)**: % de segmentos sin cortes percibidos internos (juez/VLM o humano); cobertura %.
- **M2 (P2)**: calidad de captions — CLIPScore caption↔visual, BERTScore vs transcript,
  VLM-as-judge pairwise.
- **M3 (P3)**: cumplimiento de presupuesto (%), coverage@budget, diversidad media entre
  versiones, consistencia entre presupuestos (core content preservado).
- **M4 (P4)**: F1/τ/ρ contra CADA summary humano + max/mean (estándar VideoXum).

## Fases de ejecución (con gates)

1. **F1 (nueva prioridad)**: harness **BLiSS-local** con `a2summ_x` sobre features CLIP 512-d
   (d_video=512) — cierra la evaluación que el paper dejó pendiente y ejercita el
   alignment-guided self-attention (único dataset con `sentence_time`). Gate: pipeline corre en
   ≥95% de los 2,542 clips test; A2Summ-X vs baseline A2Summ con t-test pareado multi-seed
   (protocolo del paper).
2. **F2**: harness VideoXum (descarga HF → loaders) + evaluación multi-GT del pipeline.
   Gate: pipeline corre en ≥95% de videos del split.
3. **F3**: contexto segment-level (captions vs abstractive_summary/transcript) sobre BLiSS.
   Gate: 500+ clips con métricas M2.
3. **F3**: consumer-profile benchmark sintético + métricas M3.
   Gate: 3 perfiles × 3 presupuestos × corpus, cobertura y cumplimiento reportados.
4. **F4** (opcional): QFVS/ViSHA.

## Revisión contra el paper final de A2Summ-X (`paper/paper_a2summ_x.tex`)

El paper (IEEEtran, 2026) cerró la etapa A2Summ con un contraste controlado riguroso:

- **Establecido:** baseline verificado doble (split~0 TVSum = 0.6383 idéntico al checkpoint
  oficial; BLiSS Δ<0.004) · rama de texto A2Summ-X Δ=+0.033 F1 en TVSum (p=0.014, N=25) ·
  control representacional V-JEPA-2 nulo (p=0.82) · palancas descartadas con evidencia
  (ventana temporal, contrastiva colapsando gating) · corrección metodológica reportada
  (el relato de una sola seed no sobrevivió multi-seed).
- **Pendiente declarado en el propio paper:** *“la evaluación sobre BLiSS queda pendiente”*
  y las amenazas: TVSum/SumMe **carecen de `sentence_time`** (sin señal temporal fina) y
  best-epoch puede favorecer al modelo más capaz.

**Reconciliación con este ADR:**

1. **No contradice — extiende.** El paper probó (bajo el benchmark F1-importancia) que en
   TVSum el factor limitante es arquitectónico; este ADR sostiene que ese benchmark no mide
   el propósito de integración (integridad/contexto/multi-versión/consumidor). Ambos conviven:
   el paper cierra la pregunta arquitectura-vs-representación del modelo; el ADR abre la
   pregunta propósito-vs-evaluación del sistema.
2. **Corrección importante a F2:** la evaluación pendiente de BLiSS **es ejecutable ya con
   datos locales** — el baseline A2Summ ya corre sobre BLiSS con features CLIP (512-d; la
   verificación Δ<0.004 del paper lo demuestra) y `A2SummX` parametriza `d_video`. No requiere
   videos crudos (solo SegLoop/VJudge los necesita para señales de frontera).
3. **BLiSS es además el único dataset con `sentence_time`** → es el único donde el módulo
   central del paper (alignment-guided self-attention) puede ejercitarse plenamente. Eleva la
   prioridad de la F2 (BLiSS-local) por encima de F1 (VideoXum).
4. **Estándares heredados al nuevo protocolo:** verificación doble de baseline antes de
   intervenir, t-test pareado multi-seed, reporte de correcciones, y validar cada control por
   sus datos efectivos (misma lección que ADR-0007).

## Consecuencias

- TVSum/SumMe/BLiSS dejan de ser la evaluación principal; sus resultados se conservan como
  compatibilidad + hallazgos de dominio (cortes robustos, importancia ausente — que ahora es
  un requisito de diseño: la importancia debe venir de otra señal).
- El bucle/certificación de SegLoop alimenta P1 (integridad); el VJudge alimenta P2 (contexto).
- Toda evaluación nueva con compuerta pre-registrada (regla ADR-0006/0007).
