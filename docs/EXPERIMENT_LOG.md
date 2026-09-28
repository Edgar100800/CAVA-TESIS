# EXPERIMENT LOG — CAVA

> Registro de experimentos: configuración → resultado → invalidación.
> Sin comentarios ni feedback. Decisiones derivadas viven en ADRs.
> Cada experimento define qué resultado lo invalidaría.

---

## EXP-001 · Multi-tolerancia fronteras vs GT escenas
- **Fecha:** 2026-09-25
- **Corpus:** 97 películas MovieNet (signals: transcript TF-IDF + visual SigLIP)
- **Gestor:** sin fusión, p80, link_quorum=2, tolerance_bins=1
- **Configuración:** tolerancias ±1/±2/±5/±10/±20 shots

| tolerancia | P | R | F1 |
|---|---|---|---|
| ±1 | 0.253 | 0.808 | 0.369 |
| ±2 | 0.275 | 0.873 | 0.400 |
| ±5 | 0.301 | 0.942 | 0.436 |
| ±10 | 0.314 | 0.974 | 0.454 |
| ±20 | 0.320 | 0.991 | 0.463 |

- **Resultado:** recall → 0.99 con ±20; precision estable ~0.25-0.32.
- **Invalidación:** si el baseline aleatorio supera P o R a cualquier tolerancia,
  la señal no aporta sobre azar.
- **Baseline azar:** no calculado en este experimento (añadido en EXP-007).

---

## EXP-002 · Barrido de configuración (grid quant)
- **Fecha:** 2026-09-25 · 97 películas · 12 configuraciones

| config | grupos | P@±1 | R@±1 | F1@±1 | intra transcript | intra visual |
|---|---|---|---|---|---|---|
| p70_q1 | 1.3 | 0.466 | 0.245 | 0.299 | 0.439 | 0.940 |
| p70_q2 | 15.0 | 0.212 | 0.892 | 0.330 | 0.909 | 0.970 |
| p80_q1 | 1.3 | 0.550 | 0.172 | 0.247 | 0.439 | 0.940 |
| p80_q2 | 11.3 | 0.253 | 0.808 | 0.369 | 0.826 | 0.966 |
| p90_q1 | 1.0 | 0.637 | 0.077 | 0.129 | 0.393 | 0.936 |
| p90_q2 | 8.3 | 0.322 | 0.622 | 0.398 | 0.759 | 0.961 |

- **Resultado:** link_quorum domina (q1 colapsa en mega-grupo); percentile
  ajusta granularidad fina; tolerance_bins no afecta agrupamiento.
- **Invalidación:** si q2 NO produce más grupos que q1, o si P y R no muestran
  trade-off, el gestor no está respondiendo a los parámetros.

---

## EXP-003 · Ablation por señal (MovieNet p80_q2_t1)
- **Fecha:** 2026-09-25 · 97 películas

| señal | P | R | F1 |
|---|---|---|---|
| transcript solo | 0.100 | 1.000 | 0.178 |
| visual solo | 0.098 | 1.000 | 0.175 |
| ambas (consenso) | 0.275 | 0.788 | 0.386 |

- **Resultado:** cada señal sola sobre-predice masivamente (R=1.0 = corta en
  cada shot). El consenso filtra ruido y sube P a 0.275.
- **Invalidación:** si una señal sola supera el consenso en F1, la
  complementariedad no existe y el consenso es innecesario.

---

## EXP-004 · VJudge razonamiento sobre keyframes MovieNet
- **Fecha:** 2026-09-25 · 3 películas (Rear Window + 2 más) · A100 shard

- **Resultado:** mecanismo verificado — el juez frozen lee keyframes por shot
  y produce descripción semántica (qué pasa + momento narrativo).
- **Invalidación:** N/A (verificación de mecanismo, no experimento de hipótesis).

---

## EXP-005 · Piloto de salida real (CAVA output)
- **Fecha:** 2026-09-25 · 3 videos TVSum

- **Resultado:** 114 clips mp4 cortados en 3 perfiles + playlists + contexto.
- **Invalidación:** N/A (verificación de pipeline, no de hipótesis).

---

## EXP-006 · Análisis dual de granularidad
- **Fecha:** 2026-09-25 · 97 películas

| Camino | P | R | F1 |
|---|---|---|---|
| Colapsado a GT (±10 shots) | 0.94 | 0.77 | **0.84** |
| Grano fino (sin colapsar) | 0.25 | 0.81 | 0.37 |

- **Resultado:** el sistema detecta estructura narrativa correctamente cuando se
  alinea a granularidad GT (F1 0.84).
