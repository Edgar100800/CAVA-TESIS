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
| EXP-012 | "El VJudge juzgando cada corte contra la historia previa (ctx3) añade señal de trama; el contexto largo es lo que falta" | ΔAP vs SegLoop +0.002 / +0.006 (dev / rep), ctx3 ≈ ctx1; juez saturado (p_new mediana 0.97) |
| EXP-013 | "Qwen2.5-VL-7B frozen capitula el ledger en párrafos de sinopsis" | Salida degenerada (92 % de candidatos marcados, 334/522 truncadas); ΔAP −0.022 / −0.013. Fallo del instrumento: la hipótesis de capitular queda sin probar |
| EXP-013b | "Qwen2.5-VL-7B frozen con ~30 min de historia reconoce inicios de beat mejor que SegLoop" | ΔAP −0.016 ± 0.012 (dev) / +0.025 ± 0.020 (rep), signos opuestos; instrumento sin saturar |
| EXP-014 | "El razonador (14B) o los resúmenes entity-tracking desbloquean el nivel beat" | Ninguna celda supera a SegLoop; efectos 14b−7b −0.014 ± 0.011 y new−old −0.013 ± 0.013 en replicación |
| EXP-016 | "El quorum ≥2 de {visual, diálogo, resúmenes} enlaza hilos mejor que visual sola" | −0.017 ± 0.005 de precisión en 47 películas train nuevas; diálogo no replica como votante |
| EXP-017 / 017b | "El mapa de tópicos por consenso sin fusión agrupa hilos mejor (MCC, proxy cast) que la fusión y que v2.1" | components percola; average no supera a fused (+0.002 / −0.001); visual sola es mejor en MCC. G-coherencia sí se cumple y supera a fused en cada señal |
| G-enlace (juez modelo) | "Los enlaces no contiguos de CAVA son juzgados mismo hilo más que momentos lejanos al azar" | 83 % vs 63 %, Fisher p = 0.072 (umbral 0.05): no se cumple; infradimensionado (~60 por brazo) |
| G-enlace-2 (juez modelo, mezclado) | "Los enlaces no contiguos de CAVA son mismo hilo más que pares al azar" | 62 % vs 65 %, p = 0.72. El lote 1 (p = 0.07) estaba confundido por revisores distintos por brazo |

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

---

## EXP-012 · Story ledger: el VJudge juzga cada corte contra la historia previa (pre-registro)
- **Fecha:** 2026-09-28 (registrado antes de ejecutar)
- **Motivo:** EXP-011 paso 2-R. Con contexto local (±2 shots) el VJudge no
  añade señal de trama sobre SegLoop. Un beat dura ~10 min; el juez necesita
  ver minutos de historia, no segundos.
- **Corpus:**
  - desarrollo = las 23 películas val del paso 2 (`scripts/exp011_step2_films.txt`)
  - replicación = las 35 del paso 2-R (`scripts/exp011_replication_films.txt`)
  - Se ejecutan juntas; los criterios quedan fijados aquí antes de ver nada.
- **Configuración:**
  - Unidades = tramos entre los top-100 cortes SegLoop, los mismos candidatos
    del paso 2 (mediana de 8 shots por unidad).
  - Etapa 1: Qwen2.5-VL-7B frozen resume cada unidad en una frase desde 3
    keyframes + diálogo.
  - Etapa 2, solo texto: por corte, "historia hasta aquí" = resúmenes de las
    ctx unidades previas y "siguiente" = unidad posterior → A/B → p_new.
    ctx ∈ {1, 3}.
- **Criterios**, en desarrollo Y en replicación, cada uno por separado; AP beat
  (±60 s) sobre los mismos 100 candidatos, pareado por película:
  1. **Primario:** ΔAP(ledger ctx3 − SegLoop) > 2 SE.
  2. **Contexto largo:** ΔAP(ctx3 − ctx1) > 2 SE. Si no, la mejora no viene de
     ver más historia.
  3. ΔAP(ctx3 − relacional mm del paso 2) > 0.
  4. Veto relativo ctx3 (orden SegLoop saltando la mitad inferior del ledger)
     contra SegLoop solo en beat F1 a K=24 > 2 SE pareado. Es la prueba que
     falló en 2-R.
- **Invalidación:** si falla 1 en replicación, "el VJudge con historia larga
  añade señal de trama sobre SegLoop" queda invalidado; si falla 2, se
  invalida "el contexto largo es lo que falta".

`scripts/vjudge_ledger.py` · `scripts/vjudge_ledger.sbatch`

### Resultado EXP-012 (job 53506, 1 h 31 min, 58 películas)
| criterio (AP beat pareado) | desarrollo (23) | replicación (35) |
|---|---|---|
| 1. ledger ctx3 − SegLoop | +0.002 ± 0.010 | +0.006 ± 0.014 |
| 2. ctx3 − ctx1 | −0.002 ± 0.010 | +0.001 ± 0.012 |
| 3. ctx3 − relacional mm | −0.025 ± 0.017 | +0.008 ± 0.012 |
| 4. veto rel ctx3 − SegLoop (beat F1, K24) | +0.023 ± 0.014 | +0.010 ± 0.015 |
| escena: ctx3 − SegLoop | −0.117 | −0.127 |

- **⚠️ INVALIDADO:** los cuatro criterios fallan en ambos conjuntos. "El VJudge
  juzgando cada corte contra la historia previa añade señal de trama" y "el
  contexto largo es lo que falta" no se sostienen **en esta formulación**.
- **Diagnóstico:**
  1. Juez saturado: p_new mediana 0.97 (p10 0.89) y en la película mediana no
     juzga "misma trama" ningún corte. Su orden apenas se relaciona con SegLoop
     (Spearman +0.12) ni con el relacional (+0.19).
  2. Los resúmenes son de superficie ("un hombre de traje explica…"). En
     tt0118571 el primer beat dura 25 min y los resúmenes lo describen minuto
     a minuto como eventos distintos; dos resúmenes consecutivos siempre
     parecen "nuevo evento". Es el fallo de EXP-010, ahora en texto.
  3. La pregunta absoluta "¿mismo o nuevo?" entre tramos de ~1 min no
     corresponde a la granularidad de un beat de sinopsis.
- **Siguiente (EXP-013):** en vez de un juicio absoluto por corte, que el
  VJudge lea 30 resúmenes seguidos (~30 min) y marque dónde empezaría un
  párrafo de sinopsis: decisión relativa entre cortes, no saturable.

`results/exp012_ledger_step2.json` · `results/exp012_ledger_replication.json`

---

## EXP-013 · Capitulación del ledger (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de ejecutar)
- **Motivo:** EXP-012. El juicio absoluto por corte satura; la sinopsis GT se
  escribió leyendo la historia entera y agrupándola en párrafos. Aquí el
  VJudge hace eso: una decisión relativa sobre una ventana larga.
- **Corpus:** mismas 58 películas; desarrollo = 23 (paso 2), replicación = 35
  (paso 2-R). Se ejecutan juntas.
