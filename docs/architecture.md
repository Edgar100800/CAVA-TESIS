# Arquitectura CAVA — de un video largo a tópicos y clips

> Documento de referencia de la infraestructura construida y validada.
> Evidencia, criterios y resultados: `docs/EXPERIMENT_LOG.md`. Regla
> fundacional: `docs/adr/0001-sin-fusion-de-representaciones.md`.

## 1. Qué hace

Toma contenido largo (película, documental, reunión, charla) y produce:

- un **mapa de tópicos**: tópicos que pueden **retornar** (un tema aparece,
  se deja y se retoma), cada uno con rangos de tiempo, etiqueta, personajes y
  hablantes, y la procedencia por señal;
- **versiones por consumidor**: capítulos, recap de 60 s, highlights del
  10 %, hilos de tópico e hilos por hablante;
- **clips mp4** por versión, un mp4 por playlist y un índice (`index.md`,
  `index.json`).

## 2. Flujo

```
video (+ audio) ──► unidades fijas (film 5 s · meeting 10 s)
   │
   ├─ voice       espectrograma log-mel + tono (topicagg/voice.py)
   ├─ visual      SigLIP del fotograma central
   ├─ transcript  ASR faster-whisper large-v3 → bge
   └─ vjudge      Qwen2.5-VL-7B frozen: resumen por bloque (~40 s) → bge
            │     (cada señal es un votante; nunca se fusionan)
            ▼
   manage()  topicagg/multimodal_manager.py
     · cada señal: sus cortes (percentil propio) y sus tópicos con RETORNOS
     · votantes de fronteras opcionales: SegLoop, turnos de hablante
     · consenso por ENLACE PROMEDIO sobre la matriz de votos
     · ABSTENCIÓN: una señal sin evidencia en un shot no vota sobre él
     · SNAP (film/documentary): fronteras del mapa → frontera visual a ≤ 30 s (EXP-027)
            ▼
   topic_map  topicagg/topic_map.py   (niveles fine/default, contexto por clip)
            ▼
   etiqueta de tópico   Qwen2.5-14B frozen sobre todos los tramos (EXP-019b)
   personajes           nombres propios + heredados por enlace (EXP-019d)
   hablantes            identidades de voz, ward + K por BIC (EXP-022d)
            ▼
   versions   topicagg/versions.py   → G-versión
            ▼
   clips mp4 + playlists + index     topicagg/pipeline.py (ffmpeg)
```

Uso: `python scripts/cava_run.py VIDEO[:perfil[:AUDIO]] ... --out data/cava_runs`.
Cada etapa se cachea en `<out>/<video>/work/` y se puede reanudar.

## 3. Componentes

| módulo | función |
|---|---|
| `topicagg/multimodal_manager.py` | `manage()`: votos por señal, retornos (`return_percentile`), enlace promedio (`link_mode="average"`), abstención (`abstain`), votantes de fronteras (`boundary_signals`), pesos por señal (`weights`) |
| `topicagg/topic_map.py` | mapa de tópicos: tramos, retornos, etiqueta, provenance (`agreement`, `support`, coherencia), contexto por clip |
| `topicagg/versions.py` | perfiles de consumo y gate G-versión |
| `topicagg/voice.py` | señal de voz sin modelos (log-mel + f0 + energía) |
| `topicagg/pipeline.py` | pipeline de punta a punta, resumible |
| `scripts/cava_run.py` | CLI del pipeline |
| `scripts/speaker_turns.py` | votante de fronteras por cambio de quién habla (EXP-023) |
| `scripts/eval_voice_identities.py` | identidades de voz (ward + BIC) |
| `scripts/export_training_data.py` | exportación de datos de entrenamiento (§6) |
| `scripts/learn_vote_weights.py` | aprendizaje de pesos de voto por señal (EXP-024) |

## 4. Perfiles de contenido

La granularidad NO se infiere: ningún criterio interno sin GT eligió bien
(EXP-021). Es un perfil explícito.

| perfil | unidad | corte | retorno | validación |
|---|---|---|---|---|
| film | 5 s (o shots) | p80 | p90 | EXP-018 (test MovieNet) |
| documentary | 5 s | p90 | p90 | EXP-025 (BBC Planet Earth, dominio nuevo: 62 % del techo humano; supera a contiguo z 6.1, fused z 7.4, p80 z 2.6) |
| meeting | 10 s | p95 + votante de turnos w = 6 | p90 | EXP-021c, EXP-023 (iguala a contiguo, supera a fusión y a cava sin turnos) |

## 5. Qué está validado (pre-registrado y en datos no vistos)

