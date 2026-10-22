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
| EXP-019c | "Re-etiquetar con un registro de personajes por video sube el nombrado sin perder contenido" | Nombrado +5 pts ✅ y precisión ✅, pero MRR −0.026 en test (z −3.2) ❌ |
| EXP-019e (método completo) | "Nombres por enlaces + registro + identidades por apariencia categorizan más sin perder precisión ni contenido" | Nombrado 0.48→0.65 ✅, identidades 0.95 vs 0.84 ✅, pero precisión −0.052 (z −3.3) ❌ y MRR −0.061 (z −10.8) ❌ |
| EXP-019g | "Emparejar descripción → registro con umbral absoluto y margen nombra más sin perder precisión" | +1.7 pts, pero precisión −0.008 (z −2.8) en train2 |
| EXP-019f | "Filtrar identidades genéricas las hace más consistentes" | 0.961 vs 0.969 (p = 0.92); cuesta 14 pts de cobertura |
| EXP-020b | "El mapa CAVA con retornos agrupa tópicos de reuniones mejor que fused y que lo contiguo" | vs contiguous −0.155 / −0.156 (z −2.9 / −2.7): CAVA sobresegmenta (19 frente a 7 tópicos del GT) |
| EXP-021c c3 | "El perfil meeting supera al perfil film en reuniones" | +0.036 ± 0.035 (z 1.0) en reuniones nuevas |
| EXP-022b | "Ward supera al enlace promedio en identidades de voz" | +0.021 ± 0.016 (z 1.3) |

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

---

## EXP-019c · Registro de personajes por video + re-etiquetado (pre-registro)
- **Fecha:** 2026-10-01 (registrado antes de generar)
- **Motivo:** en 019b la etiqueta solo puede nombrar a quien se nombra en el
  diálogo de los propios tramos del tópico. Los tópicos con poco o ningún
  diálogo ("sin contexto") quedan en descripciones genéricas aunque el
  personaje se nombre en otra parte del video.
- **Configuración** (solo salidas de CAVA, sin GT):
  1. Registro por video: Qwen2.5-14B-Instruct frozen lee TODAS las etiquetas
     de tópico de 019b y devuelve la lista de personajes del video, "Nombre —
     descripción breve (rol, apariencia)", solo con nombres que aparecen en
     esas etiquetas.
  2. Re-etiquetado: mismo prompt de 019b más el registro. El modelo puede
     identificar a un personaje descrito con un nombre del registro solo si
     la descripción encaja; si no, mantiene la descripción.
- **Mismos mapas, GT y métricas que EXP-019/019b** (val y test).
- **Criterios** (pareados por película, desarrollo Y confirmación):
  1. tasa de nombrado(019c) − tasa(019b) > 2 SE;
  2. precisión(019c, propia) − precisión(019c, barajada) > 2 SE;
  3. precisión propia(019c) − precisión propia(019b) no menor que −2 SE
     (guarda contra nombres inventados o mal asignados);
  4. MRR(019c) − MRR(019b) no menor que −2 SE.
- **Se reporta aparte:** tasa de nombrado y precisión en tópicos "sin
  contexto", es decir, sin ningún alias del cast en su propio diálogo
  (diálogo limpio de SDH).

---

## EXP-019d · Propagación de nombres por los enlaces de CAVA (pre-registro)
- **Fecha:** 2026-10-01 (registrado antes de calcular)
- **Idea (usuario):** cuando un personaje o un texto se repite en el video,
  SegLoop + VJudge relacionan esos tramos como el mismo contenido. La
  categoría (el nombre) conocida en un tramo puede aplicarse al otro. EXP-015,
  EXP-018 y G-enlace muestran que los enlaces de CAVA siguen la continuidad de
  personajes y situaciones, que es justo lo que hace falta para propagar
  identidad.
- **Mecanismo** (solo señales y salidas de CAVA; GT solo para evaluar):
  - Tópicos del nivel default con ≥ 30 s; base = etiquetas de 019b.
  - Nombres de un tópico = palabras en mayúscula del campo CHARACTERS de su
    etiqueta (sin artículos ni descripciones genéricas). Donantes = tópicos
    con ≥ 1 nombre.
  - Receptores = tópicos cuya etiqueta no nombra a nadie.
  - Enlace receptor–donante: centroide visual (SigLIP de sus shots) y
    centroide vjudge (bge de sus resúmenes). Cada señal vota con su propio
    percentil sobre los pares de tópicos de la película (visual ≥ p90,
    vjudge ≥ p75); hacen falta los dos votos (quorum 2, sin fusión).
  - Si hay donantes enlazados, el receptor hereda los nombres del de mayor
    similitud visual: "CHARACTERS: <nombres heredados> | TOPIC: <su tópico>".
- **Métricas:** las de EXP-019 (val y test), comparadas con 019b.
- **Criterios** (pareados por película, desarrollo Y confirmación):
  1. tasa de nombrado(019d) − tasa(019b) > 2 SE;
  2. precisión(019d, propia) − precisión(019d, barajada) > 2 SE;
  3. precisión propia(019d) − precisión propia(019b) no menor que −2 SE.
- **Se reporta aparte:** tópicos sin contexto (tasa de nombrado y precisión)
  y la precisión de los nombres heredados por sí solos.

### Resultado EXP-019d
Receptores (tópicos sin nombres): 1690; heredan nombres por enlace de dos
señales: 674 (40 %).

| criterio / medida | desarrollo (val) | confirmación (test) |
|---|---|---|
| 1. tasa de nombrado 019d − 019b | **0.54 → 0.61, +0.068 ± 0.011 (z 6.4)** ✅ | **0.49 → 0.55, +0.060 ± 0.011 (z 5.5)** ✅ |
| 2. precisión 019d propia − barajada | +0.163 ± 0.012 (z 14.0) ✅ | +0.122 ± 0.015 (z 8.4) ✅ |
| 3. precisión propia 019d − 019b (≥ −2 SE) | +0.017 ± 0.008 (z 2.2) ✅ | +0.001 ± 0.014 ✅ |
| sin contexto: tasa de nombrado | 0.24 → 0.33 | 0.22 → 0.28 |
| sin contexto: precisión | 0.20 → 0.27 | 0.33 → 0.37 |
| precisión de los nombres heredados solos | 0.54 (216 tópicos) | 0.57 (163 tópicos) |
| (desc.) MRR 019d − 019b | −0.003 ± 0.003 | −0.010 ± 0.002 (z −4.1) |

- **✅ VALIDADO (pre-registrado, desarrollo y test):** propagar nombres por los
  enlaces de CAVA (visual + vjudge, cada uno con su percentil, quorum 2, sin
  fusión) categoriza más tópicos por personaje sin perder precisión. Los
  nombres heredados aciertan como los oídos directamente (0.54–0.57 frente a
  0.50–0.60). La mejora se concentra en los tópicos sin contexto.
- **Coste (no pre-registrado):** el MRR baja levemente en test (−0.010): al
  heredar, la etiqueta reemplaza su texto de personajes y pierde algo de
  coincidencia con el diálogo propio.
- Combinable con EXP-019c (registro); se evaluará cuando termine el job 53926.

`results/exp019d_prop_{dev,test}.json` · `scripts/propagate_names.py` ·
`data/topic_labels_prop/*.propagation.json` (receptor → donante, similitudes)

### Resultado EXP-019c (job 53926, registro en 105 películas)
| criterio | desarrollo (val) | confirmación (test) |
|---|---|---|
| 1. tasa de nombrado 019c − 019b | 0.54 → 0.59, +0.048 ± 0.013 (z 3.9) ✅ | 0.49 → 0.54, +0.056 ± 0.016 (z 3.5) ✅ |
| 2. precisión propia − barajada | +0.168 ± 0.011 (z 15.6) ✅ | +0.123 ± 0.013 (z 9.3) ✅ |
| 3. precisión propia 019c − 019b (≥ −2 SE) | +0.029 ± 0.015 ✅ | +0.024 ± 0.015 ✅ |
| 4. MRR 019c − 019b (≥ −2 SE) | −0.007 ± 0.006 ✅ | **−0.026 ± 0.008 (z −3.2) ❌** |
| sin contexto: nombrado / precisión | 0.24 → 0.33 / 0.20 → 0.34 | 0.22 → 0.27 / 0.33 → 0.38 |

- **⚠️ NO VALIDADO:** falla el criterio 4 en test. Re-etiquetar con el
  registro aleja la etiqueta de lo que se dice en el tópico.
- **Lo que sí muestra:** el registro nombra más y con mejor precisión,
  sobre todo sin contexto (desarrollo 0.20 → 0.34).
- **Frente a 019d** (validado): nombrado similar (0.59 / 0.54 frente a
  0.61 / 0.55), pero 019d no toca el texto del tópico y conserva el MRR mejor.
  **019d queda como método por defecto.**

`results/exp019c_reg_{dev,test}.json` · `data/topic_labels_reg/*.registry.txt`

---

## EXP-019e · Categorización de personajes completa: nombres + identidades por apariencia (pre-registro)
- **Fecha:** 2026-10-01 (registrado antes de construir datos o etiquetas)
- **Motivo:**
  - 019d (enlaces) nombra sin tocar el texto del tópico.
  - 019c (registro) aporta precisión en tópicos sin contexto, pero al
    re-escribir la etiqueta pierde contenido.
  - Propuesta del usuario: cuando no hay nombre, categorizar al personaje
    por apariencia con una identidad estable en todo el video, y casarla con
    un nombre del registro si la descripción coincide.
- **Método** (solo salidas de CAVA; GT solo para evaluar), por video:
  1. Texto de la etiqueta propia (019b) intacto.
  2. Nombres por enlaces: regla de 019d en modo AÑADIR.
  3. Descripción → nombre: cada frase descriptiva del campo CHARACTERS
     recibe el nombre de la entrada del registro (019c, solo el registro)
     cuya descripción sea más similar (bge), si esa similitud ≥ p95 de las
     similitudes frase × entrada del video.
  4. Identidades por apariencia: las frases que siguen sin nombre se agrupan
     entre tópicos (enlace promedio). Un par entra al mismo grupo solo si dos
     señales coinciden (sin fusión): texto (bge de las frases) ≥ p90 Y visual
     (centroides SigLIP de sus tópicos) ≥ p75, percentiles del video. Los
     grupos que abarcan ≥ 2 tópicos son identidades "P1, P2, …".
  - Etiqueta final: "CHARACTERS: <nombres> ; <identidades P#: descripción> |
    TOPIC: <texto propio>".
- **Corpus de confirmación:** 47 películas train con cast y guion, nunca usadas
  en EXP-019*. Se les construyen mapas (unidades fijas de 8 shots, sin
  SegLoop), GT de contenido, etiquetas 019b y registro con el mismo código.
  Val y test se reportan solo como descriptivo (ya vistos).
- **Criterios (en train):**
  1. tasa de nombrado(019e) − tasa(019b) > 2 SE;
  2. precisión(019e) propia − barajada > 2 SE;
  3. precisión propia(019e) − (019b) ≥ −2 SE;
  4. MRR(019e) − MRR(019b) ≥ −2 SE;
  5. consistencia de identidades: entre pares de tópicos que comparten una
     identidad P#, la tasa de pares que comparten ≥ 1 personaje del GT supera
     a la de pares de tópicos al azar de la misma película (Fisher
     unilateral, p < 0.05, agrupado sobre películas).