- **Configuración:**
  - Reutiliza los resúmenes de EXP-012.
  - Qwen2.5-VL-7B frozen, solo texto, greedy. Lee 30 resúmenes consecutivos
    (~30 min) y lista qué tramos empiezan un párrafo de sinopsis.
  - Ventanas de 30 con paso 10: 522 en total, cada corte cubierto por 1–3.
  - score(corte) = fracción de ventanas que lo cubren y lo marcan.
  - AP con empates rotos al azar (20 permutaciones), sin desempatar con SegLoop.
- **Criterios**, en desarrollo Y en replicación por separado:
  1. **Primario:** ΔAP beat(chapter − SegLoop) > 2 SE pareado.
  2. veto_chapter (orden SegLoop restringido a cortes marcados en ≥ 1 ventana)
     − SegLoop solo: beat F1 a K=24 > 2 SE pareado.
- **Calibración con marcas aleatorias (tasa 20 %), desarrollo:** ΔAP −0.019 ±
  0.016; veto −0.008 ± 0.019.
- **Invalidación:** si 1 falla en replicación, "el VJudge capitulando la
  historia larga añade señal de trama sobre SegLoop" queda invalidado.

`scripts/vjudge_chapter.py` · `scripts/eval_chapter.py`

### Resultado EXP-013 (job 53556, 58 películas)
| criterio | desarrollo (23) | replicación (35) |
|---|---|---|
| 1. ΔAP beat(chapter − SegLoop) | −0.022 ± 0.010 | −0.013 ± 0.012 |
| 2. veto_chapter − SegLoop (beat F1, K24) | +0.006 ± 0.008 | −0.012 ± 0.006 |

- **Resultado pre-registrado:** falla en ambos conjuntos.
- **⚠️ Fallo del instrumento, no prueba de la idea:**
  - Salida degenerada: el modelo enumera casi todos los números en orden
    ("2, 3, 4, …"). Mediana de 22 de 29 tramos marcados por ventana; 92 % de
    los candidatos marcados.
  - 334 de 522 salidas quedaron truncadas por max_new_tokens=80: las
    posiciones 26–30 se marcan 11–24 % contra 83–94 % antes.
  - Es la misma saturación de EXP-012 en forma de lista. Queda invalidado
    "Qwen2.5-VL-7B frozen, con este prompt, capitula el ledger"; la hipótesis
    de capitular la historia larga NO queda probada ni refutada.
- **Patrón EXP-010 → EXP-013:** el VJudge frozen describe bien (resúmenes con
  personajes y eventos) pero, preguntado por continuidad de trama, responde
  "distinto" casi siempre, sea el formato A/B, relativo o de lista.

`results/exp013_chapter_step2.json` · `results/exp013_chapter_replication.json`

---

## EXP-013b · Capitulación por ítem con logits (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de ejecutar)
- **Motivo:** EXP-013 falló por el instrumento (enumeración degenerada +
  truncado). Se corrige el instrumento sin cambiar la pregunta ni el modelo.
- **Configuración:**
  - Por cada corte candidato, la misma ventana larga de resúmenes EXP-012
    (hasta 15 antes y 14 después; mediana de 30 líneas).
  - Una sola pregunta: "¿el tramo k empieza un párrafo nuevo o continúa el del
    tramo k−1?" → p_start = softmax de los logits A/B.
  - Sin generación: no hay lista que enumerar ni truncar. La evaluación es por
    ranking dentro de la película.
- **Criterios**, en desarrollo (23) Y en replicación (35) por separado:
  1. **Primario:** ΔAP beat(p_start − SegLoop) > 2 SE pareado.
  2. veto (orden SegLoop restringido a p_start ≥ mediana del juez en la
     película) − SegLoop solo: beat F1 a K=24 > 2 SE pareado.
- **Calibración con juez aleatorio, desarrollo:** ΔAP −0.016 ± 0.011; veto
  +0.009 ± 0.016.
- **Invalidación:** si 1 falla en replicación, "el VJudge frozen, con la
  historia larga como contexto, reconoce inicios de beat mejor que SegLoop"
  queda invalidado para Qwen2.5-VL-7B.

`scripts/vjudge_chapter_logit.py` · `scripts/eval_chapter.py --logit`

### Resultado EXP-013b (job 53564, 58 películas)
- **El instrumento funciona:** p_start p10/p50/p90 = 0.59 / 0.68 / 0.73, sin
  saturar; ranking dentro de cada película.

| criterio | desarrollo (23) | replicación (35) |
|---|---|---|
| 1. ΔAP beat(p_start − SegLoop) | −0.016 ± 0.012 | +0.025 ± 0.020 |
| 2. veto mediana − SegLoop (beat F1, K24) | −0.014 ± 0.016 | +0.002 ± 0.015 |
| escena: p_start − SegLoop | −0.157 | −0.170 |

- **⚠️ INVALIDADO:** "Qwen2.5-VL-7B frozen, con ~30 min de historia como
  contexto, reconoce inicios de beat mejor que SegLoop". Signos opuestos entre
  conjuntos, ninguno a 2 SE.
- **Balance EXP-010 → EXP-013b** (seis formulaciones: descripción, relacional
  local, ledger A/B, lista, logits por ítem, y la variante con veto): ninguna
  añade señal de trama sobre el ranking de confianza de SegLoop en datos no
  vistos.
  - El VJudge sirve para describir (resúmenes con personajes y eventos) y
    sigue siendo peor que SegLoop en escenas (−0.10 a −0.17 AP).
  - Con el modelo y los resúmenes actuales, el nivel beat no se alcanza.
- **Abierto:** quedan dos causas posibles sin separar: el razonador (7B
  multimodal) o los resúmenes de superficie.

`results/exp013b_chapterlogit_step2.json` · `results/exp013b_chapterlogit_replication.json`

---

## EXP-014 · 2×2 resúmenes × razonador (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de ejecutar)
- **Motivo:** EXP-013b deja abiertas dos causas: el razonador (7B multimodal)
  o los resúmenes de superficie. El 2×2 las separa.
- **Factores** (mismo instrumento que EXP-013b: capitulación por ítem con
  logits, ventana 15+14, mismos 100 candidatos):
  - **Resúmenes:** `old` = EXP-012 (una frase libre) · `new` = entity-tracking.
    Qwen2.5-VL-7B escribe `CHARACTERS | PLACE | GOAL` recibiendo el resumen
    previo como contexto, para mantener nombres entre tramos.
  - **Razonador:** `7b` = Qwen2.5-VL-7B (rev cc59489) · `14b` =
    Qwen2.5-14B-Instruct (texto, rev cf98f3b, frozen, misma familia y
    tokenizer, el doble de parámetros).
  - Celda old×7b = EXP-013b (ya medida, sin cambios).
