# EXP-036 F0–F5 — resultados (copia de texto)

**Origen:** `/data/tesis-cava/exp036` (máquina .56 del laboratorio, sin git).
**Sincronizado:** 2026-11-16.
**Estado:** F1 239/239 ok (0 truncados); barrido 64/64; F5 candidato B;
cobertura completa de tramos 501/501 válidos → **F no adoptado** (falla A4 por 1 consulta).

> **Aviso de numeración.** En el repo, `results/exp036.json` y `logs/exp036.log`
> corresponden a otro EXP-036 (detector de segunda voz / umbrales `single_k1`).
> Esta carpeta es el protocolo **F0–F5 de escenas verificables** del mismo nombre.
> Si se renombra en el manuscrito, hacerlo aquí y en `docs/`.

## Contenido

- `docs/`: TRAMO_FULL, TRAMO_PILOT, TRAMO_PILOT_PREREG, F5_BASELINE, F5_METHOD_FREEZE,
  F5_METHOD_AMENDMENT_v1, F1_REVIEW_F5, BASELINE_A2SUMM.
- `results/`: evaluaciones (provisional v0, piloto, full v1 inválida, full v2 válida)
  en JSON/CSV/log.
- `briefs/`: briefs de los 501 tramos (fusión v2).
- `state/`: merge/adoption/orchestrator/jobs/hashes, LECTURA.md, manifiestos de reparación.
- `code/`: generador, índice, evaluación, orquestador, merge y reporte (texto, congelado).
- `logs/`: log del orquestador (historia de la corrida distribuida).
- `baseline/`: métricas del baseline A2Summ (checkpoints oficiales, TVSum/SumMe).

## Números de referencia

| conjunto | valor |
|---|---|
| F1 | 239/239 ok, 0 truncados |
| barrido | 64/64 condiciones |
| B (candidato) | R@3 0.617 / IoU@3 0.301 / dur 33 s / 31 ms |
| P (piloto) | R@3 0.767 / IoU@3 0.372 |
| F (full 501) | R@3 0.717 / IoU@3 0.377 / R@1 0.633 / dur 24 s |
| A4 | F 23 vs B 24 en C → **no adoptado** |
| A2Summ TVSum | 0.6316 (paper 0.634); random 0.5664; τ 0.2505 |
| A2Summ SumMe | 0.5490 (paper 0.550); random 0.4028; τ 0.0960 |

## Lo que NO está aquí

- Índices `.npz` (binarios): hashes en `state/full_index_hashes.txt` y `F5_METHOD_FREEZE.md`.
- Vídeos, frames, clips y modelos.
- Paquetes completos: `EXP036_texto_20261116_v2.zip` y `EXP036_F5_tramos_20261115.zip`
  (en `~/Tesis/CAVA/`, sin trackear; usar release si se quieren publicar).
