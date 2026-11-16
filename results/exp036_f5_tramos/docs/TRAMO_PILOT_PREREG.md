# EXP-036 F5 — Pre-registro del piloto de tramos (sub-escenas)

**Fecha:** 2026-11-15 · **Escrito antes de generar ningún brief de tramo y antes de cualquier evaluación de
tramos.** Las consultas siguen siendo las **provisionales** (`queries/queries_provisional_v0.json`): el
resultado sirve solo para decidir si escalar o no. No es un resultado pre-registrado de EXP-036 y no cambia
el candidato congelado (`F5_METHOD_FREEZE.md`).

## 1. Hipótesis

El fallo dominante de F5 son las escenas F2 largas descritas por un único brief con tope de ítems
(`F5_BASELINE.md` §4). Si cada escena larga se describe también por **tramos de ~40 s** con el mismo prompt
F1, los eventos que no cabían en el brief de escena pasan a ser recuperables y localizables.

## 2. Unidad: tramos fijos de 40 s alineados a unidades de 5 s

- Dentro de cada escena seleccionada `[t0, t1]` (de `exp036/outputs/<mov>/escenas.json`): tramos
  consecutivos de 8 unidades (40 s) desde `t0`. Si el resto final dura < 20 s, se une al tramo anterior;
  si dura ≥ 20 s, forma su propio tramo.
- **Por qué no los bloques VJudge:** también duran ~40 s, pero (a) cruzan las fronteras de escena
  (65/66 y 57/57 escenas tienen bloques mixtos) y (b) los intervalos de referencia de las consultas
  provisionales se escribieron en parte con los límites de esos bloques. Tramos alineados a bloques
  inflarían el IoU por coincidencia de rejilla. Los tramos fijos desde `t0` no comparten esa rejilla salvo
  por azar.
- Evidencia de cada tramo: exactamente `f1_briefs.evidence_lines([[a, b]], units, summaries, asr, mixed)`,
  sin modificar F1. Entran los bloques VISION que tocan el tramo (pueden extenderse fuera de él) y las frases
  ASR que lo tocan. `mixed` = los `mixed_blocks` de la escena, es decir, los bloques que cruzan la frontera
  real de escena, no la de tramo.

## 3. Escenas seleccionadas (ventana test) y tramos

| película | escena | intervalo (s) | duración | tramos | consultas provisionales que la tocan | aciertos R@3 del candidato |
|---|---|---|---:|---:|---|---:|
| Spider_Man | S42 | 4955-6060 | 1105 s | 28 | S20-S30 (11) | 3/11 |
| Spider_Man | S30 | 3710-4265 | 555 s | 14 | S01, S02 (2) | 0/2 |
| Avengers_Endgame | S40 | 4645-4930 | 285 s | 7 | A12-A19 (8) | 5/8 |
| Avengers_Endgame | S37 | 4335-4605 | 270 s | 7 | A04-A11 (8) | 5/8 |
| **total** | | | | **56** | **29 (subconjunto L)** | **13/29 = 0,448** |

Selección: son las 4 escenas de la ventana test con más de 250 s. Coinciden con los peores casos de la
línea base. **Sesgo declarado:** se eligieron mirando dónde falla el candidato con estas mismas consultas
(selección por el resultado). Una mejora aquí es necesaria, pero no suficiente, para escalar.

## 4. Generación

- Modelo y prompt idénticos a F1: `Qwen/Qwen2.5-14B-Instruct` en la revisión
  `cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8` (local, `CAVA_minimo/models/hub`, offline), bf16,
  `device_map=auto` con offload a CPU. Se usan `PROMPT`, el registro de personajes y `validate` importados de
  `exp036/scripts/f1_briefs.py` sin modificarlo.
- Greedy (`do_sample=False`). Presupuestos escalonados por unidad: 900 → 1600 → 3500 → 8000 tokens. Se
  reintenta solo si la salida se truncó (misma regla que F1, incluida la enmienda de 8000).
- Ingeniería, sin efecto analítico: generación por lotes con relleno a la izquierda. El tamaño de lote se
  elige por rendimiento con una prueba de velocidad. El greedy por lotes puede diferir numéricamente del
  greedy de lote 1. Se guardan todas las salidas, sean como sean.
- Script: `exp036/f5/tramos/tramo_briefs.py`. Salida: `exp036/f5/tramos/briefs_tramos_<mov>.json`.

## 5. Índice y evaluación

- `exp036/f5/tramos/tramo_index.py` copia el índice congelado y **añade** el nivel `tramo`, con el mismo
  texto, fragmentos, evidencia → tiempo y embebidos BGE. Escribe en `exp036/f5/tramos/index_add/`, sin
  tocar `exp036/f5/index/`.
- Variante secundaria `index_replace/`: igual, pero los 4 documentos de escena largos se excluyen del nivel
  `scene` (los tramos los sustituyen).
- Condiciones, todas con `hybrid_rerank_loc` y los mismos parámetros congelados:
  - **B** (línea base) = candidato congelado, niveles `scene,topic`, índice congelado.
  - **P** (principal) = niveles `scene,topic,tramo` sobre `index_add`.
  - **P_rep** (secundaria) = niveles `scene,topic,tramo` sobre `index_replace`.
- Métricas: R@3, IoU@3, R@3[IoU≥.1], dur@3, latencia media/p95. Se calculan sobre las 60 consultas, sobre el
  subconjunto L (29) y sobre su complemento C (31), con desglose por escena larga. McNemar exacto P vs B.
- Script: `exp036/f5/tramos/tramo_eval.py`. Salida: `exp036/f5/results/eval_tramo_pilot.json`.

## 6. Criterio de éxito (falsable; P frente a B)

El piloto se considera **positivo (escalar)** solo si se cumplen **todas** estas condiciones:

1. R@3 en L: P − B ≥ +0,10 (≥ 3 aciertos netos de 29).
2. IoU@3 en L: P ≥ B.
3. Sin regresión global (60 consultas): aciertos R@3 de P ≥ los de B, y IoU@3 de P ≥ IoU@3 de B − 0,01.
4. Latencia p95 < 2 s.
5. ≥ 95 % de los 56 briefs de tramo con `status: ok` tras los reintentos.

Si falla 1 o 3, el resultado es **negativo**: no se escala y se informa qué implica para F2/F3. Si fallan solo
2 o 5, el resultado es **mixto**: no se escala sin una enmienda que lo justifique. P_rep es descriptiva y no
decide.