- **Corpus:** desarrollo 23 / replicación 35, como EXP-011–013b.
- **Criterios:**
  1. Por celda: ΔAP beat(celda − SegLoop) > 2 SE pareado, en desarrollo Y en
     replicación. Solo así una celda "añade señal de trama".
  2. Efectos principales en replicación, pareado por película con la media de
     los dos niveles del otro factor: razonador (14b − 7b) y resúmenes
     (new − old), cada uno > 2 SE.
- **Lectura prevista:**
  - Solo el razonador pasa: faltaba capacidad de razonamiento.
  - Solo los resúmenes: faltaba información de entidades.
  - Solo new×14b: hacen falta ambas.
  - Ninguna: con estos componentes frozen, el nivel beat no se alcanza sobre
    SegLoop.

`scripts/vjudge_ledger.py --summary-mode entity` · `scripts/vjudge_chapter_logit.py --model`

### Resultado EXP-014 (jobs 53612–53615, 58 películas)
ΔAP beat(celda − SegLoop), pareado:

| celda | desarrollo (23) | replicación (35) |
|---|---|---|
| old × 7b (EXP-013b) | −0.016 ± 0.012 | +0.025 ± 0.020 |
| new × 7b | −0.013 ± 0.016 | +0.016 ± 0.018 |
| old × 14b | −0.010 ± 0.014 | +0.014 ± 0.019 |
| new × 14b | −0.004 ± 0.020 | −0.003 ± 0.015 |
| efecto razonador (14b − 7b) | +0.007 ± 0.010 | −0.014 ± 0.011 |
| efecto resúmenes (new − old) | +0.004 ± 0.012 | −0.013 ± 0.013 |

- **Resultado pre-registrado: "ninguna".** Ninguna celda supera a SegLoop en
  ningún conjunto; ni el razonador ni los resúmenes tienen efecto. Con estos
  componentes frozen, el nivel beat no se alcanza sobre SegLoop.
- **⚠️ INVALIDADO:**
  - "Faltaba capacidad de razonamiento" (Qwen2.5-14B no mejora a 7B).
  - "Faltaba información de entidades" (los resúmenes entity-tracking no
    mejoran).
- **Instrumento:** 7b sin saturar (p50 0.59–0.68). 14b sobreconfiado: p50 0.98
  con resúmenes old y bimodal 0/1 con new. El AP, al ser por ranking, sigue
  siendo válido.
- **Diagnóstico del objetivo:**
  - Los candidatos no son el cuello de botella: el 90 % de los inicios de beat
    cae a ±60 s de un top-100 SegLoop.
  - Solo el 60 % de los inicios de beat cae a ±1 shot de un corte de escena:
    la alineación sinopsis→shot es aproximada.
  - Beats de 1.1 a 19.3 min (p10–p90), mediana 5.1.
  - Incluso SegLoop queda cerca del azar a nivel beat (AP 0.26 vs 0.21 en
    replicación).

`results/exp014_2x2.json` · `results/exp014_<celda>_<conjunto>.json`

---

## EXP-015 · Enlace de hilos no contiguos (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de calcular nada)
- **Motivo:** el nivel beat de fronteras queda como negativo documentado
  (EXP-010 → 014). Se pasa al núcleo sin probar de CAVA: agrupar segmentos NO
  contiguos del mismo hilo.
- **Unidades:** las mismas 101 por película (tramos entre los top-100 cortes
  SegLoop).
- **GT (solo evaluación, nunca señal):** `cast` de MovieNet.
  - Conjunto de personajes por unidad; par (i, j) con |i−j| ≥ 2 y ambos
    anotados.
  - Positivo = Jaccard ≥ 0.5; negativo = Jaccard 0; el resto se excluye.
  - 46 de 58 películas tienen cast. Desarrollo = las del paso 2 con cast;
    replicación = las del 2-R con cast.
- **Votantes** (cada uno por separado; similitud entre unidades):
  - `visual`: coseno de centroides SigLIP.
  - `dialogue`: coseno de centroides bge del diálogo.
  - `summary_old` / `summary_new`: coseno bge de los resúmenes de EXP-012 y
    entity-tracking de EXP-014.
  - `names`: Jaccard de los nombres que el VJudge escribió en `CHARACTERS`
    (tokens en mayúscula, sin artículos ni descripciones genéricas).
- **Baselines:** prior temporal (−|i−j|) y azar (tasa positiva).
- **Criterio primario:** en pares de largo alcance (|i−j| ≥ 10),
  ΔAP(votante − prior temporal) > 2 SE pareado por película, en desarrollo Y
  en replicación. Largo alcance = el caso "vuelve el hilo", donde la
  proximidad no explica el acierto.
- **Secundario:** enlace por consenso (≥ 2 votantes sobre su propia mediana en
  la película; sin fusión de scores). Precisión de enlace frente al mejor
  votante solo con el mismo nº de enlaces, en replicación.
- **Invalidación:** si ningún votante pasa en replicación, "las señales frozen
  actuales enlazan hilos no contiguos mejor que la proximidad" queda
  invalidado.

`scripts/eval_threads.py`

### Resultado EXP-015 (46 películas con cast: desarrollo 18, replicación 28)
AP en pares de largo alcance (|i−j| ≥ 10 unidades), ΔAP(votante − prior
temporal) pareado. AP medio de replicación: azar 0.526, prior temporal 0.552.

| votante | desarrollo | replicación | criterio |
|---|---|---|---|
| visual (SigLIP) | +0.111 ± 0.018 (z 6.0) | **+0.139 ± 0.020 (z 7.0)** | ✅ |
| dialogue (bge) | +0.085 ± 0.019 (z 4.6) | **+0.088 ± 0.016 (z 5.4)** | ✅ |
| summary_old (VJudge, bge) | +0.056 ± 0.017 (z 3.3) | **+0.045 ± 0.013 (z 3.3)** | ✅ |
| summary_new (entity) | +0.042 ± 0.016 | +0.011 ± 0.013 | ❌ |
| names (CHARACTERS) | +0.042 ± 0.019 | +0.001 ± 0.010 | ❌ |
| consenso ≥2 − mejor votante (precisión) | +0.003 ± 0.005 | −0.011 ± 0.005 | ❌ |

- **✅ VALIDADO (pre-registrado, replicado):** "las señales frozen enlazan
  unidades no contiguas del mismo hilo mejor que la proximidad". Pasan
  visual, diálogo y resúmenes VJudge (old). Es el primer resultado positivo
  replicado de la línea CAVA.
- **⚠️ INVALIDADO:**
  - Resúmenes entity-tracking y nombres como votantes de enlace (no replican).
  - Consenso ≥ 2 de 5 votantes: peor que el mejor votante solo en replicación.
    Los votantes débiles diluyen.
- **Lectura:**
  - A nivel de fronteras (EXP-011 → 014) ninguna señal superaba a SegLoop; a
    nivel de ENLACE sí hay señal multimodal real. La multimodalidad aporta en
    agrupar, no en cortar, lo que es coherente con el diseño de CAVA.
  - El VJudge aporta como votante de enlace (summary_old), no de corte.
