# EXP-036 F5 — Enmienda v1 a la congelación del método

**Fecha:** 2026-11-15 15:58 (-05) · **Escrita antes de generar la cobertura completa de tramos y antes de
ver cualquier dato gold.**
**Estado del gold: no existe ningún conjunto gold de consultas; ningún dato gold se ha visto, creado ni
simulado.** `exp036/f5/queries/` contiene solo `queries_provisional_v0.json` y `review_template_v0.csv`.

Esta enmienda modifica `F5_METHOD_FREEZE.md` según su §2.5. Todo lo que no se cambia aquí sigue vigente
(métricas, comparador, reglas, lectura del criterio + 15 pp).

## 1. Candidato condicional

| | valor |
|---|---|
| Candidato condicional **F** | `hybrid_rerank_loc` con niveles **`scene,topic,tramo`**, diseño **"añadir"** (las escenas F2 se conservan), sobre el índice de cobertura completa `exp036/f5/tramos/full/index_add/` |
| Tramos | 40 s fijos desde `t0` de cada escena F2 (resto < 20 s unido al anterior), para **todas** las escenas de ambas películas: **501 tramos** (56 del piloto + 445 nuevos) |
| Briefs | mismo modelo, revisión, prompt, validador y decodificación que el piloto (`tramos/tramo_briefs.py`), lote 8 |
| Resto | parámetros de búsqueda idénticos al candidato congelado (RRF k = 60, 20 candidatos, rerank 0,5/0,5, ≤ 3 líneas de localización, BGE con 8 hilos) |
| Si no se adopta | el candidato sigue siendo **B** = `hybrid_rerank_loc[scene,topic]` sobre `exp036/f5/index/` (hashes en `F5_METHOD_FREEZE.md` §4) y los tramos quedan como **exploratorios** |

## 2. Condiciones de adopción

Se evalúan una sola vez, automáticamente, con `tramos/full_report.py`, sobre las mismas 60 consultas
**provisionales**. F se compara con B (congelado) y con P (piloto, `tramos/index_add/`).
L = las 29 consultas de las 4 escenas del piloto; C = las 31 restantes (las mismas definiciones que en
`TRAMO_PILOT_PREREG.md`). F pasa a ser el candidato para el gold **solo si se cumplen todas**:

| # | condición |
|---|---|
| A1 | Cobertura: el manifiesto tiene exactamente 501 tramos; ≥ 95 % (≥ 476) con brief `ok` y evidencia verificada; las particiones son disjuntas; ninguna unidad inventada ni duplicada |
| A2 | Confirma el piloto: aciertos R@3 en L de F ≥ los de B + 3; IoU@3 en L de F ≥ el de B |
| A3 | Sin regresión global: aciertos R@3 de F (60) ≥ los de B; IoU@3 de F ≥ el de B − 0,01 |
| A4 | **Desplazamiento eliminado (C no peor que B):** aciertos R@3 en C de F ≥ los de B; IoU@3 en C de F ≥ el de B − 0,01 |
| A5 | Latencia p95 < 2 s |

Si falla cualquiera, F **no** se adopta (candidato = B; tramos exploratorios).

## 3. Métricas y comparador (sin cambios)

Coprimarias: **R@3** e **IoU@3**. Control: **R@3[IoU ≥ 0,1]**. Comparador: **`exp035b`** con el mismo
conjunto y el mismo código. El objetivo "Recall@3 ≥ EXP-035 + 15 pp" solo puede afirmarse sobre consultas
gold humanas (`F5_METHOD_FREEZE.md` §2.2).

## 4. Congelación del índice F

Tras construir `tramos/full/index_add/`, el orquestador escribe sus sha256 en
`tramos/full/full_index_hashes.txt` y los copia en `TRAMO_FULL.md`. **Esos hashes forman parte de esta
enmienda** y quedan fijados antes de cualquier gold. Cualquier reconstrucción posterior que cambie un hash
invalida el candidato F hasta una nueva enmienda, también anterior al gold.

## 5. Evaluación sobre el gold (cuando exista)

```bash
cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python
$P -I exp036/f5/f5_eval.py --queries exp036/f5/queries/queries_gold_v1.json --tag gold_v1          # B y exp035b
$P -I exp036/f5/tramos/tramo_eval.py --queries exp036/f5/queries/queries_gold_v1.json \
   --conds "B=exp036/f5/index:scene,topic" "F=exp036/f5/tramos/full/index_add:scene,topic,tramo" --tag gold_v1_F
```

Se lee el candidato vigente según `tramos/full/adoption.json`: F si `adopted: true`, B si no.