| afirmación | evidencia |
|---|---|
| Enlazar segmentos no contiguos del mismo hilo supera a la proximidad | EXP-015 / 016 (visual z 6–8; resúmenes VJudge z 3) |
| El mapa con retornos + consenso promedio + abstención supera a la fusión y a v2.1 (películas) | EXP-018, split test (z 2.5; precisión de enlace z 5.6) |
| Cada señal conserva su estructura (G-coherencia) | EXP-017b, EXP-018, EXP-020b, EXP-021c |
| La etiqueta del tópico certifica personajes y contenido (guion + cast) | EXP-019 / 019b (z 7–17, dev y test) |
| Los nombres se propagan por los enlaces sin perder precisión | EXP-019d (val, test, train, train2) |
| La voz identifica al hablante | EXP-020a (AUC 0.72–0.74 frente a visual 0.55–0.57, z 5.8–12.1) |
| Identidades de voz específicas; ward + BIC es la mejor regla | EXP-022 / 022d (ARI 0.30, especificidad 87–93 %) |
| Transfiere a documentales nunca vistos (escenas de 5 anotadores) | EXP-025 (z 6.1 frente a contiguo, 7.4 frente a fused) |
| Identidades de voz solo sobre unidades con habla: menos grupos espurios, no inferior en AMI | EXP-026 (z 2.29; ARI −0.007) |
| Fronteras de la señal visual + agrupamiento por consenso (snap a ≤ 30 s) | EXP-027 (MovieNet train2: M_local +0.091 z 26.6, F1 +0.054 z 23.0; frente a control al azar z 12.4 / 27.8) |
| Versiones por consumidor cumplen presupuesto | G-versión: 58/58 películas, 80/80 reuniones |

## 6. Qué no funcionó (y por qué importa)

- Fronteras de **trama** desde señales frozen (EXP-010 → 014): ninguna supera
  a SegLoop. La multimodalidad aporta al **enlace**, no al corte.
- Enlace por componentes conexas: **percola** con retornos (EXP-017).
- Votación por mediana / quorum ingenuo entre señales (EXP-015 / 016): diluye
  a la mejor señal.
- Identidades P# por apariencia: consistentes pero **poco específicas**
  (0.55–0.63 frente a grupos al azar). Para identidad, la voz es la señal,
  pero **solo en habla conversacional**: con narrador + música, la voz agrupa
  la escena acústica (EXP-026). Fuera del perfil meeting, los V# se publican
  como "grupos acústicos".
- K = 1 permitido en BIC (EXP-026, desarrollo): colapsa reuniones reales.
- Fronteras exactas: en documentales la señal visual sola corta mejor que el
  consenso (F1 0.48 frente a 0.40). CAVA gana en agrupar, no en cortar.
- Re-etiquetar con un registro de personajes o con umbral absoluto
  (EXP-019c / 019g): cuesta precisión o contenido.
- Granularidad elegida por criterio interno (EXP-021): no funciona; de ahí
  los perfiles.
- En reuniones, la segmentación contigua es una base muy fuerte: CAVA la
  iguala (EXP-021c). Con turnos de hablante (EXP-023) mejora +0.075 MCC,
  pero sigue sin superar a lo contiguo.

## 7. Datos de entrenamiento y pesos

`scripts/export_training_data.py` → `data/training/<dominio>/<id>.npz|.json`:

- **señales** por unidad, una matriz por señal (float16, nunca fusionadas);
- **objetivos**:
  - AMI: `topic`, `speaker` por unidad;
  - MovieNet: `scene`, `beat` (párrafo story) y `cast` (multi-hot);
- **splits**: AMI dev / conf / fresh3; MovieNet val / test / train / train2.

**Qué se aprende:** pesos y umbrales **por señal** de `manage()` (permitido
por ADR-0001), nunca un embedding fusionado. Primera instancia:
`learn_vote_weights.py` (EXP-024): funciona de punta a punta y da pesos
interpretables (turnos ≈ 2, voz 1.0, visual 0.7, transcript 0.7, vjudge 0.5),
pero la mejora (+0.031 MCC, z 1.2) no está validada. El perfil sigue con
pesos iguales.

Siguientes pesos naturales:
- percentiles por señal;
- `return_percentile` por señal;
- peso de los votantes de fronteras;
- umbrales de identidad de voz.

## 8. Cómo extender

- **Nueva señal:** cualquier matriz [n_unidades, D] entra en `manage(signals=…)`
  como votante; un score de frontera [n−1] entra en `boundary_signals`. Si no
  hay evidencia en una unidad, fila nula (se abstiene).
- **Nuevo perfil de consumo:** una función en `versions.py` que devuelva
  playlists de clips (tramos de tópico alineados a unidades) y respete
  `budget_s`.
- **Nueva validación:** GT solo en la evaluación; pre-registrar criterio,
  conjunto de desarrollo y de confirmación en `EXPERIMENT_LOG.md` antes de
  medir.