- **Límite del GT:** "mismo hilo" = mismos personajes (cast Jaccard ≥ 0.5).
  Parte de la señal visual puede ser "mismos actores / mismo set", que es
  percepción legítima (el votante no ve IDs) pero no equivale a trama.

`results/exp015_threads_step2.json` · `results/exp015_threads_replication.json`

---

## EXP-016 · Enlace por quorum de votantes validados, muestra nueva (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de generar datos)
- **Motivo:**
  - EXP-015 valida visual, diálogo y summary_old como votantes de enlace.
  - El consenso ≥ 2 de 5 fue peor que el mejor votante solo.
  - El `link_quorum` de CAVA sobre los tres validados se eligió después de
    ver EXP-015, así que necesita una muestra nueva.
- **Corpus nuevo:** las 47 películas *train* de MovieNet-318 con señales y cast
  (`scripts/exp016_train_films.txt`), nunca usadas en EXP-011–015. SegLoop no
  interviene, así que sus scores in-sample en train no importan.
- **Unidades:** bloques fijos de 8 shots (la mediana de EXP-015), sin SegLoop
  ni GT; ~7400 unidades.
- **Votantes:**
  - visual (SigLIP), dialogue (bge del subtítulo por shot).
  - summary_old: Qwen2.5-VL-7B frozen, prompt de EXP-012, un resumen por
    unidad, bge.
- **GT y pares:** como EXP-015 (cast Jaccard ≥ 0.5 positivo, 0 negativo;
  |i−j| ≥ 10 unidades).
- **Criterios:**
  1. Replicación de EXP-015: cada votante − prior temporal > 2 SE pareado.
  2. **Primario:** quorum = enlazar si ≥ 2 de {visual, dialogue, summary_old}
     superan su mediana en la película. Precisión del quorum − precisión de
     visual solo (fijado de antemano como mejor votante) con el mismo nº de
     enlaces > 2 SE pareado.
- **Invalidación:** si 2 falla, "el quorum multimodal enlaza mejor que la
  mejor señal sola" queda invalidado; CAVA usaría un único votante de enlace.

`scripts/vjudge_ledger.py --fixed-units 8` · `scripts/build_dialogue.py` ·
`scripts/eval_threads.py --quorum-voters visual dialogue summary_old --best-single visual`

### Resultado EXP-016 (47 películas train, 7437 unidades fijas de 8 shots, job 53617)
AP en pares |i−j| ≥ 10: azar 0.675, prior temporal 0.706, visual 0.782,
summary_old 0.727, dialogue 0.704.

| criterio | resultado | |
|---|---|---|
| 1. visual − prior temporal | **+0.076 ± 0.010 (z 7.9)** | ✅ replica |
| 1. summary_old − prior temporal | **+0.021 ± 0.007 (z 2.8)** | ✅ replica |
| 1. dialogue − prior temporal | −0.003 ± 0.007 | ❌ no replica |
| 2. **quorum ≥2 de 3 − visual solo** (precisión, mismo nº de enlaces) | **−0.017 ± 0.005 (z −3.7)** | ❌ |

- **⚠️ INVALIDADO (primario):** "el quorum multimodal enlaza mejor que la
  mejor señal sola". El quorum es peor que visual sola en muestra nueva, igual
  que el consenso ≥2 de 5 en EXP-015.
- **⚠️ INVALIDADO:** diálogo como votante de enlace robusto. Pasa en EXP-015
  (unidades SegLoop, val) y no en EXP-016 (unidades fijas, train).
- **Robusto en 3 muestras** (EXP-015 desarrollo y replicación, EXP-016):
  - visual: z 6.0 / 7.0 / 7.9.
  - resúmenes VJudge (old): z 3.3 / 3.3 / 2.8. El VJudge sí aporta señal de
    enlace sobre la proximidad, menor que la visual.
- **Consecuencia para CAVA:** con votación por mediana, añadir votantes más
  débiles a visual empeora el enlace. Queda abierto si los resúmenes VJudge
  aportan información *complementaria* a visual (no se probó; la votación por
  mediana es una regla tosca). Probarlo requiere otra muestra nueva: val y
  train ya se usaron.

`results/exp016_quorum_train.json`

---

## EXP-017 · Mapa de tópicos con retornos: la arquitectura CAVA completa (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de ejecutar)
- **Motivo:**
  - `manage()` v2.1 solo generaba etiquetas contiguas por señal, así que el
    quorum de enlace no podía agrupar "el tema se retoma después" (el caso
    TPU de VERSIONS.md).
  - Implementado `return_percentile` (commit 8ea0e85): cada señal devuelve
    segmentos propios a tópicos propios anteriores con su propio percentil, y
    el quorum de ADR-0001 decide. Sin fusión.
- **Unidades:** shots (unidad nativa del gestor).
- **Señales:**
  - `visual` (SigLIP por shot) y `dialogue` (bge del subtítulo por shot).
  - `vjudge`: bge del resumen VJudge de la unidad que contiene el shot.
- **GT (solo evaluación):** conjunto cast por shot. Pares de shots anotados
  con |i−j| ≥ 80 (largo alcance ≈ ≥10 unidades): positivo Jaccard ≥ 0.5,
  negativo 0.
- **Métrica: MCC** de "mismo tópico predicho" frente a "mismos personajes".
  No se usa F1 porque la tasa positiva es 0.5–0.7 y un solo tópico global ya
  sacaría F1 ≈ 0.75; MCC le da 0.
- **Sistemas:**
  - `cava`: manage(visual, dialogue, vjudge; percentile 80,
    return_percentile 90, link_quorum 2).
  - `contiguous`: igual con return_percentile=None (v2.1).
  - `fused`: una sola señal = concatenación de las tres L2-normalizadas; es el
    modo de fallo de A2Summ-X. link_quorum 1 (con una señal, 2 no enlazaría).
  - `visual` / `dialogue` / `vjudge` solas (link_quorum 1, mismos
    percentiles). `dialogue` solo = sistema dominado por texto.
  - En desarrollo, además: `cava+segloop` (SegLoop como votante de fronteras).
- **Corpus:**
  - Desarrollo = películas val con cast (unidades SegLoop).
  - Confirmación = 47 películas train (EXP-016, unidades fijas de 8 shots).
  - Ambas se usaron para elegir votantes en EXP-015/016, así que ninguna es
    del todo nueva. Una confirmación limpia requiere el split test (pendiente
    de autorización).
- **Criterios**, en desarrollo Y confirmación:
  1. **Primario:** MCC(cava) − MCC(fused) > 2 SE y MCC(cava) −
     MCC(contiguous) > 2 SE, pareado por película.
  2. G-coherencia (VERSIONS.md): en `cava`, margen intra − inter tópico > 0
     en CADA señal. Ninguna señal queda aplastada.
- **Secundario (se reporta, no decide):** cava frente a la mejor señal sola.
  Sensibilidad return_percentile ∈ {80, 95}, sin elegir el mejor.

`scripts/eval_topic_map.py`

