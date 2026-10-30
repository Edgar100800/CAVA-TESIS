# Estado de CAVA — qué está implementado, qué está validado y con qué contenido

> Corte al 2026-10-22, HEAD 1c21714. Base para congelar el stack y pasar a
> la evaluación con personas (A/B). La evidencia de cada fila está en
> `docs/EXPERIMENT_LOG.md`; la arquitectura, en `docs/architecture.md`.
>
> Leyenda:
> - **validado**: pre-registrado, confirmado en datos no vistos (z > 2);
> - **acotado**: validado con un límite declarado;
> - **parcial**: algunos criterios sí y otros no;
> - **no validado**: se probó y no pasó;
> - **sin probar**: implementado sin evaluación propia.

## 1. Módulos del pipeline

| # | módulo | código | implementado | validación | estado |
|---|---|---|---|---|---|
| 1 | Unidades fijas (5 s film / doc, 10 s meeting) | `topicagg/pipeline.py` | sí | base de todos los exp. | en producto |
| 2 | Señal visual (SigLIP, 1 frame / unidad) | `pipeline.py` | sí | EXP-015 / 016 (enlace z 6–8), EXP-027 | **validado** |
| 3 | Transcripción (Whisper large-v3 → bge) | `pipeline.py` | sí | EXP-030: Parakeet no la reemplaza | en producto |
| 4 | VJudge (Qwen2.5-VL-7B, resumen ~40 s → bge) | `pipeline.py` | sí | EXP-015 / 016 (resúmenes z 3); como juez de trama no sirve (EXP-010–014) | **acotado** (enlace, no corte) |
| 5 | Voz como votante de tópico (log-mel + tono) | `topicagg/voice.py` | sí | EXP-020a (AUC 0.72–0.74) | **validado** |
| 6 | Turnos de hablante como votante de fronteras (meeting) | `scripts/speaker_turns.py` | sí | EXP-023 (+0.075, z 2.32; empata con contiguo) | **parcial** |
| 7 | Gestor sin fusión: votos, retornos, enlace promedio, abstención | `topicagg/multimodal_manager.py` | sí | EXP-017 / 018 (test MovieNet z 2.5; enlace z 5.6) | **validado** |
| 8 | Ajuste de fronteras a cortes visuales (snap ≤ 30 s) | `multimodal_manager.py` | sí | EXP-027 (91 películas, z 26.6 / 23.0) | **validado** |
| 9 | Perfiles de contenido (film p80, documentary p90, meeting p95) | `pipeline.py` | sí | EXP-018, EXP-025 (BBC z 6.1 / 7.4), EXP-021c / 023 | **validado** (meeting: iguala a contiguo) |
| 10 | Pesos de voto aprendidos | `scripts/learn_vote_weights.py` | sí | EXP-024 (z 1.22) | **no validado**; producto con pesos iguales |
| 11 | Mapa de tópicos con retornos y provenance | `topicagg/topic_map.py` | sí | EXP-017b / 018 (G-coherencia) | **validado** |
| 12 | Etiqueta de tópico (Qwen2.5-14B sobre todos los tramos) | `pipeline.py` | sí | EXP-019 / 019b (z 7–17) | **validado** |
| 13 | Nombres de personajes propagados por enlaces | `pipeline.py` | sí | EXP-019d | **validado** |
| 14 | Identidades por apariencia (P#) | — | sí | EXP-019e–g: poco específicas | **no validado**; no se publican como identidad |
| 15 | Identidad de hablante (WavLM-sv + ward + BIC) | `topicagg/speaker.py` | sí | EXP-022d, EXP-028 (VoxConverse ARI 0.25 → 0.64, AMI 0.29 → 0.73) | **validado** en habla conversacional |
| 16 | Detector de un solo hablante (spread, τ 0.976) | `speaker.py` | sí | EXP-029 (0 / 40 falsos en AMI) | **acotado**: no ve al narrador de BBC (0 / 11) |
| 17 | Filtro de habla S&W / I&W para identidades | `scripts/exp034_*` | sí (fuera del producto) | EXP-034 (habla falsa 0.73 → 0.13–0.16), EXP-035a (+0.41, z 5.6) | **parcial**: bloqueado por falsos narradores (EXP-035a / 036) |
| 18 | Detectores de segunda voz (q15, minor, bic12, NME) | `scripts/exp039_*` | sí | EXP-039 (criterio 1 no: z −0.37 S&W, 0.00 I&W; `results/exp039.json`) | **no validado** |
| 19 | Versiones por consumidor y gate G-versión | `topicagg/versions.py` | sí | G-versión 58 / 58 películas, 80 / 80 reuniones, 90 / 90 v1, 25 / 25 SumMe | **validado** (presupuesto, no calidad) |
| 20 | Calidad de highlights (regla "tópicos más largos") | `versions.py` | sí | EXP-031 (≈ azar en TVSum) | **no validado** |
| 21 | Regla de highlights H3 (ventana saliente por tópico) | `scripts/exp037_highlights.py` | sí (fuera del producto) | EXP-037 (SumMe z 0.70 frente a uniforme) | **no validado** |
| 22 | Nivel de capítulo (top-N fronteras por fuerza) | `topicagg/chapters.py` | sí | EXP-033 (fronteras F1 z 2.57; agrupamiento z 0.59) | **parcial**; no adoptado |
| 23 | Política de clips aprendida (bandido contextual) | `scripts/exp038_policy.py` | sí (fuera del producto) | EXP-038 (TVSum, categoría fuera: 0.014; SumMe −0.265, peor que el azar) | **no validado** |
| 24 | Clips mp4, playlists, `index.md` / `index.json` | `pipeline.py` | sí | verificado con ffprobe en BBC y v1 | en producto |
| 25 | Contrato de corrida `cava-run-v1` (manifiesto, `clips.jsonl`, `rewards.jsonl` aparte) | `pipeline.py`, `scripts/rewards_tvsum.py` | sí | 115 corridas con `gt_used: false` | en producto |
| 26 | Exportación de datos de entrenamiento | `scripts/export_training_data.py` | sí | AMI y MovieNet | sin evaluación propia |

## 2. Qué se puede afirmar por tipo de contenido

| tipo | perfil | estructura de tópicos | identidades | versiones / clips |
|---|---|---|---|---|
| Película / ficción | film | **validado** (MovieNet test, 91 películas train2) | voz validada; P# por apariencia no | presupuesto validado; calidad no medida con personas |
| Documental | documentary | **validado** (BBC, 62 % del techo humano) | voces publicadas como **grupos acústicos**; el narrador único no se resuelve | presupuesto validado |
| Reunión | meeting | iguala a la partición contigua; no la supera | **validado** (AMI ARI 0.73) | presupuesto validado |
| YouTube largo (charlas, tutoriales) | documentary | sin GT de tópicos; contra capítulos del autor no supera a lo uniforme (EXP-032 / 033) | sin GT | presupuesto validado |
| Video de usuario corto (1–11 min) | film | sin GT de tópicos | sin GT | highlights ≈ azar (TVSum); **vacíos bajo 50 s** (defecto, ver §4) |

## 3. Contenido disponible y anotaciones

| conjunto | tipo | n | duración | anotación humana | corrido en CAVA | clips mp4 | útil para A/B con personas |
|---|---|---|---|---|---|---|---|
| BBC Planet Earth | documental | 11 episodios | ~49 min c/u | escenas (5 anotadores) | `data/cava_runs_doc/` (producto pre-v1) | sí (99 versiones) | **sí**: largo, con escenas GT |
| AMI | reunión | 120 (122 con media) | ~35 min | tópicos + hablantes | 120 mapas; producto completo solo IS1000c | 1 reunión | sí, si se cortan más reuniones |
| VidChapters blind40 | YouTube largo | 40 | 10–40 min (14 h) | capítulos del autor | `data/cava_runs_v1/` | sí | **sí**: capítulos del autor como referencia |
| VidChapters raw_ext | YouTube largo | 50 | ~22 min | capítulos del autor | `data/cava_runs_v1_dev/` (sin cortar mp4) | no | sí, con `--no-cut` desactivado |
| TVSum | video de usuario | 50 | 2–11 min (3.5 h) | importancia 1–5, 20 anotadores | `data/cava_runs_v1/` | sí | sí, para highlights |
| SumMe | video de usuario | 25 | 1–6 min | resúmenes de 15–18 usuarios | `data/cava_runs_v1_summe/` | sí (111 versiones) | sí, para highlights |
| MovieNet | película | 1 100 en la lista; usadas val, test, train y train2 (91) | completas | escenas, beats de trama, cast | mapas de tópicos | **no**: en disco solo hay fotogramas clave (240P_frames), sin video | no, para ver clips |
| VoxConverse | audio (debates, noticias) | 448 | — | diarización | cachés de identidad | no | no (sin video) |
| AVA-Speech | película (15 min) | 148 | 15 min | habla / música por segmento | cachés de filtro | no | no (banco de audio) |
| Videos de prueba | podcast (ES), resumen de película (ES), cortometraje | 3 | largo / medio / corto | ninguna | `test-video/results/` | sí | sí, como contenido real sin GT |
| BBC, escucha EXP-035b | documental | 176 clips de 5 s | — | **pendiente** (0 / 176) | — | sí (mp3) | anotación propia pendiente |

## 4. Huecos conocidos antes de mostrar el producto a personas

1. **Highlights vacíos en videos < 50 s.** El 10 % del presupuesto no cabe
   en una unidad de 5 s (Jumps en SumMe). Arreglo mínimo: usar al menos una
   unidad. Cambia el producto, así que se declara antes del A/B.
2. **Voces en documentales:** se publican como grupos acústicos, no como
   hablantes. Ninguna UI del A/B debe presentar V# como personas en el perfil
   documentary.
3. **Calidad de highlights y recap:** ninguna regla supera a bases simples
   frente a referencias humanas automáticas (EXP-031, 037). El A/B con
   personas es la primera medición directa.
4. **Granularidad:** en YouTube largo, el nivel de tópico es ~2.7× más fino
   que los capítulos del autor (EXP-032). El nivel de capítulo no está
   validado (EXP-033).
5. **Corridas BBC y AMI:** son anteriores al contrato v1 (sin `clips.jsonl`).
   Para un A/B reproducible hay que recorrerlas con el stack congelado.
6. **GPU:** solo hay una A100 completa, ocupada por otros usuarios durante
   días. Las corridas nuevas deben planificarse en shards de las A6000
   (SumMe corrió así en 14 min).

## 5. Stack a congelar para el A/B

- **Pipeline:** `topicagg/` en HEAD; pesos de modelos fijados en
  `run_manifest.json` (Whisper large-v3, SigLIP, bge, Qwen2.5-VL-7B,
  Qwen2.5-14B, WavLM-sv).
- **Perfiles:** film / documentary / meeting, como en §2. Sin nivel de
  capítulo, sin filtro de habla, sin H3, sin política aprendida.
- **Versiones:** capítulos por tópico, recap 60 s, highlights 10 %, hilos e
  hilos por hablante (solo meeting).
- **Toda corrida del A/B** se hace en un directorio nuevo, con
  `git_dirty: false` y `gt_used: false`.