- **⚠️ INVALIDADO:** el colapso usaba GT para snappear predicciones (data
  leakage). El F1 0.84 mide la distancia que el colapso eliminó, no la calidad
  del sistema. Ver ticket de invalidación más abajo.

### Invalidación EXP-006

**F1 0.84 INVÁLIDO** — el `collapse_predictions(pred, gt, window)` selecciona
predicciones usando el GT como referencia y luego evalúa esas mismas
predicciones contra el GT. Es data leakage: el GT entra en la predicción a
través del colapso. El F1 honesto es el de grano fino: **0.37** (EXP-001,
±1 shot).

Lección: nunca seleccionar predicciones usando el GT antes de evaluar.

---

## EXP-007 · Offset sweep (E1 del experiment_granularity.py)
- **Fecha:** 2026-09-25 · 35 películas · p80_q2_t1

| offset | F1 |
|---|---|
| -10 | 0.274 |
| -6 | 0.280 |
| -4 | 0.289 |
| -2 | 0.292 |
| **0** | **0.381** |
| +2 | 0.332 |
| +4 | 0.288 |
| +6 | 0.282 |
| +8 | 0.280 |
| +10 | 0.274 |

- **Resultado:** F1 pico en offset 0, decrece simétricamente. NO hay offset
  sistemático corregible.
- **Invalidación:** si un offset ≠ 0 produjera F1 > 0.40, habría un
  desalineamiento temporal corregible.

---

## EXP-008 · Ablation complementariedad (E3)
- **Fecha:** 2026-09-25 · 35 películas

| Señal | F1 |
|---|---|
| transcript solo | 0.175 |
| visual solo | 0.175 |
| **ambas** | **0.381** |

- **Resultado:** las señales son **complementarias** (2.2× al combinar).
  Cada una lleva información que la otra no tiene.
- **Invalidación:** si una señal sola alcanzara F1 ≥ 0.35, la
  complementariedad no existe.

---

## ⚠️ INVALIDACIONES

| EXP original | Claim invalidado | Razón |
|---|---|---|
| EXP-006 (F1 0.84 colapsado) | "El sistema detecta estructura narrativa con F1 0.84" | Colapso circular: snappeó predicciones al GT antes de evaluar (data leakage) |
| ADR-0008 implícito (F1 0.40 como quality bar) | "El agregador temático alcanza F1 0.40 vs GT" | El 0.40 es F1 a granularidad GT que no corresponde al diseño paso fino |
| Barrido granularidad v2 (`results/granularity_sweep_v2.INVALID_visual_only.json`) | Resultados del grid sobre 3 pilotos con una sola señal | Solo visual: link_quorum=2 inalcanzable (todo no_topic), tolerance_bins sin efecto. Descartado; el barrido válido de 2 señales es EXP-002 (`results/granularidad/sweep.md`) |
| EXP-010 | "El VJudge integrando frames + transcript lee fronteras mejor que cada modalidad sola" | AP mm 0.512 < frames 0.540 (2/3 películas); como votante no mejora Δ-vs-azar (+0.060 vs +0.069) |
| EXP-002 (columna confirm_rate) | "tolerance_bins=1 confirma ~0.24–0.54 de los cortes candidatos" | `consensus_cuts` cuenta cada índice de la ventana ±tolerance_bins (hasta 3× por corte); el salto t0→t1 está inflado. Grupos y coherencia no se ven afectados (hallado en EXP-011) |

---

## EXP-009 · VJudge reasoning como señal de proximidad temática
**2026-09-25 · 3 videos TVSum · 103 shots · TF-IDF sobre reasoning text**

**Métrica:** AUC local-vs-remoto — P(sim(i,j) > sim(i,k)) donde (i,j) son shots
a ≤3 posiciones y (i,k) a >10 posiciones.

| Señal | AUC local-vs-remoto |
|---|---|
| visual (SigLIP por shot) | **0.658** |
| reasoning (VJudge TF-IDF) | 0.510 |

- **Resultado:** el razonamiento del VJudge NO separa tópicos locales de
  remotos mejor que el visual. AUC ≈ 0.51 ≈ azar. El visual sí (0.66).
- **Invalidación:** la hipótesis "el razonamiento del VJudge captura
  estructura temática que el visual no captura" **se invalida** en este
  setting: AUC 0.51 ≈ 0.50 (azar).
- **Nota:** el reasoning se mide con TF-IDF sobre texto generado — la señal
  depende de la calidad del texto generado. Un embedder semántico (sentence
  transformer) podría capturar estructura que TF-IDF no ve. Pendiente.

