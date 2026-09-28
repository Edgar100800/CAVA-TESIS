# VERSIONES — CAVA (topicagg)

> **Repo propio desde 2026-09-25:** `~/Tesis/CAVA` (antes vivía en `~/Tesis/A2Summ/topicagg`;
> esa copia queda congelada como origen). Documentación del proyecto: `docs/` +
> `docs/granularity-plan.md` (afinado quant+qual, abierto).

> Registro de versiones de implementación. Una sección por versión: qué cambió,
> por qué, y qué evidencia la respalda. Dir de trabajo v2: `topicagg/`.

## v1 — `a2summ_x/` (congelada; paper `paper/paper_a2summ_x.tex`)

- **Paradigma:** resumen de video frame/shot-by-shot, unimodal-dominante.
- **Resultados del paper:** baseline verificado doble (split0 0.6383 idéntico; BLiSS Δ<0.004);
  rama de texto ΔF1 +0.033 TVSum (p=0.014, N=25); control V-JEPA-2 nulo; levers rechazadas.
- **Limitación validada en el cierre:** la señal de video es **aplastada estructuralmente** por
  el texto (alineación reescribe la query + gating softmax cero-suma + head sobre blend).
  Evidencia: gating texto 0.75–0.89; GraphVSum-BLiSS colapso visual; OOD ρ(importancia)≈0.
  Detalle: `topicagg/video-signal-analysis.md`.

## v2 — `topicagg/` (ACTIVA — análisis de video por tópicos multimodal)

- **Paradigma:** análisis de video (no summarization): segmentación **temática** + agregación
  de clips por tópico → **múltiples versiones adaptadas al consumidor**.
- **Cambio de unidad:** frame/shot (2s ciego) → **segmentos temáticos** (típicamente >2s).
- **Cambio de señales:** texto-dominante → **4 señales** en paralelo: transcript, **OCR
  (texto en pantalla)**, audio, video — enlazadas por tópico (el caso TPU: streamer lo dice +
  texto en pantalla + se retoma después = mismo grupo, aunque v1 sin audio no podía conectarlo).
- **Estado v2.0 (este commit):**
  - `signals/core.py` — TranscriptSignal implementado (embeddings pre-extraídos).
  - `topic_segmenter.py` — fronteras temáticas por desplazamiento de embeddings.
  - `topic_aggregator.py` — enlaza sub-segmentos no adyacentes por similitud al centroide
    (≥ τ). **Piloto BLiSS OK** (mecanismo demostrado).
  - `demo_bliss.py` — CPU sobre datos locales; hallazgo de calibración: RoBERTa domina por
    locutor → fragmentación fina (17 tópicos/clip, coherencia plana 0.99). Tuning pendiente:
    centrado por video, τ de enlace, ventana w.
  - Contratos sin implementar: OCR / audio / video signals (requieren extracción real).
- **v2.1 — GESTOR MULTIMODAL SIN FUSIÓN (2026-09-25):** `multimodal_manager.py`.
  Lección v1 aplicada al extremo: **no se fusionan embeddings ni scores** — cada señal emite
  SUS fronteras (percentil propio), SUS etiquetas de tópico, y el tópico emerge por
  **consenso de votos** (mayoría ponderada de señales activas; union-find con quorum de
  enlace). Grupos con provenance por señal. Verificado en sintético (2 señales) y
  **en real: 3 videos TVSum (transcript ASR-tiny + visual SigLIP/BaSSL + densidad de voz)** —
  los grupos resultantes son pasos procedurales del contenido (ej. 98MoyGZKHXc: seguridad →
  evaluar clavo → inflar → troubleshooting → taller), provenance multi-señal. Outputs:
  `data/cava_pilot/<video>/topics_multimodal.json`. OCR/audio-espectro pendientes de
  extracción (contratos listos).
- **Gates v2 (pre-registrados):**
  - G-coherencia: intra-tópico − inter-tópico ≥ margen (a fijar en el tuning, antes de medir
    en corpus completo).
  - G-enlace: precisión de enlaces no-adyacentes validada por humano en ≥20 casos.
  - G-versión: playlists por perfil cumplen presupuesto y ≥1 versión por perfil.
