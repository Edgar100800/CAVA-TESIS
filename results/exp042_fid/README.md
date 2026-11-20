# EXP-042-FID — identidades por rostro y voces nombradas (exploratorio)

**Fecha:** 2026-11-19/20 · **Estado:** exploratorio, **sin anotación humana, sin pre-registro**.
Uso: demo y nota de método (capa F3 de identidades ancladas). No es resultado de ningún OE.

Película: *Spider-Man: Brand New Day* (145 min), run local `CAVA_minimo/outputs/Spider_Man`
(1 740 unidades de 5 s, voces V1–V8 por WavLM-sv + ward/BIC).

## Pipeline

1. `code/exp042_fid.py scan` — 1 fps, InsightFace `buffalo_l` (detección + ArcFace 512d).
   9 312 rostros; 4 shards (GPU local .56 + .55/.61).
2. `cluster` — jerárquico promedio, distancia coseno 0,45, ≥ 20 rostros → 43 grupos.
3. Nombres puestos por el equipo mirando una hoja de contactos (`names.json`); los fragmentos
   del mismo personaje se fusionan por similitud de centroide ≥ 0,6 y revisión visual.
4. `code/voice_face_cross.py` — co-presencia voz/rostro por unidad (p y lift).
5. `code/asd.py` + `code/asd_aggregate.py` — hablante activo por movimiento de labios
   (landmarks 2d106, 5 fps, 1 426 tramos con voz, 3 GPUs).
6. V6 se dividió en V6a/V6b (ward k = 2 sobre los x-vectors de V6; `v6_split.json`).
7. `code/build_named_map.py` — `demo/topic_map_named.json` y `demo/timeline.html`.

## Asignación final de voces (curada; ver `VOICE_NAMES` en `build_named_map.py`)

| Voz | Personaje | Evidencia |
|---|---|---|
| V1 | Mary Jane Watson | pantalla ×2,6 + labios 28 % |
| V2 | Yelena | pantalla ×6,7; labios 20 % vs Peter 18 % (probable) |
| V3 | Peter Parker | labios 26 % (siguiente 8 %) |
| V4 | Peter Parker (con máscara) | voz ≈ V3 (coseno 0,963) + Spider-Man en pantalla ×2,3 (probable) |
| V5 | Ned | pantalla ×6,3 + labios 26 % |
| V6a | Punisher | pantalla 46 % + labios 37 % |
| V6b | Bill Metzger | pantalla 37 % + labios 28 % |
| V7 | sin asignar | Peter domina la pantalla; voz distinta de V3 (0,67) |
| V8 | voz fuera de cuadro | 69 % de sus tramos sin labios activos |

Las reglas automáticas (`voice_face_cross.json`, `asd_assignment.json`) son la evidencia; la
tabla anterior combina ambas y la similitud entre voces.

## Contenido

- `code/` scripts (rutas absolutas del laboratorio .56).
- `names.json` (cid → personaje), `clusters.json`.
- `voice_face_cross.json`, `asd_assignment.json`, `v6_split.json`, `asd_*.jsonl`.
- `intervals/<personaje>.csv` — apariciones en pantalla (inicio/fin).
- `demo/topic_map_named.json` (campos `speakers_named`, `characters_on_screen`, `voice_names`),
  `demo/timeline.html`.

## No incluido (a propósito)

- Embeddings faciales (`scan.npz`, `centroids.npz`): datos biométricos.
- Hojas de contactos y recortes de rostros (derechos de imagen).
- El video.

## Límites

Co-presencia ≠ habla; el movimiento de labios falla con máscaras, perfiles y caras pequeñas
(480p). Peter domina la pantalla y sesga el argmax de labios a su favor. Sin gold humano no hay
precisión/recall de identidad.