`data/cava_pilot/exp009_simple.json`

---

## EXP-009b · Reasoning VJudge con embedder semántico (bge-base)
- **Fecha:** 2026-09-28
- **Corpus:** 3 videos TVSum · 103 shots (mismos datos que EXP-009)
- **Configuración:** protocolo de EXP-009 sin cambios; reasoning embebido con
  `BAAI/bge-base-en-v1.5` (CLS, L2) además de TF-IDF

| Señal | AUC local-vs-remoto |
|---|---|
| visual (SigLIP por shot) | **0.658** |
| reasoning (TF-IDF) | 0.510 |
| reasoning (bge-base) | 0.506 |

- **Resultado:** el embedder semántico no cambia nada (0.506 ≈ 0.510 ≈ azar).
  El fallo de EXP-009 no es de TF-IDF: el texto por shot aislado no lleva la
  señal que esta métrica busca.
- **Invalidación:** si bge hubiera superado a visual, la conclusión de EXP-009
  habría sido un artefacto de TF-IDF. No ocurre; EXP-009 se sostiene.
- **Limitación de la métrica:** positivo = shots a ≤3 posiciones, negativo = a
  >10. Esto mide suavidad temporal, no tópico, y penaliza justo lo que CAVA
  busca (agrupar segmentos NO contiguos del mismo tópico). El visual gana en
  parte porque shots contiguos se parecen. La prueba con GT de escena es EXP-010.

`data/cava_pilot/exp009_bge.json` · `scripts/exp009_bge.py`

---

## EXP-010 · Narrative interpreter: VJudge lee segmentos (frames + transcript)
- **Fecha:** 2026-09-28 (pre-registro; job 53426, 47 min en ds001)
- **Corpus:** MovieNet tt0047396, tt0049730, tt0061418 · 3064 shots · 370 cortes GT
- **Configuración:** segmentos fijos de 5 shots (614); Qwen2.5-VL-7B frozen,
  greedy, prompt TOPIC/FUNCTION/SUMMARY. Condiciones: `mm` (3 keyframes +
  transcript), `frames` (solo keyframes), `text` (solo transcript). Lecturas
  embebidas con bge-base (texto completo y solo TOPIC) y TF-IDF.
- **Medidas:**
  - A) lectura sola: AP de la novedad en bordes de segmento (sin umbral; azar =
    tasa positiva) y F1@±5/15/30 s a p80, con azar de igual nº de cortes.
  - B) votante: `manage()` visual+transcript vs visual+transcript+narrative
    (sin fusión, p80, q1/q2, t1), F1 de cambios de etiqueta vs azar.
- **Gate:** F1@±15 s > 0.30 y por encima del azar.
- **Invalidación:**
  - si `mm` no supera a `frames` y a `text` en AP, la integración dentro del
    VJudge no aporta; el intérprete sería un canal más.
  - si añadir `narrative` como votante no mejora Δ-vs-azar de
    visual+transcript, la lectura no aporta al consenso.
- **Limitación conocida:** con escenas de ~5 shots, un segmento de 5 shots
  suele cruzar una frontera GT (62 % de bordes positivos en tt0049730). La
  escena GT es un proxy más fino que el tópico que busca CAVA.

`scripts/narrative_interpreter.py` (GPU) · `scripts/narrative_eval.py` (CPU) ·
salida `results/exp010_narrative.json`

### Resultado EXP-010
AP de la novedad en bordes de segmento (TOPIC con bge; azar = tasa positiva):

| película | azar | mm | frames | text |
|---|---|---|---|---|
| tt0047396 | 0.373 | 0.470 | **0.533** | 0.460 |
| tt0049730 | 0.623 | **0.728** | 0.694 | 0.636 |
| tt0061418 | 0.269 | 0.340 | **0.393** | 0.335 |
| media | 0.422 | 0.512 | **0.540** | 0.477 |

Votante en `manage()` (p80, q2, t1; F1@±15 s, media de 3 películas):

| señales | cortes | F1 | azar | Δ |
|---|---|---|---|---|
| visual+transcript | 282 | 0.450 | 0.381 | +0.069 |
| visual+transcript+narrative | 76 | 0.333 | 0.273 | +0.060 |

- **Resultado:** las tres lecturas superan al azar (AP +0.05 a +0.12), pero
  `mm` no supera a `frames` (2 de 3 películas lo pierden). Añadir el
  transcript al VJudge no ayuda, y el transcript solo es la peor lectura.
  Como votante, la lectura reduce los cortes 282→76 sin mejorar Δ-vs-azar.
