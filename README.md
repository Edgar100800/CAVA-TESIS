# CAVA *(nombre provisional — ver renaming)*

**Consumer-Adaptive Video Architecture** — sucesor del analizador A2Summ-X.
Segmentación **temática** de video long-form mediante agregación multimodal
**sin fusión de representaciones**, y producción de múltiples versiones por
clip adaptadas al consumidor.

## Estructura

```
CAVA-TESIS/
├── topicagg/                 # paquete del producto (v2.1, núcleo)
│   ├── pipeline.py               # corrida completa: unidades → señales → mapa → versiones (cava-run-v1)
│   ├── multimodal_manager.py     # gestor sin fusión: votos por señal, retornos, abstención, enlace por quórum
│   ├── topic_map.py              # mapa de tópicos (niveles fine/default, provenance, snap a cortes)
│   ├── versions.py               # 5 formatos por consumidor + compuerta G-versión
│   ├── voice.py                  # rasgos de voz (log-mel + tono), señal `voice`
│   ├── speaker.py                # embedding de hablante WavLM-sv, detector de hablante único
│   ├── diarization.py            # pyannote community-1 en subproceso, turnos y V# por unidad (v1.1)
│   ├── profiles/                 # perfiles congelados v1_0 y perfiles v1_1
│   ├── identities.py             # identidades V# (ward + BIC), votante de turnos, hablantes por tramo
│   ├── embed.py                  # embeddings bge para transcript y vjudge
│   ├── labels.py                 # prompt y limpieza de la etiqueta de tópico
│   ├── chapters.py               # nivel de capítulo (parcial, fuera del producto)
│   ├── adaptive_aggregator.py    # agregador adaptativo (granularidad emergente)
│   ├── asr_parakeet.py           # ASR alternativo (EXP-030: no reemplaza a Whisper)
│   ├── topic_segmenter.py · topic_aggregator.py   # v2.0 (TopicGroup sigue en uso)
│   └── signals/                  # contratos de señal: TranscriptSignal (solo lo usan los demos);
│                                 #   OcrSignal y AudioSignal sin implementación ni llamadores
├── tests/               # 25 pruebas: gestor, abstención, mapa, versiones, snap, agregador adaptativo
├── scripts/             # un script por experimento o evaluación (exp0NN_*, eval_*, build_*)
├── demos/               # demo_bliss (transcripts) · demo_multimodal (video real, requiere SegLoop)
├── test-video/          # corridas sobre videos de prueba propios
├── results/             # JSON de resultados por experimento
├── logs/                # salidas de los jobs SLURM
├── reports/             # reportes semanales por fecha (AAAA-MM-DD/)
├── docs/                # EXPERIMENT_LOG, progress (estado por módulo), architecture, adr/, wayfinding/
├── tesis/               # documento de tesis en LaTeX (plantilla UTEC)
├── data/                # outputs (gitignored)
└── VERSIONS.md          # registro v1 → v2 → v2.1
```

## Instalación y pruebas

```bash
pip install -e ".[dev]"          # núcleo CPU (numpy, scipy, scikit-learn) + pytest
pip install -e ".[models,dev]"   # pipeline completo: torch, transformers, faster-whisper, pillow
python -m pytest -q
```

Los scripts de `scripts/` se ejecutan desde la raíz del repo (`python scripts/<x>.py`);
añaden la raíz a `sys.path` por su cuenta. `topicagg/` no importa nada de `scripts/`.

## Ejecutar el pipeline y elegir el stack

**El valor por defecto es `--stack v1.0`**: reproduce el comportamiento congelado de `tfm-v1.0`.
La diarización pyannote solo se activa si se pide expresamente `--stack v1.1`; cambia V# en `film` y
`meeting`, mientras `documentary` y el votante de turnos de `meeting` no cambian.

```bash
# Una sola vez: registrar el worker en el venv separado, sin instalar dependencias del producto.
python -m pip --python /data/tesis-cava/dia-venv/bin/python install --no-deps -e .

# v1.1 sobre un video nuevo (salida en un directorio nuevo).
python scripts/cava_run.py /ruta/video.mp4:film --stack v1.1 --out data/cava_runs_v11
```

El worker usa `HF_HUB_OFFLINE=1` y `/data/tesis-cava/hf_dia`. En otra máquina se configuran
`CAVA_DIA_PYTHON=/ruta/dia-venv/bin/python` y `CAVA_DIA_HF_CACHE=/ruta/hf_dia`. Los turnos con
solapamiento y exclusivos quedan en `work/diar.pyannote_c1.3533c8cf.{json,rttm,exclusive.rttm}`;
no reutilizan `speaker_xvec.npy` ni ninguna identidad V# de v1.0.

## Dependencias

- **SegLoop** (`~/Tesis/SegLoop`): motor de extracción de señales — ASR
  (faster-whisper), TransNetV2, SigLIP+BaSSL, ensemble frozen, VJudge.
  Se consume vía `PYTHONPATH`; CAVA nunca duplica ese código.
- Python: numpy (núcleo CPU). h5py para GT eccv16. GPU solo para VJudge.

## Decision records y wayfinding

- **ADRs:** `docs/adr/NNNN-slug.md` (formato heredado de SegLoop; convención obligatoria).
  En este repo solo existe `0001-sin-fusion-de-representaciones.md`; ADR-0007/0008
  (citadas abajo) son de SegLoop.
- **Wayfinding:** `docs/wayfinding/map.md` — mapa de decisiones del esfuerzo activo
  (afinado de granularidad) con tickets en `docs/wayfinding/tickets/`.
  Reglas: planear antes que ejecutar · referir tickets por nombre · una decisión
  resuelta por sesión · quorum de señales para enlazar tópicos.

## Documentos pilar

| Doc | Qué describe |
|---|---|
| [`docs/journey.md`](docs/journey.md) | La jornada de implementación: de v1 al gestor sin fusión, con evidencia |
| [`docs/integration-cava.md`](docs/integration-cava.md) | Contrato y fases de integración SegLoop+VJudge ▸ analizador |
| [`docs/granularity-plan.md`](docs/granularity-plan.md) | Plan activo: afinado de granularidad (quant + qual) |
| [`docs/narrative-pipeline.md`](docs/narrative-pipeline.md) | Capa narrativa experimental: contexto global, diez imágenes por candidato, decisiones y continuidad |
| [`topicagg/video-signal-analysis.md`](topicagg/video-signal-analysis.md) | Diagnóstico v1: por qué la señal visual muere en una fusión |

(No hay índice de documentos menores: los históricos viven en los repos de origen.)

## Origen y trazabilidad

- v1 (`~/Tesis/A2Summ/a2summ_x`): congelada tras el paper; su limitación
  estructural (texto aplasta la señal visual) documentada en
  `topicagg/video-signal-analysis.md`.
- v2.1 nace aquí: gestor SIN FUSIÓN (consenso de votos por señal,
  provenance por grupo). Registros en `VERSIONS.md`.
- Documentos heredados en `docs/` (copias de lectura); los originales viven en
  los repos de origen (SegLoop, A2Summ).

## Reglas del proyecto

1. Nada fusiona embeddings ni scores entre señales: el tópico emerge por
   **consenso de votos** (lección v1; ADR-0001 aquí, ADR-0007/0008 en SegLoop).
2. Toda evaluación con compuerta pre-registrada; cuantitativa Y cualitativa.
3. Todo resultado se valida por sus datos efectivos.