- **Se reporta:** cobertura de categorías (fracción de tópicos con ≥ 1
  personaje categorizado, nombre o P#), sin contexto aparte.
- **Notas de implementación de EXP-019e (antes de ver resultados en train):**
  - Corregidos dos errores de código vistos en una prueba sobre una película
    val: (a) los nombres se manejaban como palabras sueltas, así que
    "Indiana Jones" se partía y se volvía a añadir a etiquetas que ya lo
    tenían; (b) duplicados. Ahora son frases, y solo se añade un nombre si
    aporta una palabra nueva a la etiqueta.
  - **Debilidad conocida de la regla pre-registrada (sin cambios):** p95
    dentro del video siempre deja pasar el 5 % superior de pares frase ×
    entrada, aunque sean débiles (p. ej. "man running up a hill" →
    "Sheriff"). Los roles no coinciden con alias del cast y no inflan la
    evaluación, pero son ruido en el producto. Se reportará la tasa de
    asignaciones de registro que caen en roles.

### Resultado EXP-019e — confirmación pre-registrada en 47 películas train (job 53930)
| criterio | resultado | |
|---|---|---|
| 1. tasa de nombrado 019e − 019b | **0.48 → 0.65, +0.175 ± 0.018 (z 9.6)** | ✅ |
| 2. precisión propia − barajada | +0.129 ± 0.011 (z 11.7) | ✅ |
| 3. precisión propia 019e − 019b (≥ −2 SE) | **−0.052 ± 0.016 (z −3.3)** | ❌ |
| 4. MRR 019e − 019b (≥ −2 SE) | **−0.061 ± 0.006 (z −10.8)** | ❌ |
| 5. consistencia de identidades P# | **0.95 vs 0.84 al azar, 1196 pares, Fisher p ≈ 0** | ✅ |
| cobertura (≥ 1 personaje categorizado) | 0.48 → **0.81** (+0.326 ± 0.023) | |
| sin contexto: nombrado / precisión | 0.20 → **0.46** / 0.27 → 0.30 | |

- **⚠️ NO VALIDADO como método completo:** fallan los criterios 3 y 4.
- **✅ Validado el componente de identidades por apariencia:** los tópicos que
  comparten una P# comparten un personaje real el 95 % de las veces, frente al
  84 % de pares al azar. La cobertura de categorías sube a 4 de cada 5
  tópicos.
- **Causas a diagnosticar (post hoc, siguiente):**
  - el ruido conocido de la regla p95 de descripción → nombre (precisión);
  - añadir NAMES / IDS al texto de la etiqueta diluye su embedding, y las
    P# compartidas hacen parecidas las etiquetas de tópicos distintos
    (MRR).

`results/exp019e_{cat,base019b,ids}_train.json`

### Ablación post hoc de EXP-019e (train; diagnóstico, no cambia el veredicto)
| componente (frente a 019b) | Δ nombrado | Δ precisión | Δ MRR |
|---|---|---|---|
| solo enlaces (regla 019d) | +0.072 (z 7.2) | +0.004 (z 0.4) | −0.018 (z −7.4) |
| solo registro (descripción → nombre) | +0.133 (z 7.8) | **−0.070 (z −4.1)** | −0.036 (z −8.6) |
| enlaces + registro | +0.173 (z 9.5) | −0.049 (z −3.0) | −0.046 (z −10.3) |
| solo identidades P# | +0.008 | −0.007 | −0.037 (z −7.6) |
| enlaces + identidades: cobertura | **0.48 → 0.80** · consistencia de P# 0.95 vs 0.84 (p ≈ 0) · 11 P# por película | | |

- **Causa de la caída de precisión:** el emparejamiento descripción →
  registro (ruido de la regla p95). Los enlaces mantienen la precisión y
  replican 019d en películas nuevas.
- **Causa de la caída de MRR:** añadir cualquier texto a la etiqueta (enlaces,
  registro o P#) diluye el texto que se compara con el diálogo, y las P#
  compartidas igualan etiquetas de tópicos distintos.
- **Decisión de diseño:** los personajes van como campos ESTRUCTURADOS del
  tópico (`characters`: nombres propios + heredados por enlace con
  provenance, e identidades P#), no dentro del texto de la etiqueta. Así el
  texto queda como 019b (MRR intacto por construcción).
  - El emparejamiento por registro queda fuera hasta tener una regla con
    umbral absoluto y margen (pendiente de pre-registro).
  - Evidencia de cada componente: enlaces = 019d pre-registrado (val, test)
    + replicación en train; identidades = criterio 5 de 019e pre-registrado
    en train. La combinación es post hoc y se declara así.

---

## Conjunto de confirmación nuevo: train2 (91 películas)
Películas train de MovieNet-318 con cast, guion, story y subtítulos, nunca
usadas en ningún experimento (`scripts/exp019_train2_films.txt`). Datos
generados con el mismo código que val/test/train por el job 53932: señales,
resúmenes VJudge de 8 shots, mapas con contexto, GT de contenido, etiquetas
019b y registro. Las 47 train de EXP-016/019e pasan a ser desarrollo.

## EXP-019f · Filtro de identidades genéricas (pre-registro)
- **Fecha:** 2026-10-01, antes de que existan los datos de train2.
- **Regla fijada:** una frase descriptiva solo puede formar identidad P# si
  tiene ≥ 2 palabras distintivas (fuera de una lista fija de palabras
  genéricas: man, woman, other, two, group, object…). Ejemplos: "man in
  yellow shirt" pasa (yellow, shirt); "other man", "woman" y "man with
  object" no.
- **Criterios en train2:**
  1. Las identidades del filtro superan a pares de tópicos al azar de la misma
     película (Fisher unilateral, p < 0.05).
  2. Sobre las identidades SIN filtro: las que cumplen la regla tienen mayor
     tasa de pares que comparten personaje del GT que las que no la cumplen
     (conjuntos disjuntos; Fisher unilateral, p < 0.05).
- **Se reporta:** coste en cobertura (fracción de tópicos con ≥ 1 categoría
  de personaje, con y sin filtro).

## EXP-019g · Emparejamiento descripción → registro con umbral absoluto y margen (pre-registro)
- **Fecha:** 2026-10-01, antes de que existan los datos de train2.
- **Calibración en desarrollo** (47 train ya usadas), frente a solo enlaces;
  regla de selección fijada antes del grid: máximo nombrado con Δprecisión ≥ 0.

  | abs | margen | Δ nombrado | Δ precisión |
  |---|---|---|---|
  | ≥ 0.70 (12 combinaciones) | — | ≤ +0.007 | ≈ 0 |
  | 0.50 | 0.02 | +0.127 | −0.050 |
  | 0.50 | 0.05 | +0.071 | −0.014 |
  | **0.50** | **0.10** | **+0.029** | **+0.006** |
  | 0.55 | 0.10 | +0.027 | +0.006 |

  Elegido: **abs 0.50, margen 0.10**. Ganancia modesta: las ganancias
  mayores cuestan precisión.
- **Regla:** una frase descriptiva recibe la entrada del registro más similar
  si sim ≥ 0.50 y sim − segunda mejor ≥ 0.10. Se añade a los nombres
  heredados por enlace (019d).
- **Criterios en train2**, frente a "solo enlaces" en las mismas películas,
  pareados:
  1. tasa de nombrado > 2 SE;
  2. precisión propia ≥ −2 SE;
  3. precisión propia − barajada > 2 SE.

### Resultados en train2 (91 películas nuevas; jobs 53932 + 53942)
**EXP-019g** (registro con abs 0.50 y margen 0.10, frente a solo enlaces):

| criterio | resultado | |
|---|---|---|
| 1. tasa de nombrado | 0.583 → 0.600, +0.017 ± 0.004 (z 4.9) | ✅ |
| 2. precisión propia (≥ −2 SE) | 0.562 → 0.554, **−0.008 ± 0.003 (z −2.8)** | ❌ |
| 3. propia − barajada | +0.154 ± 0.010 (z 15.2) | ✅ |

- **⚠️ NO VALIDADO:** el emparejamiento por registro aún cuesta precisión,
  aunque sea poca, y aporta poco (+1.7 pts). Queda fuera del diseño.

**EXP-019f** (filtro de identidades genéricas, ≥ 2 palabras distintivas):

| criterio | resultado | |
|---|---|---|
| 1. identidades filtradas vs pares al azar | 0.975 vs 0.863 (953 pares), p ≈ 0 | ✅ |
| 2. identidades que pasan vs que no pasan | **0.961 vs 0.969, p = 0.92** | ❌ |
| coste | cobertura 0.81 → 0.67; identidades por película 11.4 → 3.9 | |

- **⚠️ NO VALIDADO:** las identidades "vagas" son igual de consistentes contra
  el GT que las específicas, porque los personajes principales aparecen en
  casi todos los tópicos y el GT no distingue. El filtro solo quita
  cobertura y queda fuera.
- Límite de la métrica: la consistencia de P# frente al GT está cerca del
  techo (0.86 al azar) y no puede premiar la especificidad de una
  descripción. Juzgar si una identidad es útil requiere otra medida.

**Confirmación del diseño final en train2** (tercer conjunto nuevo, mismo
código):
- nombres propios + heredados por enlace: tasa de nombrado 0.506 (019b) →
  **0.583**, precisión 0.562;
- identidades sin filtro consistentes: 0.97 vs 0.86 al azar;
- cobertura de categoría de personaje: **0.51 → 0.81**.
- **Diseño final validado:** etiqueta de tópico (019b) + campos
  estructurados `characters` = nombres propios + heredados por enlaces
  (019d) + identidades P# sin filtro (019e c5).

`results/exp019g_t2_*.json` · `results/exp019f_t2_*.json`

### Análisis de especificidad de las identidades P# (descriptivo, post hoc)
- **Pregunta:** ¿una P# corresponde a un personaje concreto, o solo recoge
  a los protagonistas que están en todas partes?
- **Medida:** lift = P(personaje en los tópicos de la P#) / P(personaje en
  todos los tópicos de la película), con el personaje de mayor lift. Base de
  comparación: grupos de tópicos al azar del mismo tamaño (la elección del
  mejor personaje infla el lift).

| conjunto | lift mediano de P# | lift mediano al azar | P(P# > azar) |
|---|---|---|---|
| val | 4.75 | 4.17 | 0.55 |
| train2 | 3.91 | 3.50 | 0.63 |

- Específicas frente a vagas: lift parecido en los cuatro conjuntos (3.6–5.5).
- **Corrección importante:** las identidades P# son **solo débilmente
  específicas**. Superan al azar por poco (0.55–0.63, donde 0.5 es azar).
  Su 97 % frente a 86 % de consistencia (019e c5) es real, pero sale sobre
  todo de que los protagonistas aparecen en casi todos los tópicos.
  - Las P# NO deben presentarse como identificación fiable de personajes,
    sino como agrupación por apariencia de baja especificidad.
  - Los nombres heredados por enlace sí están validados en precisión.
- **Implicación:** hace falta una señal de identidad más fuerte. La voz
  (identidad del hablante) es la candidata natural, pero MovieNet no tiene
  audio.

---

## EXP-020 · AMI: señal de voz (espectrograma + tono) e identidad del hablante; CAVA fuera de películas (pre-registro)
- **Fecha:** 2026-10-01 (registrado antes de calcular cualquier señal)
- **Motivo:**
  - Las identidades P# son poco específicas y MovieNet no tiene audio.
  - Propuesta del usuario: usar la voz (espectrograma: altos y bajos)
    como señal de identidad.
  - AMI (CC BY 4.0) da audio + video de reuniones reales con GT de quién
    habla y tópicos humanos que se repiten. Sirve también para validar el
    mapa de tópicos de CAVA en otro dominio.
- **Datos:** 40 reuniones de escenario (ES/IS/TS) con tópicos anotados;
  audio Mix-Headset y video Corner. GT `scripts/ami_gt.py`: turnos por
  hablante y tópicos de primer nivel (tipo de la ontología o descripción).
  Mediana 30 min y 7 tópicos por reunión; 17 de 40 con tópicos que retornan.
  - Desarrollo = `data/ami/dev_20.txt`, confirmación = `data/ami/conf_20.txt`
    (partición aleatoria, semilla 7).
- **Unidades:** ventanas fijas de 10 s.
- **Señales:**
  - `voice`: log-mel de 64 bandas (media y desviación) + tono f0
    (autocorrelación: mediana, rango intercuartil, fracción sonora) +
    energía.
  - `visual`: SigLIP del fotograma central.
  - `transcript`: ASR faster-whisper large-v3 → bge.
  - `vjudge`: Qwen2.5-VL-7B frozen, resumen por unidad desde 3 fotogramas +
    transcript ASR.
  - Todo el texto viene del ASR, no de la transcripción manual.
- **EXP-020a (identidad por voz):** unidades con hablante dominante (≥ 60 %
  del habla de la unidad). Pares a ≥ 6 unidades (≥ 1 min) de distancia.
  AUC de similitud mismo hablante vs distinto, por reunión.
  1. AUC(voice) − AUC(visual) > 2 SE pareado por reunión;
  2. AUC(voice) − 0.5 > 2 SE.
- **EXP-020b (mapa de tópicos en AMI):** pares de unidades a ≥ 18 unidades
  (≥ 3 min); positivo = misma etiqueta de tópico GT. Sistemas como en
  EXP-018: cava_abst (con y sin `voice`), fused, contiguous, señales solas.
  1. MCC(cava_abst con voz) − MCC(fused) > 2 SE;
  2. MCC(cava_abst con voz) − MCC(contiguous) > 2 SE;
  3. G-coherencia: margen > 0 por señal.
  - Se reporta el efecto de añadir la voz (con − sin).
- Ambos en desarrollo Y confirmación.
- **Enmienda a EXP-020 (2026-10-02, sin resultados todavía):**
  - El job 54016 falló por datos. Solo las reuniones ES tienen cámara
    "Corner"; IS usa "C" y TS "Overview1". Algunos 404 del espejo eran
    transitorios.
  - Se usa la cámara de sala de cada sitio (equivalente: vista general de la
    sala) y se reintentan las descargas. `ami_signals.py` omite reuniones sin
    archivos en vez de fallar, y se descartó la salida parcial de ES2007d.
  - Reuniones y criterios sin cambios.
- **Enmienda 2 a EXP-020 (sin resultados):** las reuniones TS3008–TS3011 no
  tienen Overview1. Se usa Overview2 (Overview3 en TS3008d, la única vista
  general disponible). Las 40 reuniones están completas (audio + cámara de
  sala). Una segunda pasada de señales completa las 7 que la primera omitió;
  la evaluación corre después, sobre las 40.

### Resultado EXP-020 (AMI, 40 reuniones; jobs 54152 + 54155 + 54156)
**EXP-020a, identidad del hablante por voz:**

| AUC mismo vs distinto hablante | desarrollo (20) | confirmación (20) |
|---|---|---|
| voice (log-mel + tono) | **0.720** | **0.731** |
| visual (cámara de sala) | 0.562 | 0.569 |
| transcript (ASR, bge) / vjudge | 0.567 / 0.550 | 0.564 / 0.555 |
| 1. voice − visual | **+0.157 ± 0.027 (z 5.8)** ✅ | **+0.162 ± 0.023 (z 7.0)** ✅ |
| 2. voice − 0.5 | +0.220 ± 0.017 ✅ | +0.231 ± 0.019 ✅ |

- **✅ VALIDADO (pre-registrado, desarrollo y confirmación):** la voz
  (espectrograma + altos y bajos del tono, sin modelos) reconoce al mismo
  hablante a lo largo de la reunión. Ninguna otra señal lo hace (visual,
  ASR y VJudge ≈ 0.55–0.57).

**EXP-020b, mapa de tópicos CAVA en reuniones:**

| criterio | desarrollo | confirmación |
|---|---|---|
| 1. cava_voice − fused | +0.060 ± 0.038 (z 1.6) ❌ | +0.060 ± 0.040 (z 1.5) ❌ |
| 2. cava_voice − contiguous | **−0.155 ± 0.053 (z −2.9)** ❌ | **−0.156 ± 0.058 (z −2.7)** ❌ |
| 3. G-coherencia (margen > 0, todas las señales) | 100 % ✅ | 100 % ✅ |
| (desc.) aporte de la voz: con − sin | +0.036 ± 0.030 | +0.056 ± 0.029 (z 1.9) |

- **⚠️ NO VALIDADO:** en reuniones el mapa CAVA con retornos pierde frente a
  la segmentación contigua v2.1 (MCC 0.16–0.19 frente a 0.31–0.34).
- **Diagnóstico (descriptivo):** granularidad.

  | por reunión (mediana) | tópicos |
  |---|---|
  | GT | 7 (≈ 2.1 min cada uno); solo el 14 % de las instancias retorna |
  | CAVA | 18–20 |
  | contiguous | 5 |

  Los percentiles (corte 80, retorno 90) se fijaron en películas (~1350
  shots, retornos frecuentes). En reuniones (~180 unidades de 10 s, tópicos
  largos, pocos retornos) CAVA sobresegmenta y el MCC castiga los pares del
  mismo tópico que quedan separados.
- **Lectura:**
  - La agregación por retornos no es universal: en contenido de tópicos
    largos y contiguos, lo contiguo gana.
  - La granularidad tiene que adaptarse al contenido. Es el pendiente
    desde el ticket 005; no se ajusta aquí a posteriori.
  - La voz aporta como votante (+0.04 a +0.06), sin significancia.

`results/exp020_ami_{dev,conf}.json` · `topicagg/voice.py` · `scripts/eval_ami.py`

---

## EXP-022 · Identidades por voz (pre-registro)
- **Fecha:** 2026-10-03 (registrado antes de calcular)
- **Motivo:**
  - Las identidades P# por apariencia son poco específicas (0.55–0.63
    frente a grupos al azar).
  - EXP-020a valida la voz como señal de identidad del hablante.
- **Método fijo (sin GT):**
  - Por reunión, unidades de 10 s con voz (vector no nulo).
  - Clustering aglomerativo de enlace promedio sobre distancia coseno de los
    vectores de voz.
  - Número de identidades K ∈ {2, …, 8}, elegido por silueta máxima.
  - Mismo procedimiento con visual (SigLIP) como comparación: apariencia
    frente a voz.
- **GT:** hablante dominante de la unidad (≥ 60 % del habla, > 3 s).
- **Métricas por reunión** (unidades con hablante dominante):
  - ARI entre identidades y hablantes reales;
  - especificidad: lift del hablante principal de cada identidad frente a
    grupos de unidades al azar del mismo tamaño.
- **Criterios en las 40 reuniones NUEVAS** (`data/ami/meetings_fresh40.txt`):
  1. ARI(voice) − ARI(visual) > 2 SE pareado;
  2. ARI(voice) > 0 por más de 2 SE;
  3. especificidad: fracción de identidades de voz cuyo lift supera al de un
     grupo al azar del mismo tamaño, > 0.5 (binomial unilateral, p < 0.05).
- Descriptivo en las 40 ya usadas.

## EXP-021 · Granularidad adaptada al contenido (en desarrollo)
- Exploración en datos ya usados (40 reuniones AMI y 20 películas val): grid
  percentil de corte × percentil de retorno, más tres criterios internos sin
  GT (coherencia, coherencia penalizada por fragmentación, silueta). Se
  pre-registrará el criterio elegido antes de evaluar en las reuniones nuevas
  y en train2 (MCC de mapas nunca medido allí).

### EXP-021 · Resultado de la exploración (desarrollo) y pre-registro de confirmación
Desarrollo: 40 reuniones AMI ya usadas y 15 películas val. MCC medio:

| selección | AMI | películas |
|---|---|---|
| config por defecto p80/r90 | 0.171 | **0.023** |
| mejor config fija | **0.299** (p95/r90, ≈ 3.9 min por tópico) | 0.023 (p80/r90, ≈ 1.4 min) |
| oráculo por ítem | 0.481 | 0.054 |
| criterio interno: coherencia | 0.168 (≈ 20 tópicos) | 0.020 |
| criterio interno: silueta | 0.193 (≈ 3 tópicos) | 0.017 |

- **⚠️ NO VALIDADO (desarrollo):** ningún criterio interno sin GT elige bien
  la granularidad. La coherencia prefiere lo fino; la silueta, lo muy grueso.
- **No hay una granularidad universal:** ni en unidades ni en minutos (AMI
  ~3.9 min por tópico frente a películas ~1.4 min).
- **Decisión de diseño:** la granularidad es un **perfil de contenido
  explícito** (coherente con "versiones por consumidor"), no algo que se
  infiere:
  - perfil "film" = p80/r90 (validado en EXP-018);
  - perfil "meeting/talk" = p95/r90.

**Pre-registro EXP-021c** (confirmación en las 40 reuniones NUEVAS, antes de
calcular sus señales):
- cava_voice con el perfil meeting (p95/r90, average, abstain, quorum 2,
  señales voice + visual + transcript + vjudge).
- Criterios:
  1. no inferior a contiguous: MCC(cava_meeting) − MCC(contiguous) > −2 SE;
  2. MCC(cava_meeting) − MCC(fused, mismo perfil) > 2 SE;
  3. MCC(cava_meeting) − MCC(cava_voice p80/r90) > 2 SE (el perfil mejora
     al de películas).
- EXP-022 (identidades por voz) se confirma en las mismas reuniones.

### EXP-022b/c · Variantes de agrupación de voz (pre-registro, antes de las señales de las reuniones nuevas)
- **Desarrollo** (40 reuniones usadas, descriptivo), ARI medio:

  | enlace | regla K | ARI | K mediana |
  |---|---|---|---|
  | promedio | silueta (EXP-022) | 0.186 | 2 |
  | promedio | K = 4 conocido | 0.232 | 4 |
  | ward | silueta | 0.202 | 2 |
  | ward | K = 4 conocido | 0.287 | 4 |

  Ward es mejor con todas las reglas. La silueta sub-agrupa (2 frente a 4
  hablantes).
- **EXP-022b (producción, sin prior):** ward + silueta. Mismos criterios que
  EXP-022 en las 40 reuniones nuevas, más ARI(ward) − ARI(promedio) > 2 SE
  pareado.
- **EXP-022c (cota descriptiva):** ward + K = nº real de hablantes. Indica
  cuánto se ganaría estimando bien el número de hablantes.

### Producto: reuniones (AMI) con hablantes por voz
- Mapas de tópicos de reuniones con el perfil "meeting" (p95/r90): 9–11
  tópicos por reunión. Cada tópico y cada clip llevan `speakers`
  (identidades de voz V#, ward + silueta, con su fracción); además etiqueta,
  provenance y contexto (`scripts/build_ami_topic_maps.py`).
- Versiones:
  - "threads" solo aplica si el video tiene tópicos que retornan (si no, se
    marca no aplicable en vez de fallar);
  - nuevo perfil **speaker_threads**: por cada una de las 3 voces
    principales, los clips donde esa voz domina (81 playlists en 40
    reuniones).
- G-versión: **40/40** reuniones AMI y 58/58 películas val.

### EXP-022d · K por BIC (pre-registro, antes de las señales de las reuniones nuevas)
- **Desarrollo** (40 usadas, descriptivo), ward más regla de K:
  - silueta: 0.202 (K = 2);
  - eigengap: 0.205 (K = 2);
  - **BIC de mezcla gaussiana (PCA 16, diag): 0.275 (K = 3)**;
  - K real: 0.287 (cota).
- **Regla fijada:** ward + K ∈ {2, …, 8} por BIC mínimo.
- **Criterios en las 40 reuniones nuevas:**
  1. ARI(022d) − ARI(022b, ward + silueta) > 2 SE pareado;
  2. ARI(022d) − ARI(visual, misma regla) > 2 SE;
  3. especificidad > 0.5 (binomial, p < 0.05).

### Enmienda a EXP-021c (2026-10-03, antes de calcular las señales de las reuniones nuevas)
- **Defecto del pre-registro:** "contiguous con el mismo perfil" a p95 colapsa
  en un solo tópico (MCC 0.058 en desarrollo): sería una base trivialmente
  débil. La base justa es v2.1 contiguo en su propia configuración (p80),
  que dio 0.31–0.34 en EXP-020. `eval_ami.py` usa p80 para contiguous desde
  ahora; criterios sin otros cambios.
- **Exploración de retornos más raros** (desarrollo, descriptivo): p95/r99
  0.316 frente a p95/r90 0.299, dentro del ruido. No se añade variante; el
  perfil meeting sigue en p95/r90.

### Resultados en 40 reuniones AMI NUEVAS (jobs 54177 + 54180)
**EXP-020a, replicación:** AUC voice 0.737 frente a visual 0.549, voice −
visual +0.188 ± 0.016 (**z 12.1**); voice − 0.5 = +0.237 ± 0.015. ✅

**EXP-021c, perfil meeting (p95/r90) con voz:**

| criterio | resultado | |
|---|---|---|
| 1. no inferior a contiguous v2.1 (p80) | −0.062 ± 0.039 (z −1.6, dentro de −2 SE) | ✅ |
| 2. frente a fused | **+0.089 ± 0.027 (z 3.4)** | ✅ |
| 3. frente al perfil film (p80/r90) | +0.036 ± 0.035 (z 1.0) | ❌ |
| (desc.) aporte de la voz: con − sin | **+0.063 ± 0.028 (z 2.2)** | |

- **Parcialmente validado:**
  - el mapa CAVA para reuniones con voz no es inferior a la segmentación
    contigua y supera a la fusión;
  - la voz aporta de forma significativa como votante;
  - la ventaja del perfil meeting sobre el film no se confirma (la
    exploración ya mostraba ruido).
  - En reuniones, lo contiguo sigue siendo una base muy fuerte (0.25):
    CAVA lo iguala, no lo supera.

**EXP-022 (identidades por voz) y variantes:**

| variante | ARI voice | ARI visual | especificidad | criterio | |
|---|---|---|---|---|---|
| 022: promedio + silueta | 0.211 | 0.018 | 0.93 (76/82) | voice − visual +0.193 ± 0.025; ARI > 0 | ✅ |
| 022b: ward + silueta | 0.232 | 0.070 | 0.89 | ward − promedio +0.021 ± 0.016 (z 1.3) | ❌ |
| **022d: ward + BIC** | **0.297** | 0.080 | 0.87 | BIC − silueta +0.065 ± 0.018 (**z 3.5**); voice − visual +0.217 | ✅ |
| 022c: ward + K real (cota) | 0.310 | 0.103 | 0.85 | descriptivo | |

- **✅ VALIDADO:** las identidades por voz siguen a los hablantes reales
  (ARI 0.21–0.30, frente a 0.02–0.10 de la apariencia) y son específicas
  (87–93 % superan a grupos al azar, frente a 0.55–0.63 de las P# por
  apariencia en películas).
- La regla BIC queda a 0.013 de la cota con K conocido. **Regla de producto:
  ward + K por BIC.**

`results/exp021c_ami_fresh.json` · `results/exp022*_fresh.json`

---

## EXP-023 · Votante de fronteras por cambio de quién tiene la palabra (pre-registro)
- **Fecha:** 2026-10-03 (registrado antes de calcular las señales del tercer
  lote)
- **Idea:** en reuniones, el cambio de tópico suele coincidir con un cambio
  de quién habla (por ejemplo, el turno del siguiente presentador). Votante
  de fronteras: divergencia Jensen-Shannon entre el histograma de
  identidades de voz (ward + BIC, EXP-022d) de las `w` unidades anteriores y
  el de las siguientes (`scripts/speaker_turns.py`).
- **Desarrollo** (40 reuniones usadas, perfil meeting), MCC:

  | sistema | MCC | frente a base |
  |---|---|---|
  | base (cava con voz) | 0.299 | — |
  | + turnos w = 3 | 0.290 | −0.009 ± 0.020 |
  | **+ turnos w = 6** | **0.373** | **+0.074 ± 0.027** |
  | + turnos w = 12 | 0.332 | +0.033 ± 0.039 |
  | contiguous v2.1 (p80) | 0.326 | +0.027 ± 0.038 |

  **w = 6 (1 min) queda fijado.**
- **Confirmación:** tercer lote de 40 reuniones AMI nunca usadas
  (`data/ami/meetings_fresh3.txt`), perfil meeting, mismas señales.
- **Criterios:**
  1. MCC(cava + turnos) − MCC(cava) > 2 SE;
  2. MCC(cava + turnos) − MCC(contiguous v2.1 p80) > 2 SE (superar a lo
     contiguo, que hasta ahora CAVA solo igualaba);
  3. MCC(cava + turnos) − MCC(fused) > 2 SE.

### Resultado EXP-023 (tercer lote, 39 reuniones evaluables; jobs 54273 + 54274)

| sistema | MCC |
|---|---|
| **cava + turnos (w = 6)** | **0.234** |
| contiguous v2.1 (p80) | 0.221 |
| cava con voz | 0.159 |
| fused | 0.100 |
| cava sin voz | 0.093 |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. turnos − cava con voz | +0.075 ± 0.032 | 2.32 | **sí** |
| 2. turnos − contiguous | +0.013 ± 0.048 | 0.27 | **no** |
| 3. turnos − fused | +0.134 ± 0.038 | 3.52 | **sí** |

**Validado en parte.** El votante de turnos aporta lo mismo que en desarrollo
(+0.075 frente a +0.074): es la mejora más estable vista en reuniones. Pero no
supera a lo contiguo; solo lo iguala.

Lectura honesta del lote:
- En este lote, cava con voz y sin turnos queda **por debajo** de lo contiguo
  (−0.062 ± 0.044, z −1.41). Los turnos lo devuelven a la paridad.
- La señal de voz sigue identificando al hablante (AUC 0.73 frente a visual
  0.55, z 12.9) y sigue aportando dentro de CAVA (con frente a sin voz:
  z 2.46).
- Conclusión: en reuniones, la frontera de tópico la marca sobre todo el
  cambio de quién habla. El retorno de tópicos no agrega MCC sobre lo
  contiguo en AMI (pocos retornos reales en el GT).

**Decisión:** el perfil meeting pasa a incluir el votante de turnos (w = 6).

---

## EXP-024 · Pesos de voto por señal aprendidos (pre-registro)
- **Fecha:** 2026-10-03 (registrado antes de exportar o calcular el tercer
  lote)
- **Idea:** primera ejecución de la infraestructura para "construir pesos".
  ADR-0001 prohíbe fusionar representaciones pero declara los pesos por
  señal como parámetros explícitos. Aquí se aprenden de GT.
- **Método (`scripts/learn_vote_weights.py`):**
  - Entrenamiento con las 80 reuniones AMI ya usadas (dev + conf, export
    `data/training/ami`).
  - Rasgo por señal y par de unidades lejanas (≥ 18): 1 si la señal agrupa el
    par en su propio tópico (perfil meeting, retornos, abstención), 0 si no o
    si se abstiene. Señales: voice, visual, transcript, vjudge, turns
    (EXP-023, w = 6).
  - Logística balanceada sobre "mismo tópico GT". Pesos = coeficientes (piso
    0.05) normalizados a suma 5; quorum = −intercepto en esa escala.
- **Prueba:** tercer lote AMI (`meetings_fresh3.txt`), nunca usado.
- **Criterio:** MCC(pesos aprendidos) − MCC(pesos iguales, quorum 2), mismas
  señales y perfil, > 2 SE pareado.


## Producto · Pipeline de punta a punta sobre contenido largo (job 54272, 2026-10-03)

`scripts/cava_run.py` sobre 4 videos sin GT (no es un experimento: es una
corrida de producto; las observaciones de abajo son hipótesis, no resultados).

| video | perfil | duración | tópicos | con retornos | voces | G-versión | clips |
|---|---|---|---|---|---|---|---|
| 98MoyGZKHXc (TVSum) | film | corto | — | — | — | ✓ | 9 |
| IS1000c (AMI, audio Mix-Headset) | meeting | 35.7 min | 9 | — | — | ✓ | 18 |
| bbc_01 (documental) | film | 49.3 min | 59 | 37 | 6 | ✓ | 146 |
| bbc_02 (documental) | film | 48.1 min | 54 | 29 | 8 | ✓ | 126 |

Verificado en los BBC:
- todos los mp4 de versión llevan video y audio (ffprobe);
- recap 60.0 s;
- highlights 285–295 s, que es el 10 % de la duración;
- hilos ≤ 10 % cada uno;
- el mapa cubre el 100 % de la duración;
- `index.md` trae rangos, retornos, hablantes y etiquetas.

Los tópicos de menos de 30 s llevan como etiqueta el resumen VJudge, no la
etiqueta de 14B (diseño: `labels(min_dur=30)`).

Observaciones (abiertas):
1. **Granularidad:** el perfil film (p80/r90) en un documental de 49 min da
   ~55 tópicos de ~50 s, con retornos temáticos coherentes. Ejemplos:
   - pingüinos al inicio y al final;
   - osos polares en 3–8 min.

   Hay varios tópicos casi duplicados (11 y 12, osos polares). Para un
   consumidor, el nivel `default` es fino. Candidato: un perfil `documentary`
   o un nivel `coarse`. Hay que pre-registrarlo con GT de capítulos; sin GT
   no se valida.
2. **Voces:** 6–8 identidades de voz en un documental con un solo narrador.
   ward + BIC (validado en reuniones, EXP-022d) **sobre-segmenta** cuando hay
   música y sonido ambiente. Las identidades de voz quedan validadas solo en
   habla conversacional. Candidato: aplicar la voz solo en unidades con habla
   ASR. Se pre-registraría con GT de hablantes en material narrado.

### Resultado EXP-024 (tercer lote, 39 reuniones evaluables)

- **Pesos aprendidos** (1.19 M pares de entrenamiento, 80 reuniones), con
  quorum 1.36:

  | voice | visual | transcript | vjudge | turns |
  |---|---|---|---|---|
  | 1.03 | 0.73 | 0.68 | 0.54 | **2.01** |

- **Consistencia:** con pesos iguales se obtiene MCC 0.234, idéntico por
  reunión al cava + turnos de EXP-023 (diferencia máxima 0.0). Es la misma
  línea base.

| criterio | MCC iguales | MCC aprendidos | diferencia | z | ¿cumple? |
|---|---|---|---|---|---|
| aprendidos − iguales > 2 SE | 0.234 | 0.265 | +0.031 ± 0.026 | 1.22 | **no** |

**No validado.** La mejora va en la dirección esperada, pero no supera el
umbral.

Exploratorio (no pre-registrado; no cuenta como resultado):
- aprendidos frente a contiguous: +0.044 ± 0.054 (z 0.81);
- los pesos aprendidos dan tópicos más gruesos: 4.7 frente a 5.8 por reunión.

Lo que sí deja el experimento:
1. **La infraestructura de pesos funciona de punta a punta:**
   export → rasgos por señal → pesos explícitos → `manage(weights=…)` →
   evaluación en datos no vistos.
2. **El orden de los pesos coincide con la evidencia independiente:**
   - turnos ≈ 2× (EXP-023);
   - voz > visual ≈ transcript > vjudge (AUC de EXP-020a).

   Es una ponderación interpretable, no una caja negra.

**Decisión:** el perfil meeting se queda con pesos iguales (lo validado). La
siguiente palanca de pesos no es el peso de voto: es la granularidad (el
quorum aprendido engrosa los tópicos). Hay que aprenderla con un objetivo
que mida directamente la granularidad.

---

## EXP-025 · Documentales: estructura CAVA frente a escenas humanas (BBC Planet Earth, pre-registro)
- **Fecha:** 2026-10-04 (registrado antes de calcular las señales de los
  episodios 05–11, jobs 54320 / 54321)
- **Dominio nuevo para CAVA:** BBC Planet Earth, 11 episodios de ~49 min,
  audio en italiano, con escenas GT de 5 anotadores (Baraldi et al. 2015).
  SegLoop se evaluó aquí zero-shot (F1 0.13); CAVA nunca se ajustó con
  estos episodios.
- **Pregunta:** ¿el perfil film transfiere a documentales, o hace falta un
  perfil `documentary` más grueso (observación abierta de la corrida de
  producto)?
- **Métrica** (`scripts/eval_bbc.py`):
  - M_local: MCC de "misma escena" sobre pares de unidades de 5 s a
    distancia ≤ 5 min (60 unidades), promedio sobre los 5 anotadores.
  - Secundarias: F1 de fronteras (±1 unidad) y techo humano (cada anotador
    frente a los otros 4).
- **Desarrollo:** episodios 01–04.

  01–02 ya medidos (`results/exp025_bbc_dev12.json`):

  | sistema | M_local |
  |---|---|
  | **cava p90** | **0.368** |
  | cava p95 | 0.330 |
  | cava p80 | 0.311 |
  | cava p70 | 0.246 |
  | fused p80 | 0.247 |
  | contiguous p80 | 0.197 (colapsa en 5–11 segmentos) |
  | techo humano | 0.57 |

- **Regla de elección (fija desde ahora):** p* = el percentil en {80, 90, 95}
  con mayor M_local medio en los episodios 01–04 (r90, average, abstain,
  quorum 2).
- **Confirmación:** episodios 05–11 (n = 7, nunca evaluados).
- **Bases:** contiguous v2.1 y fused, cada una evaluada en p80 y en p*. Por
  episodio se toma la **mejor** de las dos, lo que es conservador para CAVA.
- **Criterios (M_local, SE pareado sobre los 7 episodios):**
  1. cava p* − mejor contiguous > 2 SE;
  2. cava p* − mejor fused > 2 SE;
  3. si p* ≠ 80: cava p* − cava p80 > 2 SE (justifica el perfil
     `documentary`);
  4. G-coherencia: margen de coherencia > 0 para cada señal en ≥ 6 de 7
     episodios.
- **Limitación declarada:** el GT de escenas es contiguo. Un retorno legítimo
  (el mismo tema más tarde) cuenta como error si cae dentro de 5 min. La
  métrica favorece lo contiguo, no a CAVA.

## EXP-026 · Voz con un solo narrador (pre-registro)
- **Fecha:** 2026-10-04 (antes de las señales de 05–11)
- **Observación de producto:** 6–8 identidades de voz en episodios con un
  narrador.
- **Desarrollo (BBC 01–02 + 15 reuniones AMI dev):**
  1. **K = 1 permitido en BIC: descartado en desarrollo.** No cambia nada en
     BBC (K_eff 6 y 8). En AMI, 3 de 15 reuniones colapsan a K = 1
     (ARI 0).
  2. Los grupos en BBC son parejos (~20 % cada uno), no un narrador dominante
     más ruido. La voz, z-normalizada por video, capta la escena acústica
     (música, ambiente), no al hablante. La silueta en BBC (0.20–0.31) cae
     dentro del rango de AMI (0.25–0.42): no hay umbral que los separe.
  3. Filtrar a las unidades con habla ASR (≥ 50 % de la unidad cubierta por
     segmentos ASR) baja K_eff de 6 a 4 y de 8 a 5. Es el único candidato que
     queda.
- **Criterios:**
  1. BBC 03–11 (n = 9): err(gate) < err(base) por > 2 SE pareado, con
     err = |K_eff − 1| y K_eff = nº de identidades con ≥ 5 % de las unidades
     con habla.
  2. No inferioridad en AMI fresh3: ARI(gate) − ARI(base) > −0.02 (media).
     En AMI el filtro es "unidad con texto ASR", porque AMI no guarda tiempos
     de segmento.
- **Lo que no cambia con ningún resultado:** la identidad por voz solo está
  validada en habla conversacional (EXP-020/022). En el perfil film o
  documentary, los V# se marcan como "agrupación acústica", no como
  hablantes.

### Resultado EXP-025 (BBC Planet Earth; jobs 54320 + 54322)

**Desarrollo (01–04), M_local medio:**

| p80 | p90 | p95 |
|---|---|---|
| 0.320 | **0.405** | 0.374 |

→ **p\* = 90**, fijado antes de evaluar 05–11.

**Confirmación (05–11, n = 7)**, M_local medio:

| sistema | M_local | segmentos |
|---|---|---|
| techo humano | 0.662 | — |
| **cava p90** | **0.413** | 79 |
| cava p95 | 0.398 | 37 |
| cava p80 | 0.344 | 138 |
| fused p90 / p95 | 0.281 / 0.280 | — |
| contiguous p80 | 0.239 | 10 |

Escenas humanas por episodio: 25–70.

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. cava p90 − mejor contiguous | +0.174 ± 0.029 | 6.11 | **sí** |
| 2. cava p90 − mejor fused | +0.126 ± 0.017 | 7.41 | **sí** |
| 3. cava p90 − cava p80 | +0.069 ± 0.026 | 2.63 | **sí** |
| 4. G-coherencia | 7/7 episodios en voice, visual, transcript y vjudge | — | **sí** |

**Validado.**
- CAVA transfiere a un dominio nuevo (documental, audio en italiano, nunca
  ajustado) y alcanza el 62 % del techo humano.
- El perfil `documentary` (5 s, p90, r90) queda justificado: la observación
  de producto "demasiado fino" era correcta.
- Lo contiguo, que en AMI era la base más dura, colapsa en documentales
  (3–14 segmentos).

Secundarias (sin criterio):
- **F1 de fronteras:**
  - cava p90: 0.40
  - cava p80: 0.44
  - visual solo: **0.48**
  - techo humano: 0.65

  Para cortar fronteras, la mejor señal sola es la visual. CAVA gana en
  agrupar (M_local), no en fronteras exactas, lo mismo que en películas
  (EXP-010–014).
- **Comparación con SegLoop:** su F1 0.13 es a nivel de shot y no es
  comparable directamente con este F1 por unidades de 5 s.

### Resultado EXP-026 (voz con un narrador)

| criterio | resultado | ¿cumple? |
|---|---|---|
| 1. BBC 03–11 (n = 9): err(base) − err(gate) | +0.89 ± 0.39, z 2.29 | **sí** |
| 2. AMI fresh3: ARI(gate) − ARI(base) | −0.007 ± 0.009 (> −0.02) | **sí** |

**Validado, con alcance limitado.** El filtro de habla reduce los grupos
espurios, pero K_eff sigue en 5.7 frente a 1 (base 6.7). La voz en material
narrado sigue sin identificar al hablante. Por eso queda la regla
pre-registrada: los V# fuera del perfil meeting son "grupos acústicos".

**Cambios en el pipeline:**
- perfil `documentary`;
- identidades de voz solo sobre unidades con habla ASR (todos los perfiles);
- etiqueta de los V# según el perfil.

Prueba de humo: bbc_05 con el perfil documentary da 36 tópicos (frente a ~55
con film) y G-versión ✓.

---

## EXP-027 · Fronteras visuales con agrupamiento CAVA: "snap" (pre-registro)
- **Fecha:** 2026-10-04 (antes de evaluar cualquier película de train2)
- **Motivación:** EXP-025, secundaria: la señal visual sola corta mejor las
  fronteras (F1 0.48) que el consenso CAVA (0.40), pero agrupa peor. ¿Se
  pueden tener ambas cosas?
- **Operador (`snap`, ADR-0001-compatible: usa las fronteras de UNA señal,
  sin fusionar representaciones):**
  1. Cada frontera del mapa CAVA se mueve a la frontera visual más cercana
     si está a ≤ R.
  2. Las unidades intermedias pasan al tópico del lado que se extiende.
  3. Las fronteras visuales salen de manage() con la señal visual sola, p80,
     r90 y quorum 1.
- **Desarrollo:** BBC 01–11 (`scripts/explore_visual_boundaries.py`). Todos
  los episodios ya se usaron; aquí son solo desarrollo.
  - **Base:** cava p90, M 0.410 / F1 0.399.
  - **Resultados frente a la base:**

    | variante | ΔM | ΔF1 |
    |---|---|---|
    | snap R = 6 unidades (30 s) | +0.043 ± 0.006 | +0.045 ± 0.012 |
    | snap R = 8 | +0.049 | +0.050 |
    | **control** fronteras al azar (mismo nº que la visual), R = 6 | +0.003 | −0.096 |
    | **control** suavizado (rachas < R se absorben), R = 6 | +0.020 | −0.085 |
    | peso de voto visual 1.5 | −0.041 | +0.041 |
    | peso de voto visual 2.0 | −0.087 | +0.052 |

    Solo el snap mejora ambas métricas. El efecto viene de las fronteras
    visuales, no del suavizado.
- **R fijado = 30 s** (en el tiempo, no en unidades), donde la ganancia se
  satura en desarrollo.
- **Confirmación:** MovieNet train2, 91 películas.
  - Dominio distinto: ficción, unidades = shots de ~3.2 s, escenas GT de
    MovieNet.
  - Nunca se usaron para evaluar estructura (solo personajes, EXP-019e).
  - Señales del export (`data/training/movienet`): visual, dialogue,
    vjudge.
  - Configuración validada de películas: EXP-018 (p80, r90, average,
    abstain, quorum 2).
- **Métricas:**
  - M_local: MCC de "misma escena" sobre pares de shots con centros a
    ≤ 300 s;
  - F1_b: fronteras, tolerancia ±1 shot.
- **Criterios (SE pareado sobre películas):**
  1. snap30 − cava > 2 SE en M_local **y** en F1_b;
  2. snap30 − control al azar (snap30 a fronteras aleatorias, mismo nº,
     5 semillas) > 2 SE en M_local **y** en F1_b.
- **Secundaria (sin criterio):** snap con R = 6 unidades (6 shots).

### Resultado EXP-027 (MovieNet train2, 91 películas)

| sistema | M_local | F1_b |
|---|---|---|
| cava (EXP-018) | 0.226 | 0.434 |
| **snap30** | **0.317** | 0.488 |
| control: snap30 a fronteras al azar | 0.274 | 0.326 |
| visual sola | 0.289 | **0.535** |
| snap 6 shots (secundaria) | 0.291 | 0.479 |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. snap30 − cava, M_local | +0.091 ± 0.003 | 26.6 | **sí** |
| 1. snap30 − cava, F1_b | +0.054 ± 0.002 | 23.0 | **sí** |
| 2. snap30 − al azar, M_local | +0.043 ± 0.004 | 12.4 | **sí** |
| 2. snap30 − al azar, F1_b | +0.162 ± 0.006 | 27.8 | **sí** |

**Validado.** Desarrollado en documentales y confirmado en ficción.

Lectura honesta:
1. **Parte de la ganancia en M_local es absorción de fragmentos.** El control
   al azar también sube M_local frente a cava (0.274 frente a 0.226). La
   parte atribuible a las fronteras visuales es +0.043 en M_local y +0.162
   en F1.
2. **En escenas locales de películas, la visual sola (0.289) supera a cava
   p80 (0.226).** Lo validado de CAVA en películas (EXP-018) son enlaces de
   largo alcance (hilos y retornos), no escenas locales. Con snap, CAVA
   supera también a la visual sola en M_local (0.317). La visual sola sigue
   mejor en F1 de fronteras exactas (0.535 frente a 0.488).
3. El mapa resultante combina las fronteras de una señal con el agrupamiento
   por consenso. Es la división de trabajo que sugerían EXP-010–014 y
   EXP-025.

**Adopción:**
- `build_topic_map(snap_visual_s=…)`, por defecto apagado;
- perfiles film y documentary del pipeline con R = 30 s;
- meeting sin snap (no validado en reuniones; la cámara de AMI es fija);
- tests en `tests/test_snap.py`.

---

## EXP-028 · Identidad del hablante fuera de reuniones: embedding de hablante frente a rasgos de voz (pre-registro)
- **Fecha:** 2026-10-04 (registrado antes de descargar o ver VoxConverse)
- **Motivación:**
  - EXP-026: con narrador y música, los rasgos de voz (log-mel + tono,
    z-score por video) agrupan la escena acústica, no al hablante.
  - Para hablantes en material no conversacional hace falta una señal
    invariante al fondo.
- **Datos:** VoxConverse (Chung et al. 2020; anotaciones CC BY 4.0).
  - Contenido: noticias, debates y programas de YouTube, con música, ruido
    y solapamientos; diarización GT (RTTM).
  - Desarrollo: dev (216 archivos). Confirmación: test (232), nunca visto.
- **Señal nueva (`xvec`):** WavLM-base-plus-sv, frozen.
  - Pesos: `refs/pr/4` (sha 939f573b), conversión safetensors de
    SFconvertbot. Verificado: los 266 tensores son idénticos al
    `pytorch_model.bin` oficial.
  - Riesgo declarado: está entrenado en VoxCeleb (YouTube). Puede haber
    personas en común con VoxConverse; los segmentos, no.
- **Protocolo** (`scripts/eval_speaker_embed.py`):
  - unidades de 5 s;
  - hablante dominante GT: ≥ 60 % del habla y ≥ 1.5 s;
  - filtro de habla con VAD oráculo (≥ 50 % de la unidad), el mismo para
    ambas señales;
  - identidades con ward + K por BIC (EXP-022d) para ambas.
- **Criterios (test, SE pareado por archivo):**
  1. AUC(xvec) − AUC(hand) > 2 SE;
  2. ARI(xvec) − ARI(hand) > 2 SE;
  3. |K_eff − K_true|(hand) − |K_eff − K_true|(xvec) > 2 SE.
- **Si se valida:**
  - `xvec` reemplaza a los rasgos de voz para la IDENTIDAD (V#) en todos los
    perfiles;
  - antes de cambiar el perfil meeting se comprueba la no inferioridad en
    AMI fresh3 (ARI, margen −0.02);
  - los rasgos de voz se quedan como votante de TÓPICO (lo validado en
    EXP-021c / 025).

### Hallazgo: deriva de idioma en etiquetas 14B (2026-10-04)

Qwen2.5-14B a veces continúa la etiqueta en chino a mitad de frase.

Afectados:
- pipeline: 2 de 368 etiquetas, ambas en bbc_09 (audio en italiano);
- etiquetas MovieNet ya evaluadas (EXP-019): 374 de 28 394 entradas
  (1.3 %).

Impacto en EXP-019: los nombres en latín quedan intactos. El texto añadido
solo podría sumar falsos "contenidos", y con 1.3 % de entradas no cambia las
conclusiones. No se re-evalúa.

**Corrección:** `clean_label` corta la etiqueta en el primer carácter CJK.
Se aplica en el pipeline al leer la caché; bbc_09 se regeneró desde caché con
el mismo mapa (37 tópicos, 65 clips).

### Producto · BBC Planet Earth completo con el perfil documentary + snap (jobs 54332 + 54333)

Configuración:
- perfil `documentary`: p90 + snap 30 s (EXP-025 / 027);
- identidades de voz con filtro de habla (EXP-026), publicadas como "grupos
  acústicos";
- etiquetas 14B limpias.

Resultados por episodio (11 episodios):
- 32–38 tópicos, de los cuales 10–15 con retornos;
- 26–31 tópicos con etiqueta 14B (los de ≥ 30 s);
- 62–70 clips; **730 clips** en total;
- G-versión ✓ en 11/11.

Comparación con el perfil film anterior:
- antes: 54–59 tópicos y 126–146 clips por episodio;
- ahora la granularidad se acerca a la de las escenas humanas.

Salida en `data/cava_runs_doc/`. Las versiones sin snap se conservan en
`data/cava_runs_doc_nosnap/` (solo bbc_01).

### Resultado EXP-028 (VoxConverse; jobs 54341, 54342, 54347)

| split | AUC voz / xvec | ARI voz / xvec | \|K_eff − K_true\| voz / xvec |
|---|---|---|---|
| dev (216) | 0.790 / **0.976** | 0.308 / **0.604** | 2.03 / **1.59** |
| test (232) | 0.735 / **0.962** | 0.249 / **0.635** | 1.84 / **1.27** |

| criterio (test) | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. AUC xvec − voz | +0.226 ± 0.008 | 28.5 | **sí** |
| 2. ARI xvec − voz | +0.386 ± 0.021 | 18.7 | **sí** |
| 3. err voz − xvec | +0.565 ± 0.088 | 6.4 | **sí** |

**Validado.**

Comprobaciones previas a la adopción:
- **AMI fresh3 (no inferioridad para el perfil meeting):** ARI 0.286 → 0.731
  (+0.445 ± 0.041). Cumple de sobra: la identidad en reuniones mejora 2.5×.
- **BBC (sin criterio):** K_eff de narrador 5.3 → 4.1. Mejora, pero no llega
  a 1.

**Modo de fallo común: un solo hablante.**
- En VoxConverse, los archivos con K_true = 1 tienen error de K de 1.9–2.3
  con xvec, frente a 1.2–1.5 en los de varios hablantes.
- Causa: K por BIC empieza en 2, y ward sobre-divide. Permitir K = 1 en BIC
  ya se descartó (EXP-026: colapsa reuniones).
- Hace falta un detector previo de "¿hay más de un hablante?". Es candidato
  a EXP-029.

**Adopción:**
- `topicagg/speaker.py` (XVec, pesos fijados) y caché
  `work/speaker_xvec.npy`;
- la IDENTIDAD (V#) usa xvec en los tres perfiles;
- `voice_identity_kind`:
  - meeting y film: "hablante";
  - documentary: "grupo acústico", hasta resolver el narrador único;
- el votante de turnos del perfil meeting (EXP-023) sigue con los rasgos de
  voz, su configuración validada;
- prueba de humo en IS1000c: 4 hablantes (4 participantes reales).
- Pendiente: regenerar los mapas AMI de producto
  (`build_ami_topic_maps.py`) con xvec.

---

## EXP-029 · Detector de "un solo hablante" antes de agrupar identidades (pre-registro)
- **Fecha:** 2026-10-04 (registrado antes de calcular o ver los embeddings
  cacheados; job 54371)
- **Problema (EXP-028):**
  - K por BIC empieza en 2: con un solo hablante, xvec da error de K
    1.9–2.3 en VoxConverse y 4.1 grupos para el narrador de BBC.
  - Permitir K = 1 dentro de BIC sobre rasgos de voz colapsa reuniones
    (EXP-026).
- **Regla:** antes de ward + BIC, un detector decide si hay un solo hablante.
  Si dice que sí, todas las unidades con habla son V1.
- **Candidatos (todos sobre xvec, unidades con habla):**
  - **D1 spread:** mediana de la similitud coseno de cada unidad con la
    xvec media del archivo. Un hablante si ≥ τ.
  - **D2 bic12:** BIC(GMM K=1) − BIC(GMM K=2) sobre PCA-16 (diag). Un
    hablante si < τ.
  - **D3 sil2:** silueta (coseno) de ward con K = 2. Un hablante si < τ.
- **Desarrollo:** VoxConverse dev (31 archivos con un hablante, 185 con
  varios) más AMI dev (`meetings_40`; nunca hay un solo hablante).
  - Para cada candidato, τ maximiza la exactitud balanceada (uno frente a
    varios) en VoxConverse dev, sujeto a 0 reuniones AMI dev declaradas de
    un hablante.
  - Se elige el candidato con mayor exactitud balanceada en dev.
- **Confirmación:**
  - VoxConverse test (232; 25 con un hablante);
  - AMI fresh3 (40) como control negativo;
  - BBC 01–11 (narrador único supuesto), sin criterio.
- **Criterios:**
  1. VoxConverse test: \|K_eff − K_true\| sin detector − con detector > 2 SE
     pareado (todos los archivos);
  2. VoxConverse test, archivos con ≥ 2 hablantes: ARI con − sin > −0.02
     (no inferioridad);
  3. AMI fresh3: 0 de 40 reuniones declaradas de un hablante.
- **Secundarias:** exactitud balanceada en test; nº de episodios BBC
  declarados de un hablante.

### Resultado EXP-029 (job 54372 de caché; evaluación en CPU)

**Desarrollo** (VoxConverse dev: 25 archivos con un hablante y 184 con
varios; AMI dev: 40 reuniones), exactitud balanceada con τ óptimo y
0 reuniones AMI declaradas de un hablante:

| candidato | exactitud balanceada |
|---|---|
| **spread** | **0.881** (τ 0.976; un hablante 80 %, varios 96 %) |
| bic12 | 0.722 |
| sil2 | 0.660 |

→ spread, congelado antes de la confirmación (commit "EXP-029 dev").

**Confirmación:**

| criterio | resultado | ¿cumple? |
|---|---|---|
| 1. VoxConverse test (232): error de K sin − con detector | +0.155 ± 0.060, z 2.60 | **sí** |
| 2. archivos con ≥ 2 hablantes (205): ARI con − sin | −0.019 (margen −0.02) | **sí, por muy poco** |
| 3. AMI fresh3: reuniones declaradas de un hablante | 0 de 40 | **sí** |

Secundarias:
- exactitud balanceada en test: 0.850;
- en archivos con un hablante, el error de K baja de 1.88 a **0.28**.

**Validado.** Advertencia: el criterio 2 pasa por muy poco. El detector
cuesta casi 0.02 de ARI en contenido con varios hablantes (falsos
"un hablante"). Es lo esperable con una especificidad del 96 %.

**BBC (secundaria): 0 de 11 episodios detectados como de un hablante.**
Diagnóstico:
- El spread de BBC es 0.91–0.95, en el rango de "varios hablantes" de
  VoxConverse (mediana 0.935).
- El cuartil inferior de similitud al centro está en ~0.65: hay una cola
  de unidades que no son del narrador.
- Causa probable: el filtro de habla. En VoxConverse es VAD oráculo; en BBC
  es "≥ 50 % cubierta por segmentos ASR", y Whisper cubre el 87 % del
  documental, incluidos tramos de música y sonido animal.
- El cuello de botella en documentales es el **VAD**, no el embedding.
  Candidato a EXP-030: un VAD real como filtro de habla.

**Adopción:**
- `topicagg/speaker.single_speaker` en el pipeline (perfiles con xvec) y en
  `build_ami_topic_maps.py`;
- test en `tests/test_snap.py`;
- el perfil documentary sigue publicando "grupos acústicos".

### Producto · Mapas AMI regenerados con identidades xvec + detector de un hablante (job 54382)

120 reuniones (las 80 de antes más el tercer lote), G-versión 120/120.
Copia de los 80 mapas anteriores en `data/ami/{topic_maps,versions}_v022d_backup`.

Identidades frente al GT (todas las reuniones AMI tienen 4 hablantes):

| | voz (antes) | xvec (ahora) |
|---|---|---|
| ARI frente al hablante dominante | 0.288 | **0.726** |
| K bruto (todas las identidades) | 3.18 | 4.13 |
| K_eff (≥ 5 % de las unidades con habla) | 3.17 | 3.65 |
| \|K_eff − 4\| | 0.95 | 0.97 |

Lectura:
- Los grupos de xvec son mucho más puros: ARI 2.5×.
- El NÚMERO de hablantes se estima igual de mal con ambas señales (error
  ~0.96).
- xvec añade grupos pequeños (< 5 %): risas, solapamientos, ruido. En el
  `index`, los V# con poca fracción deben leerse como menores.
- El detector de un hablante no se activó en ninguna de las 120 reuniones.

---

## EXP-030 · Parakeet TDT 0.6B v3 frente a Whisper large-v3 como ASR único del pipeline (pre-registro)
- **Fecha:** 2026-10-04 (registrado antes de transcribir ningún conjunto de
  evaluación con Parakeet)
- **Pedido:** un solo modelo ASR. Parakeet sustituye a Whisper solo si se
  valida aquí. La tabla del Open ASR Leaderboard (AMI 9.42 frente a 13.88 de
  Whisper large-v3-turbo) es evidencia de WER en inglés, no de lo que CAVA
  usa del ASR:
  - el filtro de habla (EXP-026 / 029);
  - el texto por unidad (señal `transcript` y etiquetas 14B);
  - el italiano de BBC.
- **Modelo:** `nvidia/parakeet-tdt-0.6b-v3`, revisión 541d1f99, safetensors
  oficiales de NVIDIA, CC-BY-4.0, 25 idiomas (incluye el italiano).
  - Ejecución: transformers `ParakeetForTDT`, decodificación greedy, una
    transcripción por unidad (5 s film/documentary, 10 s meeting).
  - Filtro de habla = la unidad tiene texto no vacío.
  - Riesgo declarado: los datos de entrenamiento de NVIDIA incluyen AMI;
    puede inflar la calidad del texto en AMI.
- **Comparación:** Whisper large-v3 (faster-whisper, fp16, `vad_filter`)
  exactamente como en el pipeline. Filtro de habla = unidad cubierta ≥ 50 %
  por segmentos.
- **Criterios:**
  1. **Filtro de habla frente a VAD oráculo** (VoxConverse test; unidad de
     habla GT = ≥ 50 % de habla RTTM). En archivos con ≥ 5 unidades GT sin
     habla:
     - tasa de falsa habla FSR(whisper) − FSR(parakeet) > 2 SE pareado;
     - pérdida de habla, en todos los archivos: miss(parakeet) −
       miss(whisper) < +0.02.
  2. **Identidades** (VoxConverse test, xvec + detector EXP-029, con cada
     filtro): \|K_eff − K_true\| parakeet − whisper < +0.05 (no
     inferioridad).
  3. **Mapas de tópicos con el texto de cada ASR** (no inferioridad,
     media > −0.02):
     - AMI fresh3: MCC del perfil meeting (cava + turnos, como EXP-023);
     - BBC 01–11: M_local del perfil documentary con snap (como
       EXP-025 / 027).
- **Secundaria:** episodios BBC detectados de un hablante con el filtro de
  Parakeet; fracción de habla en BBC.
- **Adopción si 1–3 se cumplen:** Parakeet reemplaza a Whisper en todo el
  pipeline (texto por unidad y filtro de habla) y Whisper se retira.

### Resultado EXP-030 (caché job 54414; evaluación en CPU)

| criterio | Whisper | Parakeet | diferencia | ¿cumple? |
|---|---|---|---|---|
| 1a. Falsa habla (FSR), VoxConverse test, 114 archivos con ≥ 5 unidades sin habla | 0.669 | 0.666 | +0.003 ± 0.025, z 0.11 | **no** |
| 1b. Pérdida de habla, margen +0.02 | 0.015 | 0.060 | +0.045 | **no** |
| 2. \|K_eff − K_true\|, margen +0.05 | 1.241 | 1.203 | −0.039 | sí |
| 3a. AMI fresh3 MCC, 39 reuniones (Whisper reproduce EXP-023: 0.2338) | 0.234 | 0.249 | +0.015 ± 0.033 | sí |
| 3b. BBC M_local, 11 episodios, margen −0.02 | 0.462 | 0.440 | −0.022 ± 0.012 | **no, por poco** |

**No validado.** Parakeet no reemplaza a Whisper; el pipeline sigue con
Whisper large-v3. La ventaja de WER del leaderboard no se traduce en lo que
CAVA usa del ASR:
- **Filtro de habla en VoxConverse:** igual en falsa habla y peor en pérdida
  de habla. A 5 s por unidad, ambos modelos transcriben las palabras de
  unidades con menos del 50 % de habla. La métrica por unidad es gruesa, pero
  es la pre-registrada.
- **Texto por unidad:** transcribir 5 s aislados pierde contexto. En BBC
  (italiano) el mapa empeora un poco; en AMI mejora sin ser significativo.

Secundarias (pistas, no resultados):
- **Fracción de habla en BBC:** Whisper 0.87, Parakeet 0.66. Parakeet sí
  deja fuera la música.
- **Narrador único en BBC:** con el filtro Parakeet ∩ Whisper, **10 de 11
  episodios** quedan detectados como de un hablante (frente a 0 de 11 con
  Whisper).
  - Es la primera vez que el narrador se resuelve, pero no hay GT de habla
    en material narrado para validarlo.
  - Además exigiría correr dos ASR, contra el pedido de un solo modelo.
  - Hipótesis abierta: para validarla hace falta un conjunto narrado con
    VAD o diarización GT.

---

## Corrida limpia v1 para entrenamiento (RL): contrato de salida
- **Fecha:** 2026-10-05
- **Por corrida** (`<out>/<video>/`):
  - `run_manifest.json`, esquema `cava-run-v1`:
    - commit git y si el código está sucio;
    - revisión exacta de los 6 modelos (Whisper large-v3, SigLIP, bge,
      Qwen2.5-VL-7B, Qwen2.5-14B, WavLM-sv);
    - perfil completo;
    - sha256 de la entrada;
    - tiempos por etapa;
    - `gt_used: false`.
  - `clips.jsonl`: una fila por clip, el espacio de acciones y trayectorias:
    - `clip_id` (video:t0-t1), versión, playlist y orden;
    - tramo, tópico, etiqueta, retornos y si está recortado;
    - provenance por señal, hablantes, qué se ve y qué se dice.
- **Clips nombrados por tramo exacto:** un mapa nuevo no reutiliza un clip
  viejo. Era un riesgo real, visto con BBC.
- **Recompensas:** se calculan aparte (`rewards.jsonl`), nunca dentro del
  pipeline. El GT no toca el producto.
- **Salida en directorio nuevo** `data/cava_runs_v1/`: sin cachés previas.
  Toda la corrida se recalcula con el stack final.

## EXP-031 · Recompensa de clips frente a importancia humana (TVSum, pre-registro)
- **Fecha:** 2026-10-05 (antes de correr el pipeline sobre TVSum en v1)
- **Datos:** TVSum, 50 videos (2–11 min, 3.5 h), importancia 1–5 por
  fotograma de 20 anotadores. Perfil film, stack final, sin ajuste.
- **Recompensa:**
  - importancia media de los anotadores por segundo, en z-score por video;
  - recompensa de un clip = media de z sobre sus segundos;
  - recompensa de una versión = media ponderada por duración.
- **Versión primaria:** highlights10pct. Secundaria: recap60.
- **Bases (mismos clips en número y duración):**
  - al azar: posiciones uniformes sin solapamiento, 1000 sorteos, media;
  - uniforme: clips equiespaciados.
- **Criterios (SE pareado sobre 50 videos):**
  1. R(cava highlights) − R(al azar) > 2 SE;
  2. R(cava highlights) − R(uniforme) > 2 SE.
- **Expectativa declarada:** highlights elige los tópicos más LARGOS, no los
  más importantes. No hay razón a priori para superar al azar. El resultado
  fija la recompensa de partida antes de cualquier RL; no es un objetivo a
  maximizar aquí.
- **Secundarias:** percentil de CAVA en la nula al azar; correlación por
  clip entre recompensa y duración del tópico; F1 estándar de TVSum al 15 %
  (solo informativo).

## EXP-032 · Estructura de tópicos frente a capítulos del autor (VidChapters blind40, pre-registro)
- **Fecha:** 2026-10-05 (antes de correr el pipeline sobre blind40)
- **Datos:** 40 videos de YouTube (10–40 min, media 21 min, 14 h; 8.8
  capítulos de media) con capítulos del autor (VidChapters-7M).
  - SegLoop sí usó este conjunto (validación ciega v6 y ajuste de fusión
    v8). CAVA nunca: ningún parámetro de CAVA se fijó con él.
- **Perfil primario:** documentary (p90 + snap 30 s; contenido largo no
  ficción, EXP-025 / 027). Secundario: film.
- **Métricas:**
  - M_local: MCC "mismo capítulo" sobre pares de unidades de 5 s a ≤ 5 min;
  - F1 de fronteras, ±1 unidad (secundaria ±3).
- **Criterios (SE pareado sobre 40 videos):**
  1. cava documentary − segmentación uniforme con el mismo nº de segmentos
     > 2 SE (M_local);
  2. cava documentary − mejor contiguous (p80 / p90) > 2 SE;
  3. cava documentary − fused p90 > 2 SE.
- **Limitación:** los capítulos del autor son más gruesos (~2.4 min) que las
  escenas de BBC. No se ajusta la granularidad aquí.

### Corrida limpia v1 (jobs 54535, 54536, 54537)

90 videos (TVSum 50 con perfil film; blind40 40 con perfil documentary),
1 753 clips, G-versión 90/90, `gt_used: false` en todos.

Todos los manifiestos registran el commit e0c24e8 con `git_dirty: true`.
Causa:
- el 2026-10-05 a las 12:12, antes de que arrancara ningún job, alguien
  restauró `docs/EXPERIMENT_LOG.md` y borró los tres `v1_*.sbatch` del árbol
  de trabajo;
- el código del pipeline (`topicagg/`) no cambió, y Slurm usa su copia del
  sbatch;
- las corridas son reproducibles en e0c24e8. Los archivos se restauraron
  desde git el 2026-10-09.

### Resultado EXP-031 (TVSum, 50 videos)

Recompensa = z de la importancia humana media.

| versión | cava | al azar | uniforme | percentil frente a azar |
|---|---|---|---|---|
| highlights10pct | 0.057 | 0.041 | **0.322** | 0.51 |
| recap60 | 0.148 | 0.099 | 0.227 | 0.53 |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. highlights − al azar | +0.017 ± 0.076 | 0.22 | **no** |
| 2. highlights − uniforme | −0.265 ± 0.117 | −2.26 | **no** (lo uniforme es mejor) |

**No validado**, como se esperaba.
- La regla de highlights (tópicos más largos) no sigue la importancia
  humana: la correlación por clip entre duración del tópico y recompensa es
  0.23.
- Los clips equiespaciados cubren todo el video y capturan mejor lo que los
  anotadores valoran. Base dura y conocida en TVSum.
- F1 al 15 %: 0.114 (solo informativo).

**Para RL:**
- 0.057 es la recompensa de partida de la política fija;
- lo uniforme (0.322) es la base a superar;
- `rewards.jsonl` por clip ya existe para los 50 videos.

### Resultado EXP-032 (blind40, 40 videos, capítulos del autor)

| sistema | M_local | F1 ±1 | F1 ±3 |
|---|---|---|---|
| **cava documentary (producto)** | 0.310 | 0.223 | 0.348 |
| cava film | 0.300 | 0.239 | 0.381 |
| uniforme, mismo nº de segmentos (24.0) | 0.319 | 0.133 | 0.313 |
| uniforme con el nº GT de capítulos (oráculo, 8.8) | **0.394** | 0.127 | 0.232 |
| mejor contiguous | 0.264 | — | — |
| fused p90 | 0.243 | 0.243 | 0.386 |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. cava − uniforme mismo nº | −0.009 ± 0.021 | −0.44 | **no** |
| 2. cava − mejor contiguous | +0.046 ± 0.042 | 1.10 | **no** |
| 3. cava − fused | +0.067 ± 0.027 | 2.46 | sí |

**No validado.** Lectura:
- **La granularidad domina.** CAVA hace 24 segmentos (16 tópicos) donde el
  autor pone 8.8 capítulos. Con el nº correcto, incluso lo uniforme llega a
  0.394.
- **Las fronteras de CAVA sí están mejor ubicadas** que las uniformes del
  mismo nº (F1 ±1: 0.22 frente a 0.13). El agrupamiento local no gana
  porque los segmentos son demasiado finos.
- **Siguiente palanca:** un nivel de capítulo (más grueso) sobre el mapa,
  pre-registrado y con su propio desarrollo. No se ajusta sobre blind40.

---

## EXP-033 · Nivel de capítulo sobre el mapa CAVA (pre-registro)
- **Fecha:** 2026-10-09 (antes de calcular las señales de desarrollo; job
  55212)
- **Motivación (EXP-032):**
  - los mapas son ~2.7× más finos que los capítulos del autor;
  - las fronteras de CAVA están mejor ubicadas que las uniformes (F1 ±1:
    0.22 frente a 0.13), pero el agrupamiento local pierde por exceso de
    segmentos.
- **Operador (`chapters`):** capítulos contiguos a partir de las fronteras
  del mapa del producto (perfil documentary, nivel default, con snap).
  1. Candidatas = cambios de etiqueta entre unidades contiguas.
  2. Fuerza de cada candidata = media, sobre las señales (voice, visual,
     transcript, vjudge), del rango percentil de la puntuación de frontera
     propia de la señal en ese índice. Son votos por señal, sin fusionar
     representaciones.
  3. Se conservan las N candidatas más fuertes, con N = round(duración / L).
     N sale de la duración, nunca del GT.
- **Desarrollo:** VidChapters raw_ext (50 videos, 22 min, 8.7 capítulos de
  media). CAVA no lo usó; no se solapa con blind40.
  - L se elige en {90, 120, 150, 180, 240, 300} s con el mayor M_local medio
    en desarrollo.
- **Confirmación:** blind40 (40).
  - Reutilizado: ya se evaluó en EXP-032, pero ese experimento no fijó
    ningún parámetro y L se fija solo en raw_ext. Se declara la
    reutilización.
- **Bases (mismo N por video):**
  - segmentación uniforme;
  - top-N de la puntuación de frontera de UNA señal (visual; transcript),
    con min_gap 2.
- **Criterios (SE pareado sobre 40 videos):**
  1. M_local(capítulos) − M_local(uniforme mismo N) > 2 SE;
  2. F1 ±3 (capítulos) − F1 ±3 (uniforme mismo N) > 2 SE;
  3. M_local(capítulos) − mejor M_local de señal sola top-N > 2 SE.
- **Si se valida:** nivel `chapters` en el mapa del producto y versión
  `full_chapters` por capítulo, con L fijo.

---

## EXP-034 · Filtro de habla aislado: voz frente a música y ambiente, y el narrador único (pre-registro)
- **Fecha:** 2026-10-09 (registrado antes de calcular ningún filtro sobre
  los conjuntos de abajo)
- **Motivación (EXP-026 / 029 / 030):** en documentales el cuello de botella
  de la identidad es el **filtro de habla**, no el embedding:
  - Whisper marca como habla el 87 % de BBC, incluida música y sonido
    animal; el detector de un hablante (spread, τ 0.976) da 0 de 11.
  - Con Parakeet ∩ Whisper da 10 de 11, pero sin GT no se puede validar, y
    son dos ASR (contra el pedido de un solo modelo).
  - En BBC no hay GT de habla. Este experimento **aísla el procesamiento de
    sonido** con conjuntos que sí tienen GT, y deja BBC como secundaria.
- **Conjuntos:**
  1. **AVASpeech-SMAD** (películas; etiquetas por frame de habla, de AVA-Speech,
     y de música, manuales; minutos 15–30 de cada video; audio del S3
     oficial de AVA). Unidades de 5 s. GT por unidad:
     - habla = etiqueta de habla cubre ≥ 50 % de la unidad;
     - sin habla se divide en *música* (música ≥ 50 %) y *otro*.
     - División: ids ordenados, posiciones pares = desarrollo, impares =
       confirmación.
  2. **Narrador sintético con GT exacto** (VoxConverse + MUSAN). Archivos con
     K_true = 1 (regla de EXP-028) y el mismo número con K_true ≥ 2 (sorteo,
     semilla 0). Tres condiciones por archivo:
     - limpio;
     - música de MUSAN de fondo a SNR 5 dB;
     - ruido/ambiente de MUSAN a SNR 5 dB.

     El fondo cubre todo el archivo; su nivel se fija respecto al RMS del
     habla RTTM. VoxConverse dev = desarrollo, test = confirmación; los
     archivos de MUSAN se dividen por sha1 del nombre (par = desarrollo,
     impar = confirmación).
  3. **AMI fresh3** (40 reuniones; solo confirmación): no regresión.
  4. **BBC 01–11:** solo secundarias, sin criterio.
- **Candidatos (filtro por unidad):**
  - **W** Whisper large-v3 exactamente como el pipeline (`vad_filter`,
    unidad cubierta ≥ 50 % por segmentos). Base.
  - **S** Silero VAD v5 (el ONNX que trae faster-whisper, opciones por
    defecto), unidad cubierta ≥ 50 %.
  - **I** inaSpeechSegmenter (CNN speech/music para TV; habla = male/female),
    unidad cubierta ≥ 50 %.
  - **A** AST AudioSet (`MIT/ast-finetuned-audioset-10-10-0.4593`, revisión
    f826b80d), P(Speech) ≥ θ, θ ∈ {0.1, …, 0.9}.
  - **S∩W, I∩W, A∩W:** el texto sigue saliendo de Whisper; el filtro solo
    descarta unidades.
  - Solo de referencia, no adoptable (dos ASR): **P** Parakeet (texto no
    vacío) y **P∩W**.
- **Selección en desarrollo (AVA dev, congelada antes de la confirmación):**
  el candidato adoptable con mayor exactitud balanceada media por video
  (recall de habla y especificidad), sujeto a recall ≥ recall(W) − 0.05.
  τ del detector de un hablante **no se toca** (0.976, EXP-029).
- **Criterios de confirmación (SE pareado):**
  1. **AVA conf:** FSR(W) − FSR(elegido) > 2 SE por video (FSR = fracción de
     unidades sin habla marcadas como habla), **y** recall(elegido) ≥
     recall(W) − 0.05.
  2. **Narrador sintético (VoxConverse test, K_true = 1, condiciones música y
     ruido):** tasa de "un hablante" detectado con el elegido − con W > 2 SE
     por mezcla.
  3. **Sin falsos narradores (VoxConverse test, K_true ≥ 2, las tres
     condiciones):** tasa de "un hablante" del elegido ≤ la de W + 0.05.
  4. **AMI fresh3 (no regresión):** ARI de identidades elegido − W > −0.02, y
     0 de 40 reuniones declaradas de un hablante.
- **Lectura pre-declarada:**
  - 1–4 se cumplen: el filtro elegido entra en el pipeline (todos los
    perfiles) y el perfil documentary vuelve a publicar los V# como
    "hablante".
  - 1 sí y 2 no: el filtro mejora pero el narrador sigue sin resolverse; el
    problema no es solo el VAD.
  - 1 no: ningún candidato separa voz de música mejor que Whisper.
- **Secundarias (sin criterio):** FSR solo en unidades de música y en
  *otro*; desglose por condición y SNR; P y P∩W como referencia; en BBC,
  fracción de habla, episodios de un hablante y K_eff; F1 por frame de I
  frente al benchmark publicado de inaSpeechSegmenter en AVASpeech-SMAD
  (control del código de evaluación); exportación de unidades BBC donde los
  filtros discrepan, para escucharlas.
- **Expectativa declarada:** S, I o A deberían bajar la falsa habla en música
  (W cubre tramos de música porque sus segmentos atraviesan los huecos).
  Que eso alcance para el narrador es la pregunta abierta: EXP-030 sugiere
  que sí, pero sin GT.

### Precisiones a EXP-034 (2026-10-09, antes de calcular ningún filtro sobre los conjuntos)
- En AVA, FSR y recall de un video se cuentan solo si tiene ≥ 5 unidades sin
  habla (FSR) o con habla (recall). La media es por video.
- En AMI, el filtro W es el gate del caché de identidades (`*.xvec.npz`, el
  mismo de EXP-028/029). Las x-vectors de todos los candidatos, W incluido,
  se recalculan sobre todas las unidades, para comparar en igualdad.
- **Control de alineación:** el repositorio de AVASpeech-SMAD publica las
  predicciones de inaSpeechSegmenter por video. El acuerdo por unidad entre
  nuestro I y el publicado comprueba que la ventana de audio (minutos 15–30)
  coincide con la de las etiquetas.
- **Prueba de humo:** antes del registro se pasó Silero sobre un solo video
  AVA (`_7oWZq_s_Sk`, split conf) para probar la lectura de etiquetas. No se
  eligió nada con eso.
- **Videos AVA ausentes del S3 de AVA v2.1:** se excluyen, y el número se
  reporta.
- **Entorno:** inaSpeechSegmenter corre en un entorno aparte (`inaseg`,
  TensorFlow 2.21, CPU), sin tocar `segloop`.

### Control de alineación de EXP-034 (2026-10-09, AVA dev)
El acuerdo por unidad entre nuestro I y las predicciones publicadas de
inaSpeechSegmenter es bajo: 0.735 de media, mínimo 0.25. El diagnóstico
descarta un problema de alineación:
- desfase óptimo de nuestro I frente al GT (frames de 0.1 s, ±10 s): **0.0 s
  en los 72 videos** de desarrollo;
- exactitud por unidad frente al GT: nuestro I 0.808, el publicado 0.722.

Las predicciones publicadas vienen de otra versión del modelo o de otra
configuración, no de otra ventana de audio. **La ventana minutos 15–30
coincide con las etiquetas.** El control queda cumplido por el desfase, no
por el acuerdo con lo publicado.

### Desarrollo EXP-034 (jobs 55305 + 55371 de caché; 55372 de evaluación; AVA dev, 72 videos)
**Elección congelada: A0.3&W** (Whisper ∩ AST con P(Speech) ≥ 0.3).

| candidato | exactitud balanceada | recall | FSR | FSR en música |
|---|---|---|---|---|
| W (base) | 0.592 | 0.931 | 0.747 | 0.754 |
| **A0.3&W (elegido)** | 0.746 | 0.892 | 0.399 | 0.335 |
| S&W | **0.837** | 0.816 | 0.143 | 0.099 |
| S | 0.830 | 0.849 | 0.188 | 0.131 |
| I&W | 0.811 | 0.746 | 0.124 | 0.072 |
| P&W (referencia) | 0.761 | 0.865 | 0.343 | 0.286 |

- **El piso de recall decide.** Recall(W) − 0.05 = 0.881. S, S&W, I e I&W
  tienen mejor exactitud balanceada pero quedan por debajo del piso. Se
  aplica la regla pre-registrada sin cambios.
- **Whisper marca como habla el 75 % de las unidades de música** de AVA. Es
  el fallo que motivó el experimento, ahora medido con GT.
- **Narrador sintético dev (descriptivo, no elige nada):** la detección de
  un hablante en archivos con K = 1 cae de 0.61 (limpio) a 0.16–0.19 con
  música o ruido a 5 dB, **con cualquier filtro** (W, A0.3&W, P, P&W). Sin
  falsos narradores en K ≥ 2.
  - Lectura provisional: a 5 dB el fondo dispersa las x-vectors del propio
    narrador. El problema no sería solo qué unidades entran, sino cómo
    suenan.
- **Antes de la confirmación:** S&W e I&W se agregan a la confirmación como
  **secundarias sin criterio** (mismas métricas), porque separan voz de
  música mucho mejor y el piso de recall las excluyó. No cambian ningún
  criterio ni la elección.

### Resultado EXP-034 (confirmación)

| criterio | resultado | ¿cumple? |
|---|---|---|
| 1. AVA conf (76): FSR(W) − FSR(A0.3&W) | +0.323 ± 0.019, **z 16.9**; recall 0.880 frente a piso 0.874 | **sí** |
| 2. Narrador sintético, K = 1, música y ruido (50): un hablante, elegido − W | 0.000 ± 0.000 | **no** |
| 3. Falsos narradores, K ≥ 2 (75) | 0.013 frente a 0.013 | sí |
| 4. AMI fresh3: ARI elegido − W | +0.040 ± 0.030; 0 de 40 de un hablante | sí |

**No validado.** Aplica la lectura pre-declarada "1 sí y 2 no": el filtro
separa mucho mejor la voz de la música, pero el narrador sintético sigue sin
resolverse.

**AVA conf** (secundarias):

| filtro | recall | FSR | FSR en música | exactitud balanceada |
|---|---|---|---|---|
| W | 0.924 | 0.734 | 0.715 | 0.595 |
| A0.3&W (elegido) | 0.880 | 0.411 | 0.327 | 0.735 |
| P&W (ref.) | 0.843 | 0.356 | 0.274 | 0.744 |
| S&W (sec.) | 0.809 | 0.162 | 0.108 | **0.824** |
| I&W (sec.) | 0.726 | **0.126** | **0.075** | 0.800 |

**Narrador sintético conf** (un hablante detectado en K = 1):

| filtro | limpio | música 5 dB | ruido 5 dB |
|---|---|---|---|
| W | 0.56 | 0.04 | 0.20 |
| A0.3&W | 0.56 | 0.04 | 0.20 |
| S&W | 0.64 | 0.08 | 0.20 |
| I&W | 0.64 | 0.24 | 0.24 |

**Lectura honesta del criterio 2.** El diseño sintético no le dejaba margen
al filtro:
- las mezclas tienen un 92 % de unidades con habla GT;
- el fondo suena debajo de TODA el habla a 5 dB.

Lo que midió es la **contaminación de las x-vectors por el fondo**, no la
selección de unidades. Es un hallazgo en sí: con música constante a 5 dB,
el detector spread (τ 0.976) casi nunca reconoce a un solo hablante, sea
cual sea el filtro. No se rescata el criterio: queda no cumplido.

**BBC (secundaria, sin GT):**

| | W | A0.3&W | P&W | S&W | I&W |
|---|---|---|---|---|---|
| episodios de un hablante | 0 | 7 | 10 | **11** | **11** |
| fracción de habla | 0.87 | 0.62 | 0.62 | 0.50 | 0.52 |

En el documental real, quitar las unidades de solo música sí basta para que
aparezca el narrador único. Ahí la música llena los huecos más que sonar bajo
la voz, al revés que en el sintético. Sigue sin GT: son 110 clips para
escuchar en `data/gatebench/audit/bbc_XX/` (con `anotar.csv`).

**AMI (secundaria):** ARI W 0.731 (reproduce el 0.726 de los mapas de
producto) → A0.3&W 0.771, S&W 0.782, I&W 0.785. Ningún filtro declara
reuniones de un hablante.

**Decisión:**
- El pipeline no cambia. A0.3&W no se adopta, porque EXP-034 no se valida.
- Pendiente de pre-registrar (EXP-035):
  1. un narrador sintético con la estructura de un documental (habla con
     fondo bajo + huecos de solo música);
  2. GT humano de las 110 unidades BBC exportadas.

  Con eso se decide S&W / I&W frente a W para el perfil documentary.

---

## EXP-035 · ¿Silero o ina + Whisper resuelven el narrador? Sintético con estructura de documental + GT humano en BBC (pre-registro)
- **Fecha:** 2026-10-10 (registrado antes de generar las mezclas y de
  muestrear las unidades BBC)
- **Motivación (EXP-034):**
  - S&W e I&W separan voz de música mucho mejor que W (FSR en AVA 0.16 y
    0.13 frente a 0.73) y dan 11 de 11 narradores en BBC, pero sin GT.
  - El sintético de EXP-034 tenía fondo bajo toda la voz y un 92 % de habla:
    no le dejaba nada que descartar al filtro.
- **Candidatos (congelados, sin ajuste):**
  - W (base);
  - A0.3&W (elegido en EXP-034);
  - **S&W** y **I&W** (los dos de interés).

  τ del detector de un hablante: 0.976 (EXP-029), sin cambios.

### EXP-035a · Narrador sintético con estructura de documental
- **Fuentes:** los mismos archivos de VoxConverse de EXP-034 (K = 1 y K ≥ 2;
  dev = dev, test = confirmación) y la misma división de MUSAN.
- **Generador:**
  1. El habla de la fuente se corta en tramos por los silencios RTTM de
     ≥ 0.5 s, conservando el audio original.
  2. Debajo de la voz, fondo continuo a **SNR 15 dB** (música "agachada").
  3. Tras cada tramo, con probabilidad 0.6, un **hueco de solo fondo** de
     4–20 s (uniforme) a **0 dB** respecto al RMS del habla (la música sube
     cuando nadie habla).
  4. Condiciones: música, ruido/ambiente. Semilla 0. GT de habla y de
     hablante trasladado de la RTTM.
  - Dev solo se usa para comprobar el generador (fracción de habla GT entre
    0.45 y 0.70). No se elige nada.
- **Criterios (confirmación, VoxConverse test):**
  1. K = 1, música y ruido: tasa de un hablante, G − W > 2 SE pareado,
     evaluado por separado para G = S&W y G = I&W.
  2. K ≥ 2: tasa de falsos narradores de G ≤ la de W + 0.05.

### EXP-035b · GT humano en BBC
- **Muestra estratificada (semilla 0)** por episodio, según el patrón de los
  filtros en EXP-034 (sobre todas las unidades):
  - c0 W no;
  - c1 W sí, S&W no, I&W no;
  - c2 W sí, S&W sí, I&W no;
  - c3 W sí, S&W no, I&W sí;
  - c4 W sí, S&W sí, I&W sí.

  Por episodio se toman 2 / 5 / 3 / 3 / 3 unidades (todas si hay menos), unas
  176 en total. Peso de cada unidad = tamaño del estrato / muestreadas.
- **Anotación ciega:** página con un clip por unidad, en orden aleatorio, sin
  estrato ni filtro visibles. Etiquetas:
  - narrador;
  - otra voz (persona distinta del narrador);
  - voz con música (el narrador sobre la música);
  - música sin voz;
  - animal / ambiente;
  - silencio;
  - no sé.

  Habla = narrador, otra voz, voz con música. Las unidades "no sé" se
  excluyen y se reportan.
- **Métricas ponderadas** (sobre las 11 × ~590 unidades), con SE por
  bootstrap de episodios (2000 remuestreos, pareado entre filtros):
  - FSR(G) = P(G marca habla | sin habla);
  - recall(G) = P(G marca habla | habla).
- **Criterios**, para G = S&W y G = I&W por separado:
  1. FSR(W) − FSR(G) > 2 SE;
  2. recall(G) ≥ 0.80. El filtro solo decide qué unidades reciben identidad
     de hablante; el texto de Whisper sigue entrando en todas.
  3. **Narrador único real:** "otra voz" < 5 % del habla ponderada. Si no se
     cumple, BBC tiene conversaciones y "un hablante" no es la verdad del
     dominio.
- **Adopción en el perfil documentary:** G pasa 035b-1, 035b-2 y 035b-3 **y**
  035a-2 (sin falsos narradores). Si pasan los dos, se adopta el de menor FSR
  en 035b.
  - Con la adopción, los V# del perfil documentary vuelven a publicarse como
    "hablante".
  - 035a-1 se reporta como generalidad. Si falla, se declara que la ganancia
    depende de la estructura de huecos del documental.

### Corrección del generador de EXP-035a (verificación de dev, antes de calcular ningún filtro)
Con tramos cortados por silencios ≥ 0.5 s, la fracción de habla GT en dev
fue 0.770, fuera de la ventana pre-registrada (0.45–0.70).
- Causa: muchos archivos de VoxConverse tienen pocos silencios largos
  (mediana de 4 tramos por archivo en dev), así que había pocos huecos.
- Corrección: cualquier frontera de segmento RTTM puede llevar un hueco
  (min_sil = 0; solo se funden segmentos solapados). Se eligió por la
  fracción simulada, sin mirar ningún filtro.
- Fracción de habla tras la corrección: ver la línea de abajo. Las mezclas
  se regeneraron desde cero.
- Tras la corrección: dev 0.661, conf 0.582 (dentro de la ventana).

### EXP-035b · muestra y página de anotación (2026-10-10)
- **Muestra:** 176 clips (c0 22, c1 55, c2 33, c3 33, c4 33). La clave
  privada (`sample.json`: episodio, unidad, estrato, peso) no se publica.
- **Página de anotación ciega:** https://claude.ai/artifact/MgZL67zwzopXg6DXGJdxSo
  - un clip por vista, en orden aleatorio, con nombres opacos;
  - etiquetas en la colección `labels` (un documento por anotador y clip);
  - fuente de la página en `scripts/exp035b_annotate_page.html`.
- **Con más de un anotador:** mayoría por clip; los empates y "no sé" se
  excluyen y se reportan.

### Resultado EXP-035a (caché job 55567, ina job 55568; docmix conf: 46 mezclas K = 1, 54 K ≥ 2)

| criterio | S&W | I&W |
|---|---|---|
| 1. un hablante en K = 1, G − W | +0.413 ± 0.073, **z 5.6** ✅ | +0.413 ± 0.073, **z 5.6** ✅ |
| 2. falsos narradores en K ≥ 2 (límite W + 0.05 = 0.050) | 0.056 (3 de 54) ❌ | 0.056 (3 de 54) ❌ |

| filtro | un hablante K = 1 (música / ruido) | falsos (música / ruido) | \|K_eff − 1\| (música / ruido) | FSR | recall |
|---|---|---|---|---|---|
| W | 0.09 / 0.17 | 0.00 / 0.00 | 1.86 / 1.75 | 0.721 | 0.968 |
| A0.3&W | 0.32 / 0.21 | 0.07 / 0.04 | 1.18 / 1.29 | 0.279 | 0.964 |
| S&W | 0.55 / 0.54 | 0.07 / 0.04 | 0.55 / 0.46 | 0.068 | 0.960 |
| I&W | 0.55 / 0.54 | 0.07 / 0.04 | 0.45 / 0.50 | **0.009** | 0.932 |

**Criterio 2 no cumplido, por una mezcla** (3 de 54 frente a un límite de
2.7). Por la regla pre-registrada, **la adopción queda bloqueada** sea cual
sea el resultado de 035b.

Lectura:
- Con la estructura de documental (huecos de solo fondo), los filtros S&W e
  I&W sí resuelven al narrador: la detección pasa de 0.09–0.17 a 0.54–0.55,
  y el error de K baja de ~1.8 a ~0.5. El fallo de EXP-034 era del diseño
  sintético, no del filtro.
- **Los falsos narradores son archivos dominados por una voz:**
  - gylzn: 83 % / 17 %, en música y en ruido;
  - mjmgr: 86 %, con la segunda voz en 5.5 %, apenas sobre el umbral K ≥ 2.

  W no los marca porque, con la música dentro, nada parece un solo hablante.
  Al limpiar la entrada, el detector spread (τ 0.976, fijado con VAD oráculo
  en EXP-029) queda en el borde con voces muy dominantes.
- No se ajusta τ aquí. Es candidato a un experimento propio, con su
  desarrollo.

---

## Plan del 2026-10-12: cerrar EXP-033 y preparar el entrenamiento de la política de clips

Orden acordado: EXP-033 (capítulos) → EXP-036 (umbral del narrador) →
EXP-037 (highlights por importancia con regla fija) → EXP-038 (política
aprendida). Los tres pre-registros de abajo se escriben y se commitean
antes de calcular cualquiera de sus números.

Nota de numeración: el reporte semanal del 9 oct llamaba "EXP-034" a los
highlights por importancia. Ese número lo tomó el filtro de habla; los
highlights pasan a EXP-037.

### Precisión de EXP-033 (antes de correr su evaluación)
- `topicagg/chapters.py` (commit 8f7de03, anterior al job 55212) conserva
  round(D / L) − 1 fronteras, es decir, **round(D / L) capítulos**. La base
  uniforme usa el mismo número. Es lo que el pre-registro llama "N", contado
  en capítulos.

---

## EXP-036 · Umbral del detector de un hablante con habla filtrada (pre-registro)
- **Fecha:** 2026-10-12 (antes de calcular el detector con cualquier τ
  nuevo)
- **Motivación (EXP-035a):** con S&W o I&W el narrador se detecta (+0.41,
  z 5.6), pero hay 3 de 54 falsos narradores (límite 2.7). Son archivos
  dominados por una voz (83 / 17 %, 86 %). τ = 0.976 se fijó en EXP-029 con
  VAD oráculo sobre conversación; la entrada filtrada cambia la distribución
  de la estadística.
- **Lo único que cambia:** τ del detector spread (mediana del coseno de cada
  unidad con la x-vector media) **cuando la entrada es S&W o I&W** (perfil
  documentary). El perfil meeting conserva τ = 0.976 y la puerta W.
- **Desarrollo:** docmix dev (VoxConverse dev; música y ruido; las mismas
  mezclas de EXP-035a).
  - Rejilla τ ∈ {0.960, 0.961, …, 0.990}.
  - Se agrupan S&W e I&W (un solo τ para la entrada filtrada).
  - Elegido = el τ con mayor (tasa de un hablante en K = 1 − tasa de falsos
    en K ≥ 2), con la restricción falsos ≤ 0.02 en dev. Empate: el τ mayor.
- **Confirmación:** docmix conf (VoxConverse test). Se reutiliza: es el
  conjunto de EXP-035a, que no fijó nada. Se declara.
- **Criterios**, para G = S&W y G = I&W por separado, con G a τ nuevo frente
  al producto actual (W, τ 0.976):
  1. K = 1: tasa de un hablante G − W > 2 SE pareado;
  2. K ≥ 2: falsos narradores de G ≤ los de W + 0.05 (el mismo criterio que
     bloqueó 035a).
  3. No regresión fuera del documental: en AMI (40 reuniones, unidades de
     10 s) con G a τ nuevo, como mucho 1 de 40 reuniones marcada como de un
     hablante.
- **Adopción en el perfil documentary:** G pasa 036-1, 036-2 y 036-3 **y**
  035b-1, 035b-2 y 035b-3 (GT humano, pendiente). 036-2 sustituye a 035a-2
  solo para el τ nuevo; el bloqueo de 035a sigue en pie para τ 0.976.

---

## EXP-037 · Highlights por importancia con una regla fija sobre el mapa (pre-registro)
- **Fecha:** 2026-10-12 (antes de correr CAVA sobre SumMe y de calcular
  cualquier regla nueva sobre TVSum)
- **Motivación (EXP-031):** highlights10pct elige los tópicos más largos y
  queda como el azar (0.057 frente a 0.041). Los clips equiespaciados ganan
  (0.322): TVSum premia la cobertura.
- **Presupuesto:** m = max(1, ⌊0.10 · D / 5⌋) unidades de 5 s, alineadas a
  la rejilla del mapa (nivel default, sin tópicos no_topic, como el
  producto).
- **Reglas candidatas** (solo salidas del pipeline, sin GT):
  - **H0, producto:** highlights10pct tal como está en `clips.jsonl`
    (referencia).
  - Para H1–H3, las m unidades se reparten entre tópicos en proporción a su
    duración (resto mayor; empates por inicio más temprano). El cupo de un
    tópico tiene como tope la longitud de su tramo más largo; lo que sobra
    pasa al siguiente en el orden del resto. Cada tópico recibe una ventana
    contigua de su cupo dentro de su tramo más largo, centrada en:
    - **H1, cobertura:** el centro del tramo;
    - **H2, representativa:** la unidad del tramo con mayor coseno visual
      (SigLIP) a la media visual del tópico;
    - **H3, saliente:** la unidad del tramo con mayor distintividad visual,
      1 − coseno a la media visual del video.
- **Recompensa:** la de EXP-031 (z por video de la importancia media por
  segundo, media sobre los segundos elegidos). En SumMe, la importancia por
  fotograma es `gt_score` (fracción de usuarios que lo eligieron).
- **Desarrollo:** TVSum (50; ya visto en EXP-031). Se elige la regla H* de
  H1–H3 con mayor recompensa media.
- **Confirmación:** SumMe (25 videos de 1–6 min, nunca usados por CAVA).
  - CAVA se corre con el stack final (perfil film) en
    `data/cava_runs_v1_summe/`.
  - Cooking está en `videos_corrupt/` de SegLoop (ffprobe da 85.8 s). Se
    intenta; si el pipeline falla, se excluye y se declara.
- **Criterios (SE pareado sobre los videos de SumMe):**
  1. R(H*) − R(uniforme, mismas duraciones de clip) > 2 SE;
  2. R(H*) − R(H0) > 2 SE;
  3. R(H*) − R(al azar, 1000 sorteos, mismas duraciones) > 2 SE.
- **Adopción:** si pasan 1 y 2, H* sustituye la regla de highlights10pct y
  recap60.
- **Expectativa declarada:** H1 se parece a lo uniforme por construcción;
  superar lo uniforme por 2 SE con 25 videos es improbable. El resultado fija
  la regla fija contra la que se mide EXP-038.
- **Secundarias:** F1 estándar de SumMe al 15 % (máximo sobre usuarios), solo
  informativo.

---

## EXP-038 · Política de clips aprendida por refuerzo (bandido contextual) (pre-registro)
- **Fecha:** 2026-10-12 (antes de escribir el código de entrenamiento)
- **Qué es y qué no es:** una decisión de un paso por video (qué unidades
  entran en los highlights bajo el presupuesto), aprendida por gradiente de
  política con la recompensa de importancia. Es un bandido contextual, no
  RL secuencial. Con 50 videos de entrenamiento no hay datos para más.
- **Estado por unidad de 5 s** (solo salidas del pipeline y del mapa; sin
  GT):
  - posición relativa t / D;
  - fracción de la duración del video que ocupa su tópico;
  - el tópico tiene retornos;
  - primera unidad del tramo;
  - acuerdo y soporte del tópico por señal (voice, visual, transcript,
    vjudge; 0 si la señal se abstuvo);
  - distintividad visual (1 − coseno a la media visual del video);
  - cambio visual local (puntuación de frontera visual en la unidad);
  - hay transcripción en la unidad;
  - banderas needs_review y no_topic.

  Rasgos en z-score por video.
- **Política:** puntuación lineal w · f. Al entrenar se muestrean m
  unidades sin reemplazo (Plackett–Luce, m como en EXP-037). Al evaluar se
  toman las m de mayor puntuación.
- **Entrenamiento (hiperparámetros fijos, sin búsqueda):**
  - REINFORCE con línea base de la media de 16 muestras por video;
  - Adam, lr 0.05, 300 épocas, L2 1e-3;
  - semilla 0.
- **Recompensa:** la de EXP-031 / EXP-037 (z de importancia sobre los
  segundos elegidos). Ningún término de estructura: TVSum y SumMe ya premian
  la cobertura, así que se mide si la política aprende algo más que cubrir.
- **Evaluación:**
  - **Interna:** TVSum dejando una categoría fuera (10 pliegues de 5
    videos: entrena con 45, prueba con 5).
  - **Externa:** entrena con los 50 de TVSum y prueba en SumMe.
- **Bases (mismas m unidades por video):**
  - uniforme (m unidades equiespaciadas en la rejilla);
  - al azar (1000 sorteos);
  - H* de EXP-037.
- **Criterios (SE pareado por video):**
  1. SumMe: R(política) − R(uniforme) > 2 SE;
  2. SumMe: R(política) − R(H*) > 2 SE;
  3. TVSum dejando una categoría fuera: R(política) − R(uniforme) > 2 SE.
- **Validación:** 1, 2 y 3. Si solo pasa 3, se declara que lo aprendido no
  transfiere de dominio.
- **Control de "solo cubrir":**
  - dispersión temporal de lo elegido (desviación de los huecos entre
    unidades frente a lo uniforme);
  - pesos aprendidos por rasgo, publicados.

  Si la política gana pero copia lo uniforme (rasgo de posición dominante,
  huecos casi constantes), se reporta como tal.

### Resultado EXP-036 (`scripts/exp036_tau.py`, CPU sobre las cachés de EXP-035a; docmix dev 124 mezclas (59 K = 1, 65 K ≥ 2), conf 46 K = 1 / 54 K ≥ 2, AMI 40)

**Desarrollo** (S&W e I&W agrupados, música y ruido):

| τ | un hablante K = 1 | falsos K ≥ 2 |
|---|---|---|
| 0.960 | 0.763 | 0.285 |
| 0.970 | 0.627 | 0.092 |
| 0.974 | 0.559 | 0.062 |
| 0.976 (EXP-029) | 0.398 | 0.046 |
| 0.980 | 0.280 | 0.031 |
| **0.982 (elegido)** | 0.195 | 0.015 |
| 0.985 | 0.076 | 0.000 |

**Confirmación (τ 0.982):**

| criterio | S&W | I&W |
|---|---|---|
| 1. un hablante en K = 1, G − W | 0.130 frente a 0.130, +0.000 ± 0.062, z 0.0 ❌ | 0.196 frente a 0.130, +0.065 ± 0.072, z 0.90 ❌ |
| 2. falsos en K ≥ 2 (límite 0.05) | 0.019 (mjmgr, música) ✅ | 0.019 (mjmgr, música) ✅ |
| 3. AMI, reuniones marcadas como un hablante (≤ 1) | 0 de 40 ✅ | 0 de 40 ✅ |

**No validado.** Subir τ elimina los falsos narradores, pero también la
detección del narrador real (0.55 → 0.13–0.20). En dev no hay ningún τ con
detección alta y falsos bajos a la vez.

La estadística spread (mediana del coseno a la media) **no separa** "un solo
hablante" de "una voz que domina el 85 % con otra breve": en esos archivos
casi todas las unidades son de la voz dominante, así que la mediana es igual
a la de un monólogo. Es un límite del detector, no del umbral.

Consecuencias:
- El perfil documentary sigue publicando las voces como grupos acústicos.
  La adopción de S&W / I&W queda bloqueada (035a-2 con τ 0.976, 036-1 con
  τ 0.982).
- Siguiente candidato, sin pre-registrar aún: un detector que pregunte
  "¿hay una segunda voz con soporte propio?" (p. ej., BIC de K = 2 frente a
  K = 1 sobre las unidades filtradas) en lugar de "¿la voz típica es
  homogénea?". Antes de eso hace falta el GT humano de BBC (035b) para saber
  si, en el dominio real, "otra voz" existe.

### Resultado EXP-037 · desarrollo (TVSum, 50 videos; `scripts/exp037_highlights.py --mode dev`)

| regla | recompensa media | uniforme (mismas duraciones) | al azar |
|---|---|---|---|
| H0 producto | 0.058 | — | — |
| H1 cobertura | 0.063 | 0.038 | 0.017 |
| H2 representativa | 0.057 | 0.038 | 0.018 |
| **H3 saliente (H\*)** | **0.066** | 0.038 | 0.020 |

H\* = **H3**, congelado antes de evaluar SumMe. En desarrollo, H3 − uniforme
= +0.029 ± 0.100 (z 0.29) y H3 − H0 = +0.009 ± 0.117 (z 0.07). Las cuatro
reglas están en el ruido.

### ⚠️ Corrección de la lectura de EXP-031 (hallada al verificar la base uniforme de EXP-037)
La base "uniforme" de EXP-031 (0.322) **no mide cobertura**:
- highlights10pct es **un solo clip** en los 50 videos de TVSum (el tópico
  más largo, recortado al 10 %);
- `uniform_spans` con un solo clip lo coloca **en el centro del video**.

La importancia de TVSum tiene un sesgo de posición fuerte. z media por
decil de duración, de 0–10 % a 90–100 %:

`−0.32 −0.22 −0.01 +0.25 +0.24 +0.31 +0.18 −0.01 −0.02 −0.38`

Con el mismo presupuesto repartido en m unidades equiespaciadas, lo uniforme
cae a −0.04, y con las duraciones de H1–H3 da 0.038.

Lectura corregida:
- **"Un clip en el centro del video" = 0.322** es la base dura de TVSum.
  Explota el sesgo de posición de los anotadores, no la cobertura.
- Lo que el reporte del 9 oct dice sobre "TVSum premia la cobertura" es
  incorrecto. Se corrige en el próximo reporte.
- Para EXP-038 esto es central: un rasgo de posición basta para aprender
  "centro". El control de "solo cubrir" pre-registrado debe leerse también
  como control de "solo centro": si el peso de posición domina, se reporta.
- El resultado numérico de EXP-031 no cambia (no validado). Cambia la
  explicación.

### Enmienda de EXP-038 (2026-10-12, antes de escribir su código; motivada por la corrección de EXP-031)
- **Base nueva, "centro":** m unidades contiguas centradas en la mitad del
  video. Es la base dura real de TVSum.
- **Criterio nuevo, 1b:** SumMe, R(política) − R(centro) > 2 SE.
- **Criterio nuevo, 3b:** TVSum dejando una categoría fuera,
  R(política) − R(centro) > 2 SE.
- **Validación:** 1, 1b, 2, 3 y 3b. La enmienda solo endurece; no se quita
  ningún criterio.
- Los rasgos no se tocan. La posición sigue entrando como t / D lineal, como
  se registró: una política lineal no puede expresar "centro" con ese rasgo.
  No se añade un rasgo cuadrático, porque eso sería ajustar a lo que ya se
  vio en TVSum.

### Resultado EXP-033 (dev raw_ext job 55212, 50 videos; confirmación blind40, 40 videos; `scripts/exp033_chapters.py`)

**Desarrollo (raw_ext), M_local medio por L:**

| L (s) | 90 | 120 | 150 | 180 | 240 | 300 |
|---|---|---|---|---|---|---|
| capítulos | **0.382** | 0.335 | 0.314 | 0.284 | 0.241 | 0.212 |
| uniforme, mismo N | 0.364 | 0.389 | 0.370 | 0.359 | 0.329 | 0.261 |

- L = 90 s, en el **borde inferior** de la rejilla pre-registrada. No se
  extiende la rejilla.
- Señal de alarma ya en dev: lo uniforme con L = 120 (0.389) supera a los
  capítulos con cualquier L.

**Confirmación (blind40, L = 90 congelado; 8.8 capítulos GT de media):**

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. M_local capítulos − uniforme mismo N | +0.016 ± 0.027 | 0.59 | **no** |
| 2. F1 ±3 capítulos − uniforme mismo N | +0.087 ± 0.034 | 2.57 | sí |
| 3. M_local capítulos − mejor señal sola por video | −0.038 ± 0.030 | −1.23 | **no** |

Medias: capítulos M_local 0.381 / F1 ±3 0.363; uniforme 0.365 / 0.276;
top-N visual 0.325; top-N transcript 0.328; máximo por video de las dos
0.418.

**No validado.** Lectura:
- **Las fronteras que elige el operador sí están mejor ubicadas** que las
  uniformes con el mismo número (F1 ±3 +0.087, z 2.57). Es lo mismo que vio
  EXP-032 a nivel de tópico.
- **El agrupamiento local no mejora** frente a lo uniforme. Con L = 90 se
  hacen ~14 capítulos frente a 8.8 del autor: la granularidad sigue
  mandando.
- **Criterio 3, tal como está implementado** (commit 8f7de03, anterior a
  los datos), compara con el **máximo por video** de visual y transcript.
  Es un oráculo que elige la señal a posteriori, más duro que "la mejor
  señal sola" fija.
  - Exploratorio, no cuenta: frente a cada señal fija, capítulos − visual
    +0.056 ± 0.034 (z 1.63) y − transcript +0.053 ± 0.033 (z 1.62).
  - Tampoco pasaría.
- El mapa CAVA no tiene un nivel de capítulo validado. **No se adopta**
  `chapters` ni la versión `full_chapters` por capítulo.
- Lo que queda abierto es elegir el número de capítulos por video. Es la
  palanca que domina desde EXP-032, y ninguna regla interna la resuelve
  (EXP-021). Es candidata a ser una decisión de la política aprendida, no
  una regla fija.

### Resultado EXP-038 · TVSum dejando una categoría fuera (10 pliegues, 50 videos; `scripts/exp038_policy.py --mode loco`)

| política / base | recompensa media en los videos de prueba |
|---|---|
| **política aprendida** | **0.014** |
| centro (m unidades contiguas) | **0.300** |
| H3 (EXP-037) | 0.066 |
| H0 producto | 0.058 |
| al azar | −0.001 |
| uniforme en la rejilla | −0.042 |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 3. política − uniforme | +0.056 ± 0.111 | 0.50 | **no** |
| 3b. política − centro | −0.286 ± 0.119 | −2.40 | **no** (el centro es mejor) |
| secundaria: política − H3 | −0.052 ± 0.119 | −0.44 | — |

**Criterios 3 y 3b no cumplidos.** EXP-038 queda no validado sea cual sea
el resultado de SumMe (criterios 1, 1b y 2), que se corre igual cuando
termine el job de SumMe.

Lectura:
- **Aprende en entrenamiento y no generaliza.** La recompensa muestreada en
  los videos de entrenamiento sube de −0.04 a ~0.29 por pliegue. En la
  categoría que queda fuera, la política queda al nivel del azar (0.014
  frente a −0.001).
- **Los pesos no son estables entre pliegues.** El signo cambia en 11 de 17
  rasgos (p. ej., acuerdo transcript −1.6 a +2.6, retornos −3.6 a +0.8).
  - Estables en todos los pliegues: fracción del tópico (+1.3 a +2.7),
    cambio visual local (−0.5 a −3.2), habla en la unidad (−0.2 a −2.8),
    acuerdo vjudge (−0.4 a −3.3), soporte transcript (+0.1 a +4.0).
  - Lo estable dice "tópicos grandes y tramos visualmente quietos": la misma
    preferencia de H0.
- **Control de "solo centro / solo cubrir":** la posición lineal tiene peso
  medio +1.05 (prefiere el final, no el centro). La dispersión de los huecos
  es 1.09 frente a 0.29 de lo uniforme: la política **concentra** sus
  unidades, no cubre. No copia ninguna de las dos bases triviales; tampoco
  las supera.
- **Con 45 videos de entrenamiento y la importancia de TVSum como
  recompensa, una política lineal sobre el estado del mapa no aprende nada
  que transfiera entre categorías.** La recompensa está dominada por un
  sesgo de posición (centro, +0.30) que el estado registrado no puede
  expresar, y el resto es específico de categoría.
- **Implicaciones para la línea RL:**
  1. La recompensa de TVSum no sirve sola como señal de entrenamiento. Hace
     falta una recompensa con más videos o menos sesgo de posición, o
     normalizar la importancia por posición antes de usarla (pre-registrar).
  2. El entorno (`clips.jsonl` + `rewards.jsonl` + este entrenador) funciona
     de punta a punta y queda como banco reproducible.
  3. Antes de ampliar la política (más rasgos, no lineal), se necesita más
     dato etiquetado. Ampliar el modelo con 45 videos solo ajustaría ruido.

---

## EXP-039 · Detector de "¿hay una segunda voz con soporte propio?" para el narrador con habla filtrada (pre-registro)
- **Fecha:** 2026-10-12 (registrado antes de generar el conjunto nuevo y de
  calcular cualquiera de los detectores de abajo sobre cualquier conjunto)
- **Motivación (EXP-035a / 036):**
  - con S&W o I&W el narrador se detecta (0.13 → 0.55 en K = 1), pero el
    detector spread da falsos narradores en archivos con una voz dominante;
  - subir τ no sirve (EXP-036). La causa es estructural: **la mediana del
    coseno a la media ignora por construcción cualquier voz con < 50 % de
    las unidades**. Una voz del 17 % no mueve la mediana.
- **Literatura consultada (2026-10-12):**
  - estimación del número de hablantes por *eigengap* sobre el grafo de
    afinidad, sin ajuste en desarrollo (NME-SC, Park et al., IEEE SPL 2019,
    arXiv 2003.02405);
  - VBx (BUT, VoxConverse) estima el número de hablantes por ARD y acierta
    más que AHC;
  - modelos de segmentación con conteo local (pyannote segmentation-3.0,
    powerset, ventanas de 10 s). No está instalado y es un modelo con
    acceso restringido: queda fuera de este experimento y es el siguiente
    candidato si este falla.
- **Lo único que cambia:** el detector de un hablante **cuando la entrada es
  S&W o I&W** (perfil documentary). Embedding (WavLM-sv, unidades de 5 s),
  filtros y perfil meeting sin cambios.
- **Candidatos** (sobre las x-vectors de las unidades que pasan el filtro;
  ≥ 10 unidades, si no "varios", igual que EXP-029):
  - **D0 spread:** mediana del coseno a la media ≥ τ; τ ∈ {0.960, …, 0.990}
    (paso 0.001). Es el detector actual con τ libre.
  - **D1 q15:** cuantil 0.15 del coseno a la media ≥ τ; τ ∈ {0.500, …,
    0.990} (paso 0.005). Una voz con ≥ 15 % de las unidades mueve este
    cuantil.
  - **D2 minor:** centro robusto = media normalizada de las unidades con
    coseno a la media ≥ su mediana. Fracción de unidades con coseno al
    centro robusto < θ. Un hablante si esa fracción ≤ 0.10 (fijo).
    θ ∈ {0.500, …, 0.990} (paso 0.005).
  - **D3 bic12:** el de EXP-029 (BIC GMM K = 1 − K = 2 sobre PCA-16, por
    unidad). Un hablante si < τ; τ en 200 valores equiespaciados entre el
    mínimo y el máximo de dev.
  - **D4 nme:** número de hablantes por eigengap normalizado (NME, Park
    2019). Afinidad coseno, binarización de los p vecinos por fila,
    simetrizada, laplaciano no normalizado, K ≤ 8; p ∈ {2, …, max(2, N/4)}
    elegido por la regla NME (mínimo de p / g_p). Un hablante si K̂ = 1. Sin
    parámetro ajustable.
- **Conjunto nuevo: domix (voces dominantes).** Archivos de VoxConverse con
  K_true ≥ 2, voz principal ≥ 70 % de las unidades con hablante, **no
  usados** en docmix. Son 40 por split (dev y test), y se usan todos. Mismo
  generador de documental de EXP-035a (fondo a 15 dB, huecos de 4–20 s a
  0 dB, p = 0.6, música y ruido, división de MUSAN de EXP-034, semilla 0):
  80 mezclas por split. Cachés con el mismo código de EXP-034 (Whisper,
  Silero, AST, Parakeet, xvec) e ina.
- **Desarrollo** (S&W e I&W agrupados, música y ruido; un solo umbral):
  - docmix dev (K = 1 y K ≥ 2) + domix dev (K ≥ 2).
  - Por candidato, el umbral con mayor (tasa de un hablante en K = 1 − tasa
    de falsos en K ≥ 2, docmix y domix juntos), con falsos ≤ 0.02. Si
    ningún umbral cumple, el de menos falsos (empate: más detección).
    Empate en el objetivo: el umbral más estricto.
  - Elegido = el candidato con mayor objetivo entre los que cumplen
    falsos ≤ 0.02. Empate: el primero en el orden D0…D4.
- **Confirmación** (para G = S&W y G = I&W por separado, con el detector y el
  umbral congelados, frente al producto actual: W con spread τ 0.976):
  1. docmix conf, K = 1: tasa de un hablante G − W > 2 SE pareado;
  2. docmix conf, K ≥ 2: falsos de G ≤ los de W + 0.05;
  3. **domix conf (nuevo, 80 mezclas): falsos de G ≤ los de W + 0.05;**
  4. AMI fresh3 (40 reuniones) con G: como mucho 1 de 40 marcada como de un
     hablante.
- **Reutilización declarada:** docmix conf ya se miró en EXP-035a y 036 (es
  la tercera vez). Por eso la condición nueva (3) se mide sobre domix conf,
  que es nuevo y contiene justo el modo de fallo.
- **Lectura pre-declarada:**
  - 1–4 se cumplen: el detector queda listo para el perfil documentary,
    pero la adopción **sigue requiriendo 035b** (GT humano de BBC);
  - 1 sí y 3 no: con x-vectors de 5 s no se separa una voz dominante de un
    monólogo; siguiente paso, segmentación con conteo local (pyannote);
  - 1 no: ningún detector conserva la detección del narrador.
- **Límite conocido:** una segunda voz del ~5 % (1 unidad en un archivo de
  14) no es detectable con unidades de 5 s. Se reporta cuántos falsos son
  de ese tipo.
- **Secundarias (sin criterio):** todos los candidatos en conf con su umbral
  de dev; desglose por condición y por fracción de la voz principal; nº de
  episodios BBC declarados de un hablante con G y el elegido.
- **Jobs (2026-10-12):** 56270 mix y 56272 ina COMPLETED. 56271 cache FAILED
  a los 70 s con CUDA OOM en faster-whisper: `--gres=gpu:1` genérico cayó en
  ag001, cuyo A100 está partido en MIG (probablemente un slice chico). El
  eval 56273 quedó en DependencyNeverSatisfied.
- **Relanzado (2026-10-22):** 56273 cancelado. Cache en shards de RTX A6000:
  job 58171, `scripts/exp039_cache_shard.sbatch` (`shard:rtxa6000:14`,
  `expandable_segments`), corre en ds001; retoma desde lo ya escrito (1 item
  de domix del 12 oct). Eval: job 58172, `afterok:58171`. Mismo código y
  mismos datos; solo cambia el recurso.
  Domix son 160 archivos (31.9 h, unos 23 000 unidades de 5 s); a ~1 unidad/s
  (471 unidades en 8 min) no cabe en las 4 h del job. No se pudo ampliar el
  límite (permiso denegado), así que se encadenó un segundo cache, job 58174
  (`--time=06:00:00`, `afterany:58171`), que retoma lo ya escrito. El eval
  58172 pasó a `afterok:58174`.

### Corrida SumMe para EXP-037 / 038 (antes de evaluar nada en SumMe)
- **Job 56181:** 4.4 días en cola. Corrió 16 min en ag001 y terminó 19 de 25
  videos. Falló en Scuba.mp4 porque ffmpeg no encuentra pista de audio.
- **Videos sin audio en la fuente:** Scuba y St Maarten Landing. Ni el mp4
  ni el webm de SumMe traen pista de audio (ffprobe), así que son videos
  mudos.
  - Entran con una pista silenciosa de su duración exacta
    (`data/summe_silent/`), usando la opción de audio externo de
    `cava_run.py`. Es lo que vería el producto con un video mudo: sin
    transcripción y con voz vacía.
  - No es una exclusión. Si el pipeline falla con ellos, se excluyen y se
    declara.
- **Job de la segunda parte:** `scripts/v1_summe2.sbatch`, con los 6 que
  faltan (Statue of Liberty, Uncut_Evening_Flight, Valparaiso_Downhill,
  Scuba, St Maarten Landing, Cooking). Va un comando por video, para que un
  fallo no detenga al resto.
- **2026-10-22:** el job 57354 (A100) sigue en cola detrás de 7 jobs A100 de
  2 días de otro usuario, con más prioridad. La misma segunda parte se lanza
  en shards de la RTX A6000 de g002: job 58144, `scripts/v1_summe2_shard.sbatch`,
  con ~42 GB libres medidos con `nvidia-smi` antes de lanzar. Arrancó por
  backfill a las 13:11. Mismo código y mismos videos; solo cambia la GPU.
  57354 queda como respaldo y se cancela si 58144 termina bien.
- **Resultado de la corrida:** job 58144 COMPLETED en 14 min. Los 25 videos
  tienen `clips.jsonl` y G-versión True, incluidos los dos mudos (ASR 0
  segmentos) y Cooking. Los 25 manifiestos tienen `git_dirty: false`. 57354
  cancelado.

### Resultado EXP-037 · confirmación (SumMe, 25 videos; H\* = H3 congelado en dev)

| regla | recompensa media |
|---|---|
| **H3 saliente** | **0.278** |
| H0 producto (24 videos, ver abajo) | 0.158 |
| uniforme, mismas duraciones que H3 | 0.120 |
| al azar | 0.010 |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. H3 − uniforme | +0.158 ± 0.225 | 0.70 | **no** |
| 2. H3 − H0 (n = 24) | +0.139 ± 0.226 | 0.61 | **no** |
| 3. H3 − al azar | +0.269 ± 0.173 | 1.55 | **no** |

**No validado.** H3 tiene la media más alta en SumMe, pero la varianza entre
videos es grande (de −0.62 a +3.00) y ninguna diferencia llega a 2 SE.

**Caso no previsto en el pre-registro (Jumps, 38 s):**
- el presupuesto de highlights10pct es 3.8 s, menos que una unidad de 5 s,
  así que el producto no devuelve ningún clip y H0 no tiene recompensa;
- el criterio 2 se calcula sobre los 24 videos con H0 definido;
- sensibilidad: con H0 = 0 en Jumps, +0.127 ± 0.217 (z 0.58), la misma
  conclusión.

Es además un defecto del producto: con videos de menos de 50 s, el 10 % no
cabe en una unidad y los highlights salen vacíos. Las reglas H1–H3 usan
m ≥ 1 y no lo tienen.

### Resultado EXP-038 · SumMe (política entrenada con los 50 de TVSum)

| política / base | recompensa media |
|---|---|
| H3 | 0.278 |
| uniforme en la rejilla | 0.156 |
| centro | 0.091 |
| al azar | 0.002 |
| **política aprendida** | **−0.265** |

| criterio | diferencia | z | ¿cumple? |
|---|---|---|---|
| 1. política − uniforme | −0.421 ± 0.153 | −2.75 | **no** |
| 1b. política − centro | −0.356 ± 0.152 | −2.34 | **no** |
| 2. política − H3 | −0.544 ± 0.209 | −2.60 | **no** |
| secundaria: política − al azar | −0.267 ± 0.102 | −2.62 | peor que el azar |

**No validado: transfiere en negativo.** En SumMe, la política entrenada en
TVSum es significativamente peor que elegir al azar.

- **El sesgo de posición no es el mismo en los dos conjuntos.** z media por
  decil de duración en SumMe:

  `+0.13 +0.09 +0.21 +0.04 −0.10 −0.06 −0.10 +0.02 −0.14 −0.06`

  Ahí se premia el principio, no el centro. Por eso el centro cae a 0.091 y
  lo uniforme sube a 0.156.
- **La política aprendió preferencias propias de TVSum:**
  - posición +1.45, es decir, prefiere el final;
  - cambio visual −2.99, prefiere tramos quietos;
  - acuerdo vjudge −2.66.

  En videos de usuario de SumMe (deportes, cámara en mano) esas
  preferencias apuntan en contra.
- **Cierre de EXP-038:** criterios 1, 1b, 2, 3 y 3b no cumplidos. La
  recompensa de importancia de un solo conjunto pequeño no sirve para
  entrenar una política de clips que generalice. Ver la propuesta de
  recompensa en el reporte del 16 oct (normalizar por posición o un
  conjunto grande).