- **Gate:** F1@±15 s > 0.30 solo lo pasan configuraciones con muchos cortes,
  y su F1 queda a +0.06–0.07 del azar. El F1 lo explica sobre todo el nº de
  cortes, no su posición.
- **⚠️ INVALIDADO (pre-registrado):** "el VJudge integrando frames + transcript
  lee fronteras narrativas mejor que cada modalidad sola". Tampoco se sostiene
  "la lectura narrativa mejora el consenso".
- **Diagnóstico:**
  1. Lecturas independientes: cada segmento se describe sin ver al vecino. La
     novedad entre textos generados por separado mezcla cambio de tópico con
     varianza de redacción (mm/frames responden en markdown, text en plano).
  2. Techo estructural: con ventanas fijas de 5 shots, solo 45–80 % de los
     cortes GT caen a ±15 s de algún borde posible.
  3. Las 3 películas son del split *train* de MovieNet-318. No hay fuga aquí
     (nada supervisado), pero bloquea usar el ensemble SegLoop en ellas.

`results/exp010_narrative.json`

---

## EXP-011 · Paso 0 — baseline jerárquico (escenas y beats de trama)
- **Fecha:** 2026-09-28
- **Corpus:** 19 películas MovieNet-318 *val* con señales + `annotation/*.json`
  `story` (párrafos de sinopsis alineados a shots). GT medio: 129 escenas,
  17 beats, 1353 shots. Los beats varían de 4 a 68 por película según el
  detalle de la sinopsis.
- **Gestor:** sin fusión, visual SigLIP + transcript TF-IDF, t1,
  percentil {50…98} × link_quorum {1, 2}; fronteras = cambios de etiqueta.
- **Métricas:** F1 escena ±15 s, F1 beat ±60 s (solo dentro del tramo
  anotado), Pk por nivel, scene_prec (corte a ±1 shot de un corte de escena).
  Todo contra azar con el mismo nº de cortes.

| sistema | tópicos | escena F1 (azar) | escena Pk (azar) | beat F1 (azar) | beat Pk (azar) | scene_prec (azar) |
|---|---|---|---|---|---|---|
| p70_q1 | 60 | 0.325 (0.195) | 0.319 (0.420) | 0.236 (0.218) | 0.527 (0.566) | 0.487 (0.204) |
| p80_q1 | 36 | 0.260 (0.144) | **0.306** (0.389) | 0.236 (0.216) | 0.515 (0.547) | 0.549 (0.207) |
| p90_q1 | 14 | 0.146 (0.065) | 0.311 (0.355) | 0.175 (0.151) | 0.467 (0.494) | **0.617** (0.208) |
| p80_q2 | 384 | 0.384 (0.302) | 0.529 (0.608) | 0.091 (0.090) | 0.590 (0.593) | 0.336 (0.207) |
| p90_q2 | 233 | **0.427** (0.305) | 0.429 (0.550) | 0.139 (0.135) | 0.580 (0.590) | 0.377 (0.208) |

- **Resultado:**
  - A nivel escena hay señal: F1 +0.12 sobre el azar (p90_q2) y Pk −0.08
    (p80_q1).
  - A nivel beat de trama las señales actuales están **en el azar** en todas
    las configuraciones: F1 como mucho +0.02, Pk como mucho −0.04.
  - Cuando ambas señales coinciden (q1), el corte cae en un corte de escena
    real 3× más que el azar (scene_prec 0.55–0.62 vs 0.21).
- **Lectura:** visual + transcript por novedad ven cambios de escena, no de
  trama. El nivel beat es lo que tienen que aportar las capas nuevas (VJudge,
  enlace multimodal, agregador adaptativo).
- **Referencia pre-registrada para los pasos 1–2:** un agregador adaptativo con
  UNA salida debe superar, contra el azar, al mejor percentil fijo elegido con
  GT por nivel (escena Δ F1 +0.12 · beat Δ F1 +0.02 / Δ Pk −0.04), sin bajar
  scene_prec del mejor fijo de ese nivel de granularidad.
- **Defecto hallado:** `manage().consensus_cuts` marca cada índice de la ventana
  ±tolerance_bins donde se alcanza la mayoría, así que un corte se reporta hasta
  3 veces seguidas. Las filas `consensus` del JSON no son válidas.
- **Nota:** Pk a nivel beat tiende a ~0.43 con muy pocos cortes, para el
  sistema y para el azar por igual; se lee solo como diferencia contra el azar.

`results/exp011_hierarchy_baseline.json` · `scripts/eval_hierarchy.py`