### Hallazgo durante EXP-017 (antes de ver sus resultados) y pre-registro EXP-017b
- **Diagnóstico en tt0061722** (sin mirar MCC):
  - Con retornos, cada señal forma tópicos razonables: visual 30, diálogo 37,
    vjudge 20.
  - La regla de enlace v2.1 (componentes conexas de pares con ≥ quorum votos)
    es enlace simple: cadenas i~j (señales 1+2) y j~k (señales 2+3) unen i con
    k aunque ninguna mayoría los agrupe. Resultado: un tópico gigante con el
    94 % de los shots.
  - Con etiquetas contiguas el defecto no se veía porque las cadenas quedaban
    dentro de tramos.
- **Corrección** (`link_mode="average"`, commit siguiente): consenso por enlace
  promedio sobre la matriz de votos. Dos grupos se unen solo si, en promedio
  sobre todos sus pares, ≥ link_quorum señales los agrupan. Sigue siendo
  conteo de votos por señal (ADR-0001). Test que reproduce la percolación
  (`test_average_link_mode_does_not_chain`). En tt0061722 / tt0102138 da 46 /
  121 tópicos, el mayor con 15–16 % de los shots, y 20 / 63 tópicos con
  retornos.
- **EXP-017 se ejecuta igualmente tal como se registró** (modo components) y se
  reporta.
- **Pre-registro EXP-017b** (antes de ver MCC con average): mismos corpus,
  pares, métrica y criterios que EXP-017.
  - `cava_avg`: link_mode="average", percentile 80, return_percentile 90,
    link_quorum 2.
  - Primario: MCC(cava_avg) − MCC(fused) > 2 SE y MCC(cava_avg) −
    MCC(contiguous v2.1) > 2 SE, en desarrollo Y confirmación.
  - G-coherencia: margen > 0 en cada señal para cava_avg.
  - `fused` sigue siendo una sola señal (una señal no tiene quorum que enlazar;
    su partición es su propio etiquetado).

### Resultado EXP-017 (registrado: link_mode components)
MCC en pares de largo alcance (|i−j| ≥ 80 shots), media por película:

| sistema | desarrollo (46) MCC / tópicos | confirmación (47) MCC / tópicos |
|---|---|---|
| cava (components) | −0.004 / 9 | +0.002 / 5 |
| contiguous (v2.1) | +0.007 / 95 | +0.004 / 65 |
| fused (A2Summ-X) | +0.009 / 36 | +0.011 / 38 |
| visual sola | +0.019 / 54 | **+0.025** / 48 |
| vjudge sola | **+0.022** / 32 | +0.010 / 31 |
| dialogue sola | +0.001 / 78 | +0.003 / 71 |

- **⚠️ INVALIDADO:** con enlace por componentes, cava − fused = −0.013 ± 0.005
  (desarrollo) y −0.009 ± 0.006 (confirmación). El tópico gigante (tasa de
  enlace 0.98, 5–9 tópicos) confirma el diagnóstico de percolación.
- **Magnitud:** todos los MCC son pequeños (≤ 0.025). La pertenencia a una
  partición dura es exigente: un sistema que enlaza el 15–26 % de los pares
  lejanos no puede tener MCC alto aunque sus enlaces sean precisos. Se
  comparan sistemas entre sí, no contra 1.
- **G-coherencia:** con components, cava pierde margen positivo en algunas
  películas (vjudge 84 %, diálogo 90 % de películas > 0); fused y contiguous
  lo mantienen en todas.

`results/exp017_topicmap_dev.json` · `results/exp017_topicmap_conf.json`

### Resultado EXP-017b (link_mode average)
MCC en pares de largo alcance; tasa de enlace = fracción de pares lejanos que
el sistema pone en el mismo tópico.

| sistema | desarrollo (46) MCC / tópicos / enlace | confirmación (47) MCC / tópicos / enlace |
|---|---|---|
| cava_avg | +0.011 / 78 / 0.046 | +0.010 / 82 / 0.048 |
| cava_avg + SegLoop | +0.014 / 81 / 0.035 | — |
| fused | +0.009 / 36 / 0.208 | +0.011 / 38 / 0.188 |
| contiguous | +0.007 / 95 / 0.002 | +0.004 / 65 / 0.003 |
| visual sola | +0.019 / 54 / 0.260 | **+0.025** / 48 / 0.263 |
| vjudge sola | **+0.022** / 32 / 0.147 | +0.010 / 31 / 0.138 |

| criterio | desarrollo | confirmación |
|---|---|---|
| cava_avg − fused | +0.002 ± 0.004 (z 0.6) | −0.001 ± 0.003 (z −0.5) |
| cava_avg − contiguous | +0.005 ± 0.004 (z 1.2) | +0.006 ± 0.003 (z 2.2) |
| cava_avg − cava (components) | +0.015 ± 0.005 (z 3.2) | +0.008 ± 0.004 (z 1.8) |
| cava_avg − visual | −0.007 ± 0.005 | −0.015 ± 0.005 (z −3.1) |

- **Primario: NO se cumple.** cava_avg no supera a fused en ningún conjunto;
  sobre contiguous solo alcanza 2 SE en confirmación. El enlace promedio
  arregla la percolación (78–82 tópicos frente a 5–9), pero en MCC contra el
  proxy cast la mejor partición es la de visual sola.
- **G-coherencia: SE CUMPLE en ambos conjuntos.** Margen > 0 en las tres
  señales en el 100 % de películas. Además, en ambos conjuntos el margen de
  cada señal es mayor en cava_avg que en fused (descriptivo, no
  pre-registrado):

  | señal | cava_avg (dev / conf) | fused (dev / conf) |
  |---|---|---|
  | visual | 0.049 / 0.045 | 0.033 / 0.032 |
  | diálogo | 0.028 / 0.028 | 0.009 / 0.009 |
  | vjudge | 0.163 / 0.110 | 0.106 / 0.086 |

  La fusión aplana la estructura de cada señal (el diálogo queda en 0.009);
  el consenso sin fusión la conserva. Es la lección de A2Summ-X medida.
- **Límite del GT:** "mismos personajes" favorece a la señal visual por
  construcción (mismas caras en pantalla); un hilo sostenido por diálogo no
  cuenta como positivo. El juez neutral es la revisión humana G-enlace
  (preparada: `data/review_g_enlace/`, 30 casos).

`results/exp017b_topicmap_dev.json` · `results/exp017b_topicmap_conf.json`

---

## EXP-018 · Abstención de señales sin evidencia; confirmación en el split test (pre-registro)
- **Fecha:** 2026-09-29 (registrado antes de ejecutar en cualquier dato)
- **Motivo (diagnóstico post EXP-017b, 10 películas de desarrollo):**
  - El 33 % de los shots no tiene diálogo. Con retornos, cada tramo silencioso
    recibe un tópico de diálogo propio y el diálogo vota en contra de
    enlazarlo: el silencio cuenta como desacuerdo.
  - Quitar el diálogo subió la precisión de enlace de 0.304 a 0.333 (azar
    0.283).
  - Todos los sistemas quedan cerca del azar en precisión contra el proxy
    cast (0.29–0.33 frente a 0.283): el proxy es débil y sesgado a lo visual.
