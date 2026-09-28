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
| EXP-011 paso 1 | "Fusionar por continuidad multimodal supera al mejor componente" | A igual nº de cortes SegLoop solo gana en escena F1 (+0.276 vs +0.197), beat F1 (+0.043 vs +0.016) y scene_prec |
| EXP-011 paso 1b | "Los votantes de similitud deciden dónde parar mejor que el orden de SegLoop" | ρ=0.9 pre-registrado para en ~5 tópicos, igual al control; ρ=1.0 +0.017 beat F1 (~1 SE, no pre-registrado) |
| EXP-011 paso 2 / 2-R | "El VJudge relacional (contexto ±2 shots) ordena transiciones de trama mejor que SegLoop" | +0.027 ± 0.017 en 23 películas no replica: −0.002 ± 0.012 en 35 nuevas |

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

### Corrección del gestor (2026-09-28, tras EXP-011 paso 0)
Tres defectos en `topicagg/multimodal_manager.py`, con tests de regresión en
`tests/test_multimodal_manager.py`:
1. `consensus_cuts` repetía cada corte en toda la ventana ±tolerance_bins, y
   una señal con dos cortes cercanos votaba dos veces. Ahora cada señal vota
   una vez por índice y cada racha colapsa en un corte.
2. Una señal sin información (score 0, p. ej. TF-IDF en silencio) emitía
   cortes. Ahora score 0 no corta.
3. `min_gap` comparaba contra `i` en vez de `i+1`, lo que permitía cortes
   adyacentes.

Los defectos 2 y 3 cambian los cortes por señal, así que **todos los números
de `manage()` de EXP-001 a EXP-011 paso 0 se calcularon con el gestor
defectuoso**. Re-ejecución del paso 0 sobre las mismas 19 películas:

| sistema | tópicos antes→después | Δ escena F1 vs azar | Δ beat F1 vs azar |
|---|---|---|---|
| p80_q1 | 36→30 | +0.116→+0.107 | +0.020→+0.018 |
| p90_q2 | 233→204 | +0.123→**+0.139** | +0.003→+0.005 |
| p95_q2 | 170→143 | +0.117→+0.138 | +0.004→+0.006 |

La conclusión del paso 0 no cambia (escenas sí, beats en el azar); la
referencia pasa a escena Δ F1 +0.139. EXP-001–008 no se re-ejecutan; sus
cifras quedan marcadas como calculadas con el gestor anterior.

`results/exp011_hierarchy_baseline_fixed19.json`

---

## EXP-011 · Paso 1 — agregador adaptativo por continuidad multimodal
- **Fecha:** 2026-09-28
- **Corpus:** 23 películas val (las que tienen señales; extracción del resto
  en curso, job 53481)
- **Votantes** (sin fusión): visual SigLIP, transcript TF-IDF, diálogo bge-base
  (embeddings, test LOO `cross ≥ ρ·min(coh)`, se abstienen sin evidencia);
  SegLoop frozen (umbral frozen) y habla (|Δ fracción|, p80) como fronteras.
  Propuesta inicial: top 30 % de scores SegLoop. Fusión por mayoría estricta
  de activos, rondas hasta estabilizar. ρ=0.9 pre-registrado.
- **Scores SegLoop:** exportados sobre val por el ensemble frozen; val se usó
  para elegir pesos/umbral, no para entrenar. Índice reconstruido y verificado
  (102035 scores, labels idénticos).
- **Corrección durante el paso:** la coherencia in-sample se inflaba (cada shot
  pesa 1/|A| en su centroide) y los votantes decían "corte" en ~90 % de pares;
  se pasó a coherencia leave-one-out antes de medir. ρ no se tocó.

Δ = sistema − azar con el mismo nº de cortes (± error estándar, 23 películas):

| sistema | tópicos | Δ escena F1 | Δ escena Pk | Δ beat F1 | Δ beat Pk | scene_prec |
|---|---|---|---|---|---|---|
| mejor fijo (p95_q2 / p95_q1) | 152 / 6 | +0.135 | −0.124 | +0.041 | −0.028 | 0.39 / 0.58 |
| segloop_frozen | 118 | **+0.276** | −0.247 | +0.027 | −0.064 | 0.643 |
| adaptive ρ0.9 | 81 | +0.197 | −0.171 | +0.016 | **−0.088** | 0.606 |
| SegLoop top-K, K = cortes de adaptive ρ0.9 | 81 | **+0.276** | −0.217 | **+0.043** | −0.068 | **0.691** |
| SegLoop top-K, K = cortes de adaptive ρ0.8 | 36 | +0.214 | −0.140 | **+0.070** | −0.065 | 0.848 |
| adaptive sin SegLoop | 193 | +0.157 | −0.213 | −0.002 | −0.031 | 0.476 |

