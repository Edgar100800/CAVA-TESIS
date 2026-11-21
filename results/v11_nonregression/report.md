# No regresión del stack v1.1

Estado global: **PASS**

Enmienda a R1 (2026-11-21, `docs/EXPERIMENT_LOG.md`): R1 pasa si la estructura es exactamente igual (ids de tópico, `shots`, `spans`, flags, etiquetas, `versions.json`, filas de `clips.jsonl` salvo campos numéricos) y |Δ| <= 1e-06 en todo campo de punto flotante; se reporta también la igualdad byte a byte.

| comprobación | estado | resultado | commit |
|---|---|---|---|
| R1 | PASS | enmienda: estructura=[0, 0, 0, 0, 0, 0]; máx. abs Δ=1.19e-07; byte a byte=[False, True, False, True, True, True] | `dc4edac` |
| R2 | PASS | 446 estímulos; errores=0 | `519e37b` |
| R3 | PASS | diff no hablante=0; backend=pyannote_c1 | `dc4edac` |
| R4 | PASS | Vox ARI=0.9383188026875701 n=231; AMI ARI=0.974559941883068 n=40 | `519e37b` |
| R5 | PASS | diffs=[0, 0, 0] | `519e37b` |
| R6 | PASS | diff no hablante=0; backend=pyannote_c1 | `519e37b` |
| R7 | PASS | RTTM idéntico=True; exclusivo=True | `519e37b` |
| R8 | PASS | manifiestos=5; errores=0 | `519e37b` |

Los datos y artefactos grandes quedan en `/data/tesis-cava/v11_work/`.
`SKIPPED` no cuenta como aprobado. El GT de R4 solo evalúa; no entra en el pipeline.