- **Corrección** (`abstain=True`, commit previo): un shot sin evidencia en una
  señal no recibe voto de ella. Un par se enlaza solo con ≥ link_quorum
  votantes activos y mayoría media de activos coincidentes. Es la regla
  "señales activas" de ADR-0001.
- **Corpus de confirmación: split test de MovieNet-318** (autorizado; nunca
  usado en CAVA).
  - Películas con story y cast; unidades fijas de 8 shots; resúmenes VJudge
    con el prompt de EXP-012.
  - SegLoop NO interviene en test: el test_lock de SegLoop queda intacto.
- **Sistemas:**
  - `cava_abst`: visual + diálogo + vjudge; percentile 80, return_percentile
    90, link_mode average, abstain, link_quorum 2.
  - Mismos baselines que EXP-017b: fused, contiguous, visual / diálogo /
    vjudge solas, cava_avg.
- **Criterios (solo en test, una ejecución):**
  1. **Primario:** MCC(cava_abst) − MCC(fused) > 2 SE y MCC(cava_abst) −
     MCC(contiguous) > 2 SE, pareado por película.
  2. Precisión de enlace de cava_abst − tasa base > 2 SE: la partición dice
     algo más allá del azar.
  3. G-coherencia: margen > 0 en cada señal en cada película.
- **Descriptivo, no decide:** la misma evaluación en desarrollo (val) y en la
  confirmación anterior (train), marcada como post hoc. El diagnóstico se hizo
  sobre val.
- **G-enlace:** decide la revisión humana (`data/review_g_enlace/`), no el
  proxy cast.

`scripts/eval_topic_map.py --average --abstain`

### Resultado EXP-018 — confirmación pre-registrada en el split test (job 53817, 47 películas)
| criterio (test) | resultado | |
|---|---|---|
| 1. MCC(cava_abst) − MCC(fused) | **+0.0060 ± 0.0024 (z 2.46)** | ✅ |
| 1. MCC(cava_abst) − MCC(contiguous) | **+0.0068 ± 0.0027 (z 2.48)** | ✅ |
| 2. precisión de enlace − tasa base | **+0.026 ± 0.005 (z 5.6)** (fused +0.005, z 1.95; visual +0.016, z 4.3) | ✅ |
| 3. G-coherencia: margen > 0 por señal | visual 0.053 · diálogo 0.018 · vjudge 0.121, en el 100 % de películas | ✅ |

- **✅ VALIDADO (pre-registrado, split test nunca usado):** "el mapa de tópicos
  CAVA — cada señal con sus propios tópicos que retornan, consenso por enlace
  promedio entre señales activas, sin fusión — agrupa hilos mejor que la fusión
  de señales (modo de fallo de A2Summ-X) y que el gestor v2.1 contiguo". Sus
  enlaces son los más precisos de todos los sistemas (margen sobre el azar ~5×
  el de fused) y conserva la estructura de cada señal (G-coherencia).
- **Salvedades:**
  1. Magnitudes pequeñas en términos absolutos: MCC 0.011 frente a 0.005 de
     fused. La pertenencia a partición dura contra el proxy cast es exigente
     y el proxy es débil.
  2. visual sola obtiene más MCC que cava_abst en test (−0.008 ± 0.003) y en
     train. El proxy "mismos personajes" favorece por construcción a la señal
     de caras; visual enlaza el 25 % de los pares con menos precisión sobre el
     azar (+0.016 frente a +0.026).
  3. Heterogeneidad: en train (post hoc) cava_abst empata con fused (+0.000 ±
     0.003); en val (post hoc) +0.006 ± 0.004. El criterio se evaluó y se
     cumple en test; train muestra que la ventaja sobre fused no es uniforme
     entre muestras.
  4. G-enlace (revisión humana, 30 casos) sigue pendiente y es el juez neutral
     del proxy.
- **Post hoc** (el diagnóstico se hizo sobre val, no decide):

  | conjunto | cava_abst − fused | cava_abst − contiguous | precisión − base |
  |---|---|---|---|
  | val | +0.006 ± 0.004 | +0.009 ± 0.005 | +0.035 ± 0.009 |
  | train | +0.000 ± 0.003 | +0.007 ± 0.003 | +0.029 ± 0.007 |

`results/exp018_test.json` · `results/exp018_posthoc_dev.json` · `results/exp018_posthoc_conf.json`

---

## G-enlace · Revisión ciega de enlaces no contiguos (pre-registro del análisis)
- **Fecha:** 2026-09-30 (registrado antes de ver cualquier veredicto)
- **Juez:** revisión automática por modelo (Claude, 6 revisores independientes,
  10 casos cada uno), a pedido del usuario ("no human input required"). **No
  es la revisión humana** que G-enlace pre-registró en VERSIONS.md; se
  documenta como juez sustituto.
- **Casos:**
  - 30 enlaces del sistema: pares de apariciones del MISMO tópico CAVA
    separadas por ≥ 80 shots; mapas con la configuración validada de EXP-018.
  - 30 controles: misma película, mismo desfase temporal (mediana 40.2 min en
    ambos), tramos de tópicos DISTINTOS.
- **Ciego:** los revisores ven solo keyframes (3 por lado), resúmenes y tiempos.
  Instrucciones idénticas para casos y controles; ningún revisor sabe qué
  conjunto evalúa. Sin etiqueta de tópico, provenance ni cast.