- **Resultado:**
  - Frente al gate pre-registrado (mejor percentil fijo de `manage()`), el
    adaptativo gana en escena (+0.197 vs +0.135) y en beat Pk (−0.088 vs
    −0.028), y pierde en beat F1.
  - Frente al control a igual nº de cortes, SegLoop solo gana en escena F1,
    beat F1 y scene_prec; el adaptativo solo gana en beat Pk (~1 SE).
  - Las ganancias sobre `manage()` vienen de incluir a SegLoop como votante.
- **⚠️ INVALIDADO:** "fusionar unidades por continuidad multimodal supera al
  mejor componente". A igual granularidad, los votantes de similitud toman
  peores decisiones de fusión que el ranking de confianza de SegLoop.
- **Hallazgo:** el ranking de confianza de SegLoop lleva señal de trama: sus
  36 cortes más fuertes dan beat F1 +0.070, el mejor sistema a nivel beat.
- **Siguiente (paso 1b):** invertir roles. SegLoop ordena la jerarquía; los
  votantes solo deciden dónde dejar de dividir (divisivo top-down).

`results/exp011_adaptive_partial20.json` · `topicagg/adaptive_aggregator.py` ·
`scripts/eval_adaptive.py` · `scripts/build_val_voters.py`

---

## EXP-011 · Paso 1b — divisivo: SegLoop ordena, los votantes deciden parar
- **Fecha:** 2026-09-28
- **Corpus:** las mismas 23 películas val
- **Configuración:** `divisive()`. Cada unidad se parte en su corte SegLoop
  interno más fuerte solo si una mayoría estricta de votantes activos ve
  discontinuidad en ventanas locales (≤32 shots por lado); si no, es hoja.
  ρ=0.9 y ventana 32 pre-registrados. Control: SegLoop top-K con el mismo nº
  de cortes por película.

| sistema | tópicos | Δ escena F1 | Δ beat F1 | Δ beat Pk | scene_prec |
|---|---|---|---|---|---|
| divisive ρ0.9 (pre-registrado) | 5 | +0.035 | +0.015 | −0.016 | 0.506 |
| SegLoop top-K igualado | 5 | +0.039 | +0.020 | −0.017 | 0.535 |
| divisive ρ1.0 | 109 | +0.238 | +0.037 | −0.070 | 0.518 |
| SegLoop top-K igualado | 109 | +0.270 | +0.020 | −0.054 | 0.640 |

- **Resultado:**
  - Con ρ=0.9 los votantes rechazan casi todos los cortes de raíz: la recursión
    se detiene en ~5 tópicos, al nivel del control.
  - Con ρ=1.0 gana al control en beat F1 (+0.017) y beat Pk (−0.016), ~1 SE
    en ambos, y pierde en escena y scene_prec. ρ=1.0 no estaba pre-registrado
    y no se adopta.
- **⚠️ INVALIDADO:** "los votantes de similitud, decidiendo solo dónde parar,
  añaden señal de trama sobre el orden de SegLoop".
- **Lectura de pasos 0–1b:** visual, diálogo, TF-IDF y habla no llevan
  información de trama más allá de SegLoop, se agreguen como se agreguen.
  Tiene que venir de un votante que entienda la historia → paso 2 (VJudge
  relacional en los cortes candidatos de SegLoop).

`results/exp011_step1b_partial.json`

---

## EXP-011 · Paso 2 — VJudge relacional en cortes candidatos (pre-registro)
- **Fecha:** 2026-09-28 (registrado antes de ver resultados; job 53482)
- **Corpus:** 23 películas val · top-100 cortes SegLoop por película (2300)
- **Configuración:** Qwen2.5-VL-7B frozen compara ANTES (keyframes de los shots
  c-6, c-1) y DESPUÉS (c, c+5) de cada corte: "¿sigue el mismo evento de trama
  (A) o la historia pasa a otro (B)?". p_new = softmax de los logits de A/B.
  Condiciones: `mm` (+ diálogo 45 s a cada lado) y `frames`.
- **Criterio primario:** AP pareada por película, candidato positivo = inicio de
  beat a ±60 s. Pasa si ΔAP(mm − SegLoop) > 0 por más de 2 SE.
  Calibración con jueces falsos: aleatorio −0.021 ± 0.013; oráculo +0.677.
- **Secundarios:**
  - AP(mm) > AP(frames).
  - veto_mm − veto_random en beat F1 a K=24 > 2 SE. Solo como apoyo: con un
    juez aleatorio da +0.025 ± 0.013 (1.9 SE), así que es demasiado ruidoso
    para decidir por sí solo.
- **Controles:**
  - Veto aleatorio con la misma tasa de veto. Un veto aleatorio ya mejora
    beat F1 sobre SegLoop top-K (+0.062 vs +0.071 en ese sorteo), porque saltar
    candidatos espacia los cortes.
  - Azar con el mismo K.
- **Invalidación:** si ΔAP(mm − SegLoop) ≤ 2 SE, el VJudge relacional no añade
  señal de trama sobre el ranking de SegLoop.

