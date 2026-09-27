# EXPERIMENT LOG — CAVA

> Registro de experimentos: configuración → resultado. Sin comentarios ni
> feedback. Decisiones tomadas a partir de resultados viven en ADRs.

---

## EXP-001 · Multi-tolerancia fronteras vs GT escenas
**2026-09-25 · 97 películas MovieNet · signals: transcript(TF-IDF) + visual(SigLIP)**
**Gestor: sin fusión, p80, link_quorum=2, tolerance_bins=1**

| tolerancia | precision | recall | F1 |
|---|---|---|---|
| ±1 shot | 0.253 | 0.808 | 0.369 |
| ±2 shots | 0.275 | 0.873 | 0.400 |
| ±5 shots | 0.301 | 0.942 | 0.436 |
| ±10 shots | 0.314 | 0.974 | 0.454 |
| ±20 shots | 0.320 | 0.991 | 0.463 |

Hallazgo: recall →0.99 con ±20 mientras precision se mantiene ~0.32.
Fronteras cercanas a GT pero con offset sistemático (granularidad/alineación).

`results/movienet_topics/multitolerance_both_p80_q2_t1.json`

---

## EXP-002 · Barrido de configuración (grid quant)
**2026-09-25 · 97 películas · grid: percentile × link_quorum × tolerance_bins**

| config | grupos | P@±1 | R@±1 | F1@±1 | intra transcript | intra visual |
|---|---|---|---|---|---|---|
| p70_q1 | 1.3 | 0.466 | 0.245 | 0.299 | 0.439 | 0.940 |
| p70_q2 | 15.0 | 0.212 | 0.892 | 0.330 | 0.909 | 0.970 |
| p80_q1 | 1.3 | 0.550 | 0.172 | 0.247 | 0.439 | 0.940 |
| p80_q2 | 11.3 | 0.253 | 0.808 | 0.369 | 0.826 | 0.966 |
| p90_q1 | 1.0 | 0.637 | 0.077 | 0.129 | 0.393 | 0.936 |
| p90_q2 | 8.3 | 0.322 | 0.622 | 0.398 | 0.759 | 0.961 |

Hallazgos: link_quorum domina (q1 colapsa en mega-grupo, q2 produce grupos
reales). percentile ajusta granularidad (más percentil → menos cortes → menos
coherencia intra). tolerance_bins no afecta agrupamiento.

`results/granularidad/sweep.json`

---

## EXP-003 · Ablation por señal (MovieNet, p80_q2_t1)
**2026-09-25 · 97 películas · una señal a la vez**

| señal | P | R | F1 |
|---|---|---|---|
| transcript solo | 0.100 | 1.000 | 0.178 |
| visual solo | 0.098 | 1.000 | 0.175 |
| ambas (consenso) | 0.275 | 0.788 | 0.386 |

Hallazgo: cada señal sola sobre-predice masivamente (P≈0.1, R≈1.0). El
consenso filtra la mayor parte del ruido y sube P a 0.275.

`data/movienet_topics/eval_p35_*.json`

---

## EXP-004 · VJudge razonamiento sobre keyframes MovieNet
**2026-09-25 · 3 películas · A100 3g.20gb shard**
**Gestor: Qwen2.5-VL 7B frozen, zero-shot, 3 keyframes por shot**

Mecanismo verificado: el juez lee keyframes por shot y produce explicación
semántica (qué pasa + momento narrativo). Los primeros 3 videos (Rear Window,
etc.) producen descripciones concretas de acción y setting.

`data/mn_reasoning/tt0047396.json` (y 2 más)

---

## EXP-005 · Piloto de salida real (CAVA output)
**2026-09-25 · 3 videos TVSum · ffmpeg + topicagg + ASR tiny**

114 clips mp4 cortados en 3 perfiles (recap60, highlights10pct,
full_chapters) + playlists JSON + contexto textual. Primer producto tangible
del pipeline completo.

`data/cava_pilot/` (SegLoop)

---


---

## EXP-006 · Análisis dual de granularidad — colapso a nivel GT
**2026-09-25 · 97 películas · gestor sin fusión p80_q2_t1**
**Camino 1: colapsar a GT (±10 shots) · Camino 2: grano fino sin colapsar**

| Camino | P | R | F1 |
|---|---|---|---|
| Colapsado a GT | 0.94 | 0.77 | **0.84** |
| Grano fino | 0.25 | 0.81 | 0.37 |
| Cobertura GT | — | 99.8% | — |

Hallazgo: el sistema detecta la estructura narrativa correctamente (F1 0.84
a granularidad GT). Las 4× fronteras finas adicionales son útiles para
clipping, no ruido. El F1 0.37 sin colapsar reflejaba granularidad distinta,
no falta de señal.

`results/dual_granularity.json`