- **Veredicto por caso:** yes / no / unsure ("mismo hilo = mismos personajes
  principales en la misma situación, relación, conflicto o trama").
- **Criterio:**
  1. Tasa de "yes" en enlaces del sistema > tasa en controles, Fisher exacto
     unilateral p < 0.05; "unsure" cuenta como no-yes.
  2. Se reporta también la precisión absoluta (yes / (yes + no)).
- **Invalidación:** si la tasa de "yes" del sistema no supera a los controles,
  los enlaces no contiguos de CAVA no son mejores que emparejar momentos
  lejanos de la misma película al azar.

### Resultado G-enlace (revisión ciega por modelo, 30 enlaces + 30 controles)
| | enlaces CAVA | controles (mismo desfase) |
|---|---|---|
| mismo hilo (yes) | **25 (83 %)** | 19 (63 %) |
| distinto (no) | 1 | 6 |
| dudoso (unsure) | 4 | 5 |
| precisión entre decididos | **96 %** | 76 % |

- **Criterio pre-registrado:** Fisher exacto unilateral sobre yes / no-yes,
  **p = 0.072 → NO se cumple** (umbral 0.05). La dirección es la esperada: los
  enlaces CAVA se juzgan "mismo hilo" 20 puntos más que momentos lejanos al
  azar de la misma película.
- **Descriptivo (no pre-registrado, no decide):** excluyendo los "unsure",
  25/26 frente a 19/25, p = 0.044.
- **Potencia:** con las tasas observadas hacen falta ~60 casos por brazo para
  80 % de potencia; con 30 la prueba estaba infradimensionada.
- **Límites del juez:**
  1. Es un modelo, no un humano. Revisores independientes y ciegos al
     conjunto, pero no a la película: 59 de 60 juicios usaron conocimiento
     del film.
  2. Las películas con una sola trama dominante hacen que muchos controles
     parezcan "mismo hilo" (tasa base 63 %). El juez distingue poco y el
     margen posible es estrecho.
  3. Hubo más "yes" de alta confianza en controles (10) que en enlaces (5):
     muchos controles caen en arcos muy reconocibles (clímax, persecución).
- **Estado:** G-enlace sin cumplir con este juez; señal positiva no
  concluyente. Siguiente paso pre-registrable: ~60 + 60 casos NUEVOS con el
  mismo protocolo, sin reutilizar estos 60 (evita el testing secuencial
  sobre la misma muestra).

`results/g_enlace_model_review.json` · `data/review_g_enlace/verdicts_*.json`

### Pre-registro G-enlace-2 (lote nuevo, antes de muestrear)
- **Protocolo idéntico** al lote 1: mismo prompt, revisores ciegos al
  conjunto, veredicto yes / no / unsure, controles de la misma película con
  desfase emparejado y tópicos distintos.
- **n = 60 enlaces + 60 controles NUEVOS.** Se excluyen todos los tópicos y
  pares del lote 1; semillas distintas (sistema 41, controles 43).
- **Criterio:** Fisher exacto unilateral, yes frente a no-yes ("unsure"
  cuenta como no-yes), p < 0.05, **solo sobre el lote 2**. El lote 1 no se
  suma: la decisión no depende del resultado ya visto.
- **Revisores:** 6 instancias independientes, 20 casos cada una; enlaces y
  controles mezclados al azar dentro de cada revisor. Nadie sabe qué caso es
  enlace y cuál control.

### Resultado G-enlace-2 (lote nuevo, 60 + 60 mezclados a ciegas)
| | enlaces CAVA | controles |
|---|---|---|
| mismo hilo (yes) | 37 (62 %) | 39 (65 %) |
| distinto (no) | 12 | 12 |
| dudoso | 11 | 9 |
| precisión entre decididos | 76 % | 76 % |

- **Criterio pre-registrado:** Fisher unilateral **p = 0.72 → NO se cumple.**
  Los enlaces no contiguos de CAVA no se distinguen de momentos lejanos al
  azar de la misma película a nivel "mismo hilo" con este juez.
- **⚠️ INVALIDADO (juez modelo):** "los enlaces no contiguos de CAVA son
  juzgados mismo hilo más que pares al azar con igual desfase".
- **Relectura del lote 1:** en el lote 1 enlaces y controles los juzgaron
  revisores DISTINTOS. La diferencia 83 % vs 63 % puede deberse a la
  severidad de cada revisor y no al sistema. El lote 2 mezcla ambos en cada
  revisor y elimina ese confundido; es el diseño válido y da diferencia nula.
- **Lectura conjunta con EXP-018:**
  - En el proxy "mismos personajes" (cast), el mapa CAVA supera a la fusión
    y a v2.1, con los enlaces más precisos (z 5.6).
  - En el juicio "misma trama" (con conocimiento del film), no supera al
    azar.
  - Los enlaces de CAVA siguen continuidad de personajes / escena, que es lo
    que ven las señales (caras, diálogo, descripción). No siguen
    *argumento*: el 63–65 % de pares al azar ya cuenta como "mismo hilo"
    porque las películas tienen pocas tramas.
  - Es coherente con EXP-010 → 014: ninguna señal frozen alcanzó el nivel
    trama.
- **Estado de los gates v2:** G-versión ✅ (58/58) · G-coherencia ✅ (dev,
  conf, test) · G-enlace ❌ con juez modelo a nivel trama (la revisión humana
  pre-registrada no se hizo).

`results/g_enlace_model_review_batch2.json` · `data/review_g_enlace/batch2_*`

---

## EXP-019 · Certificación de la categorización de tópicos contra el contenido real (pre-registro)
- **Fecha:** 2026-09-30 (registrado antes de construir el GT completo y de medir)
- **Objetivo:** el producto es video largo → tópicos categorizados → clips →
  reconstrucciones (versiones por tópico, índice completo con rangos,
  resúmenes). La trama era una capa de validación intermedia. Aquí se
  certifica que cada tópico está bien categorizado: su etiqueta dice quién
  está y de qué trata, contrastado con lo que MovieNet sabe de punta a punta.
- **GT de contenido por shot** (`scripts/build_content_gt.py`, solo validación):
  - quién aparece = cast por shot → personaje (meta);
  - quién habla y qué dice = guion (HABLANTE + línea) alineado a subtítulos
    por contención idf y camino monótono, con varios cues por línea.
  - Calidad observada en un muestreo de 12 pares en 2 películas: ~10/12
    correctos. Los errores son cues cortos asignados a una línea vecina y
    cues con dos hablantes atribuidos a uno. Es GT ruidoso; el ruido es igual
    para la etiqueta propia y la barajada, así que no sesga la comparación.
- **Tópicos:** mapas validados en EXP-018 (abstain, nivel default); tópicos
  de duración ≥ 30 s con ≥ 1 personaje en el GT.
  - GT de personajes del tópico = personajes presentes (en pantalla o
    hablando) en ≥ 2 shots del tópico.
- **Etiqueta:** la etiqueta VJudge actual del tópico (resumen de su unidad
  dominante). Personajes nombrados = palabras en mayúscula de la etiqueta que
  coinciden con un alias del cast de la película.
- **Métricas por película:**
  1. **Precisión de personajes:** fracción de personajes nombrados que están
     en el GT del tópico (solo etiquetas que nombran ≥ 1). Control: la misma
     medida con la etiqueta de OTRO tópico de la película (media sobre todos
     los demás tópicos).
  2. **Recuperación de contenido:** coseno bge entre la etiqueta y las líneas
     del guion del tópico. MRR del propio tópico entre todos los de la
     película; control = MRR del azar (H_N / N).
  - Se reporta también la tasa de nombrado (fracción de etiquetas que nombran
    un personaje conocido).
- **Criterios** (desarrollo = val 58; confirmación = test 47, mapas sin
  SegLoop porque test no lo permite):
  1. precisión(propia) − precisión(barajada) > 2 SE pareado por película.
  2. MRR − MRR_azar > 2 SE pareado por película.
  - Ambos en desarrollo Y confirmación.
- **Invalidación:** si fallan, las etiquetas actuales no certifican de qué
  trata el tópico y la categorización necesita una etiqueta de nivel tópico
  (siguiente paso: etiqueta construida desde todos los tramos del tópico).

### Resultado EXP-019
GT de contenido: 105 películas. Cobertura de alineación guion↔subtítulos:
mediana 44 % de cues, con cola baja (algunas películas sin subtítulos o con
guion que difiere del montaje). Los tópicos sin líneas alineadas salen de la
prueba de contenido.

| criterio | desarrollo (val, 56) | confirmación (test, 47) |
|---|---|---|
| 1. precisión de personajes propia − barajada | **+0.187 ± 0.019 (z 9.7)** · 0.57 vs 0.37 | **+0.156 ± 0.021 (z 7.5)** · 0.64 vs 0.48 |
| 2. MRR − azar | **+0.227 ± 0.015 (z 15.3)** · 0.36 vs 0.14 | **+0.256 ± 0.015 (z 17.4)** · 0.38 vs 0.12 |
| top-1 (~39 tópicos por película; azar ≈ 2.6 %) | 24 % | 26 % |
| tasa de nombrado | 28 % | 22 % |

- **✅ VALIDADO (pre-registrado, desarrollo y test):** la etiqueta de cada
  tópico CAVA certifica de qué trata frente al contenido real. Cuando nombra
  personajes, acierta muy por encima de etiquetas de otros tópicos, y
  describe lo que se dice en sus rangos lo bastante bien como para encontrar
  su propio tópico entre ~39 (MRR ×3 sobre el azar).
- **Límites:**
  1. Solo el 22–28 % de las etiquetas nombra un personaje; el resto usa
     descripciones genéricas ("a man in a suit"). La categorización por
     personajes queda incompleta.
  2. La etiqueta (resumen VJudge) vio el diálogo de su unidad, así que la
     prueba de contenido es parcialmente circular con los subtítulos. Valida
     que la etiqueta representa lo que se dice en el tópico, no comprensión
     visual independiente.
  3. La etiqueta sale de UNA unidad (la dominante). Un tópico con retornos
     tiene más contenido del que su etiqueta resume (top-1 24–26 %).
- **Siguiente:** etiqueta de nivel tópico construida desde todos sus tramos,
  con personajes explícitos, y contexto por clip (quién aparece, quién habla,
  qué dice) en el mapa.

`results/exp019_categ_dev.json` · `results/exp019_categ_test.json` ·
`scripts/build_content_gt.py` · `scripts/eval_categorization.py`

---

## EXP-019b · Etiqueta de nivel tópico desde todos sus tramos (pre-registro)
- **Fecha:** 2026-09-30 (registrado antes de generar etiquetas)
- **Motivo:** en EXP-019 solo el 22–28 % de las etiquetas nombra personajes,
  y la etiqueta sale de una sola unidad del tópico.
- **Configuración:**
  - Qwen2.5-14B-Instruct frozen (texto, rev cf98f3b), greedy.
  - Entrada: los tramos del tópico (hasta 8, los más largos, en orden
    temporal), cada uno con lo que vio el VJudge y el diálogo en sus shots.
    Es el `context` del mapa: solo señales propias de CAVA, sin GT.
  - Salida: "CHARACTERS: … | TOPIC: …".
  - Tópicos del nivel default con duración ≥ 30 s.
- **Mismas películas, mapas, GT y métricas que EXP-019** (desarrollo = val,
  confirmación = test).
- **Criterios**, en desarrollo Y confirmación, pareados por película:
  1. tasa de nombrado(topic) − tasa de nombrado(unidad) > 2 SE;
  2. precisión(topic, propia) − precisión(topic, barajada) > 2 SE (la etiqueta
     sigue certificando);
  3. MRR(topic) − MRR(unidad) no menor que −2 SE (no se pierde contenido).
- **Nota:** el diálogo entra al modelo, así que los nombres oídos pueden
  aparecer en la etiqueta. Es legítimo en producción (ASR / subtítulos) y la
  precisión contra cast + hablantes sigue siendo la prueba de que nombra a los
  personajes correctos.

`scripts/vjudge_topic_labels.py` · `scripts/eval_categorization.py --labels-dir`
- **Enmienda al pre-registro de EXP-019b (antes de generar ninguna etiqueta):**
  - Algunos subtítulos son SDH, con etiquetas de hablante ("RATCHED: …") y
    sonidos ("[INMATE COUGHS]").
  - Se eliminan del diálogo que lee el etiquetador, porque un ASR de
    producción no los tendría y darían nombres gratis.
  - Criterios sin cambios. Job 53914 aún en espera: lee el script corregido.

### Sensibilidad EXP-019: subtítulos SDH
- Las etiquetas de unidad de EXP-019 se generaron con el diálogo crudo, y
  algunos subtítulos son SDH (con etiquetas de hablante "NOMBRE:").
- Solo 2 de 58 películas val y 5 de 47 test tienen etiquetas en > 5 % de los
  cues (`scripts/sdh_films.txt`).
- Sin esas 7 películas:

  | | desarrollo | confirmación |
  |---|---|---|
  | precisión propia − barajada | +0.189 ± 0.020 (z 9.4) | +0.170 ± 0.021 (z 8.1) |
  | MRR − azar | +0.232 ± 0.015 (z 15.7) | +0.263 ± 0.015 (z 17.2) |

- **EXP-019 se sostiene sin los SDH**; la validación no depende de esa fuga.

`results/exp019_categ_dev_nosdh.json` · `results/exp019_categ_test_nosdh.json`

### Resultado EXP-019b (job 53914, 4645 etiquetas de tópico en 105 películas)
Comparación pareada con las etiquetas de unidad sobre los mismos mapas:

| criterio | desarrollo (val) | confirmación (test) |
|---|---|---|
| 1. tasa de nombrado tópico − unidad | **0.28 → 0.54, +0.259 ± 0.020 (z 13.2)** ✅ | **0.22 → 0.49, +0.263 ± 0.020 (z 12.9)** ✅ |
| 2. precisión de la etiqueta de tópico, propia − barajada | **+0.176 ± 0.013 (z 13.5)** ✅ | **+0.141 ± 0.016 (z 8.6)** ✅ |
| 3. MRR tópico − unidad (no menor que −2 SE) | +0.025 ± 0.009 (z 2.7) ✅ | −0.020 ± 0.010 (z −1.96) ✅ por poco |
| (desc.) precisión propia tópico − unidad | −0.076 ± 0.034 (z −2.3) | −0.001 ± 0.027 |

- **✅ VALIDADO (pre-registrado, desarrollo y test):** la etiqueta de nivel
  tópico duplica la fracción de tópicos categorizados por personaje (≈ 1 de
  cada 2) y nombra a los personajes correctos muy por encima del azar, sin
  perder la representación del contenido.
- **Salvedades:**
  - Al nombrar el doble, la precisión baja algo en desarrollo (0.57 → 0.50),
    no en test.
  - En test el MRR queda en el límite del criterio (z −1.96).
  - Algunas etiquetas sin nombres caen en descripciones genéricas ("Two boys
    on a sidewalk…", "Varying dialogues unrelated to a central theme"): son
    tópicos que el propio etiquetador reconoce como poco cohesivos.
- Los mapas reciben el campo `topic_label` (etiqueta de nivel tópico); `label`
  se conserva (etiqueta de unidad).

`results/exp019b_{unit,topic}_{dev,test}.json` · `data/topic_labels/`