`scripts/vjudge_relational.py` · `scripts/eval_relational.py`

### Resultado EXP-011 paso 2 (job 53482, 23 películas)
AP sobre los 100 candidatos por película (positivo = inicio de beat a ±60 s):

| scorer | AP beat | AP escena |
|---|---|---|
| azar (tasa positiva) | 0.271 | 0.567 |
| SegLoop | 0.323 | **0.774** |
| VJudge mm | **0.349** | 0.657 |
| VJudge frames | 0.342 | 0.632 |

- **Primario:** ΔAP beat(mm − SegLoop) = **+0.027 ± 0.017** (1.55 SE); mm
  gana en 11 de 23 películas. **No alcanza el umbral de 2 SE.**
- **Secundarios:**
  - mm − frames = +0.007 ± 0.018: sin diferencia.
  - veto_mm − veto_random ≈ 0 en todos los K.
- **Defecto del diseño:** el juez responde "nueva trama" casi siempre (p
  mediana 0.82; p < 0.5 en solo 1 % de candidatos), así que el veto con umbral
  fijo 0.5 casi no actúa y la prueba del veto no informa. El umbral no se
  reajusta a posteriori.
- **Escena:** SegLoop es muy superior (−0.118 ± 0.023 para el VJudge), como se
  esperaba de un detector supervisado de escenas.
- **Patrón:** con top-K propio del VJudge, beat Pk mejora (−0.084 vs −0.056 a
  K=24) y beat F1 empeora; es el mismo desacuerdo Pk/F1 del paso 1.
- **Estado:** dirección positiva y no significativa. No se declara ni validado
  ni invalidado; se resuelve con replicación, no re-analizando estas 23.

`results/exp011_step2_relational.json`

### Pre-registro EXP-011 paso 2-R (replicación)
- **Películas:** las 35 películas val con beats que no están en el paso 2
  (`scripts/exp011_replication_films.txt`), nunca vistas por esta prueba.
- **Configuración:** idéntica al paso 2, solo condición `mm`.
- **Criterio:** ΔAP beat(mm − SegLoop) > 0 por más de 2 SE en las
  35 películas nuevas. Si pasa, se valida "el VJudge relacional añade
  señal de trama sobre SegLoop"; si no, se invalida. Las 23 del paso 2 no se
  suman para decidir.

### Pre-registro adicional para 2-R: veto relativo (antes de ver la replicación)
- **Corrección del defecto del veto:** el juez responde "nueva" en ~80 % de
  los casos, así que el umbral fijo 0.5 no veta nada. Nuevo voto relativo: el
  juez vota "nueva trama" si su p_new supera SU mediana en esa película.
  Selección = orden SegLoop saltando la mitad inferior del juez (sin fusión:
  dos votantes, cada uno con su propio ranking).
- **Observado post hoc en las 23 del paso 2** (diseñado después de verlas, así
  que no cuenta como prueba): beat F1 del veto relativo menos veto aleatorio
  de igual tasa = +0.029 / +0.021 / +0.025 a K = 12 / 24 / 36. Nulo con 200
  jueces aleatorios (`scripts/veto_null.py`): p empírico 0.045 / 0.075 / 0.020.
- **Criterio en las 35 de la replicación:** p empírico < 0.05 a K=24 contra
  200 jueces aleatorios. K=24 fijado de antemano como en el pre-registro del
  paso 2.

`results/exp011_step2_veto_null.json`

### Resultado EXP-011 paso 2-R (replicación, 35 películas val nuevas, job 53504)
| scorer | AP beat | AP escena |
|---|---|---|
| azar | 0.212 | 0.670 |
| SegLoop | **0.259** | **0.856** |
| VJudge mm | 0.257 | 0.751 |

- **Primario:** ΔAP beat(mm − SegLoop) = **−0.002 ± 0.012**; mm gana en 14 de
  35. **⚠️ INVALIDADO:** "el VJudge relacional con contexto local (±2 shots)
  ordena transiciones de trama mejor que SegLoop". El +0.027 del paso 2 no
  replica.
- **Veto relativo (pre-registrado):** +0.022 sobre veto aleatorio de igual
  tasa, p empírico 0.015 < 0.05 → **pasa**. Replica el +0.021 post hoc de las 23.
- **Contra SegLoop solo** (descriptivo, pareado): el veto relativo no mejora
  beats en ninguna K de ninguna de las dos muestras (p. ej. K24 +0.007 ±
  0.013 en las 35) y baja escena F1 entre −0.007 y −0.024 en todas.
- **Lectura:** los votos del juez no son aleatorios (dañan menos que un veto al
  azar), pero no añaden señal de trama sobre SegLoop. Con contexto local el
  VJudge no aporta al nivel beat. El siguiente paso tiene que ampliar el
  contexto que ve el juez, no cambiar cómo se lee su voto.

`results/exp011_step2R_replication.json` · `results/exp011_step2R_veto_null.json`

