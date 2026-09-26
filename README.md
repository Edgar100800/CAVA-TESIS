# CAVA *(nombre provisional — ver renaming)*

**Consumer-Adaptive Video Architecture** — sucesor del analizador A2Summ-X.
Segmentación **temática** de video long-form mediante agregación multimodal
**sin fusión de representaciones**, y producción de múltiples versiones por
clip adaptadas al consumidor.

## Estructura

```
CAVA/
├── topicagg/            # gestor multimodal sin fusión (v2.1, núcleo)
│   ├── multimodal_manager.py   # consenso de votos por señal (sin embeddings fusionados)
│   ├── topic_segmenter.py      # fronteras temáticas por desplazamiento
│   ├── topic_aggregator.py     # enlaza segmentos no adyacentes del mismo tema
│   └── signals/                # contratos: transcript ✓ · OCR · audio · video
├── demos/               # demo_bliss (transcripts) · demo_multimodal (video real)
├── docs/                # jornada + integración + plan de granularidad
├── scripts/
├── data/                # outputs (gitignored)
└── VERSIONS.md          # registro v1 → v2 → v2.1
```

## Dependencias

- **SegLoop** (`~/Tesis/SegLoop`): motor de extracción de señales — ASR
  (faster-whisper), TransNetV2, SigLIP+BaSSL, ensemble frozen, VJudge.
  Se consume vía `PYTHONPATH`; CAVA nunca duplica ese código.
- Python: numpy (núcleo CPU). h5py para GT eccv16. GPU solo para VJudge.

## Documentos pilar

| Doc | Qué describe |
|---|---|
| [`docs/journey.md`](docs/journey.md) | La jornada de implementación: de v1 al gestor sin fusión, con evidencia |
| [`docs/integration-a2sumx.md`](docs/integration-a2sumx.md) | Contrato y fases de integración SegLoop+VJudge ▸ analizador |
| [`docs/granularity-plan.md`](docs/granularity-plan.md) | Plan activo: afinado de granularidad (quant + qual) |
| [`topicagg/video-signal-analysis.md`](topicagg/video-signal-analysis.md) | Diagnóstico v1: por qué la señal visual muere en una fusión |

(No hay índice de documentos menores: los históricos viven en los repos de origen.)

## Origen y trazabilidad

- v1 (`~/Tesis/A2Summ/a2summ_x`): congelada tras el paper; su limitación
  estructural (texto aplasta la señal visual) documentada en
  `topicagg/ANALYSIS_VIDEO_SIGNAL.md`.
- v2.1 nace aquí: gestor SIN FUSIÓN (consenso de votos por señal,
  provenance por grupo). Registros en `VERSIONS.md`.
- Documentos heredados en `docs/` (copias de lectura); los originales viven en
  los repos de origen (SegLoop, A2Summ).

## Reglas del proyecto

1. Nada fusiona embeddings ni scores entre señales: el tópico emerge por
   **consenso de votos** (lección v1, ADR-0007/0008).
2. Toda evaluación con compuerta pre-registrada; cuantitativa Y cualitativa.
3. Todo resultado se valida por sus datos efectivos.
