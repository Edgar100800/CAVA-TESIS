# EXP-036 F5 — Congelación del método (antes de ver cualquier dato gold)

**Fecha de congelación:** 2026-11-15 · **Aprobado por:** responsables de EXP-036 (decisión transmitida a la
sesión F5) · **Estado del gold de consultas:** no existe; ningún dato gold se ha visto ni creado.

## 1. Lo que queda congelado

| elemento | valor congelado |
|---|---|
| Método candidato F5 | `hybrid_rerank_loc` con niveles **`scene,topic`** (`f5_search.py`, `--method hybrid_rerank_loc --levels scene,topic`) |
| Índice | `exp036/f5/index/` tal como está (hashes en §4) |
| Componentes | BM25 FTS5 (`porter unicode61`) + BGE `bge-base-en-v1.5` (consulta con instrucción, 128 tokens) → RRF k = 60 → top-20 reordenados por `0,5·cos(doc) + 0,5·max cos(fragmento)` → intervalo = evidencia citada por el fragmento ganador (≤ 3 líneas) recortada al documento |
| Filtro | cada consulta busca solo en su película; top-10 evaluado |
| Métricas coprimarias | **R@3** (solape ≥ 1 s con alguna referencia) e **IoU@3** (máximo IoU temporal en el top-3) |
| Control | **R@3[IoU ≥ 0,1]** |
| Secundarias (descriptivas) | R@1, R@5, IoU@1, MRR@10, duración devuelta, latencia media/p95 |
| Comparador | **`exp035b`** (réplica de `CAVA_minimo/scripts/scene_search.py` sobre `CAVA_minimo/outputs/<mov>/scene_index.npz`) con el **mismo** conjunto de consultas y el mismo código de evaluación (`f5_eval.py`) |
| Inferencia | IC 95 % bootstrap (2000 remuestreos, semilla 0) de R@3 e IoU@3 por método; McNemar exacto pareado sobre R@3 (lo que ya calcula `f5_eval.py`) |
| Latencia | CPU, `torch` 8 hilos; criterio < 2 s por consulta |

## 2. Reglas

1. **No se cambia el método, los niveles, los parámetros ni las métricas después de ver el gold.** Todo
   lo que se pruebe sobre el gold y no esté en la tabla anterior se reporta como exploratorio.
2. **El objetivo pre-registrado "Recall@3 ≥ EXP-035 + 15 pp" solo puede afirmarse sobre consultas gold
   humanas**: conjunto `status: gold_reviewed` producido por `f5_queries.py to-gold` a partir de una revisión
   hecha mirando el MP4 (`ref_verified_on_video = Y`), escrita sin ver salidas del sistema. Nunca sobre
   `queries_provisional_v0.json` ni sobre consultas generadas por un modelo.
3. Lectura del criterio: se cumple si R@3(candidato) − R@3(exp035b) ≥ 0,15 sobre el gold. Además se
   informa IoU@3 de ambos. Un R@3 alto con IoU@3 ≈ 0 (intervalos enormes) no se interpreta como éxito
   de localización.
4. El conjunto provisional **sigue siendo provisional**. Sus números (§3) son una línea base interna y no
   cuentan como resultado pre-registrado.
5. Variantes posteriores (p. ej. el piloto de tramos, `TRAMO_PILOT_PREREG.md`) **no** sustituyen al
   candidato. Solo podrían hacerlo mediante una **enmienda fechada a este documento, escrita antes de ver
   cualquier dato gold**, con su propio índice congelado y hashes. Si no hay enmienda, se evalúan sobre el
   gold como exploratorias, junto al candidato congelado.

## 3. Números de referencia (consultas PROVISIONALES, no gold; `results/eval_provisional_v0.json`)

| método | R@3 (IC 95 %) | IoU@3 (IC 95 %) | R@3[IoU≥.1] | R@1 | dur@3 | lat. media/p95 |
|---|---|---|---|---|---|---|
| **candidato** `hybrid_rerank_loc[scene+topic]` | 0,617 [0,483-0,750] | 0,301 [0,220-0,388] | 0,567 | 0,467 | 33 s | 30/31 ms |
| comparador `exp035b` | 0,767 [0,650-0,867] | 0,300 [0,213-0,390] | 0,517 | 0,517 | 1114 s | 30/30 ms |

Por película (R@3 / IoU@3): candidato Endgame 0,733/0,381, Spider 0,500/0,221; exp035b Endgame
0,867/0,342, Spider 0,667/0,257. Con estas consultas provisionales, el candidato **no** supera a exp035b en
R@3 (diferencia −15 pp). Las razones están documentadas en `F5_BASELINE.md` §4: intervalos envolventes y
fuga desde los bloques VJudge en exp035b, y escenas F2 largas en F5.

## 4. Hashes (sha256, 16 primeros caracteres) en el momento de la congelación

```
fb1720153e945641 f5_common.py
e6c292fa6600f110 f5_index.py
626ae8339837b034 f5_search.py
17b957c91f136408 f5_eval.py
b6b873aef07cd025 f5_queries.py
20714005f41c6b3a queries/queries_provisional_v0.json
b6d4301c5de5db92 index/Avengers_Endgame.npz
10423b557314b110 index/Spider_Man.npz
8a81b7c8b0d9a1bf index/Avengers_Endgame.meta.json
d887985095b73c05 index/Spider_Man.meta.json
7186717cb07d0703 index/bm25.sqlite
```

## 5. Ejecución sobre el gold (cuando exista)

```bash
cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python
sha256sum exp036/f5/{f5_common,f5_index,f5_search,f5_eval}.py exp036/f5/index/*   # comparar con §4
$P -I exp036/f5/f5_queries.py to-gold --csv <revisado.csv> --out exp036/f5/queries/queries_gold_v1.json
$P -I exp036/f5/f5_eval.py --queries exp036/f5/queries/queries_gold_v1.json --tag gold_v1
# leer: summary["hybrid_rerank_loc[scene+topic]"] frente a summary["exp035b"]
```
