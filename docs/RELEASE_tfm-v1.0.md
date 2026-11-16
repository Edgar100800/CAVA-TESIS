# TFM v1.0 — paquete de evidencia (EXP-035 / EXP-036-F5 / baseline A2Summ)

Fecha: 2026-11-16 · Tag: `tfm-v1.0`

Artefactos de **solo texto** para reproducir y auditar los resultados de la tesis, sin
vídeos, modelos ni índices binarios.

## Contenido del release

| Activo | Qué es |
|---|---|
| `EXP036_F5_tramos_20261115.zip` | EXP-036-F5: briefs de tramos (piloto + cobertura completa 501), docs, resultados de búsqueda, hashes del índice congelado |
| `EXP036_texto_20261116.zip` | EXP-035 + EXP-036 (F0/F1/F2/barrido): artefactos de texto |
| `EXP036_texto_20261116_v2.zip` | Igual que el anterior, con el barrido 64/64 completo y correcciones |
| `*.zip.sha256` | Verificación de integridad |

## Números de referencia

- F1: 239/239 ok, 0 truncados, 0 problemas duros.
- Barrido: 64/64 condiciones.
- Búsqueda (60 consultas provisionales, sin gold): R@3 0.617, IoU@3 0.301, 33 s, 31 ms.
- Tramos: 501/501 válidos; **F no adoptado** (A4: 23 vs 24 en C).
- A2Summ: TVSum 0.6316 (paper 0.634), SumMe 0.5490 (paper 0.550); aleatorio TVSum 0.5664.

## Fuera del release

- Índices `.npz` (hashes en `results/exp036_f5_tramos/state/full_index_hashes.txt`).
- Vídeos, frames, clips, checkpoints (se regeneran con los scripts del repo).
- `exports/` y `films/` (no se publican).

## Identificadores

Ver `docs/EXP_IDS.md`: EXP-036V (segunda voz) ≠ EXP-036-F5 (tramos verificables).
