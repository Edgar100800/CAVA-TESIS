# EXP-036 — Revisión de F1 (y F2) como insumo de F5

**Fecha:** 2026-11-15 · **Alcance:** qué puede indexar F5 de los artefactos F1/F2 cerrados, qué falta y
qué implica para el índice, las consultas y la evaluación. Solo lectura sobre F1/F2: no se modificó
ningún artefacto. Cifras recalculadas desde los JSON (script en línea en esta sesión y
`exp036/f5/f5_index.py`, que verifica la reconstrucción de evidencia con un `assert`).

Fuentes: `exp036/H1_CIERRE.md`, `exp036/EXP-036.md`, `exp036/scripts/f1_briefs.py`,
`exp036/scripts/f2_escenas.py`,
`exp036/outputs/{Avengers_Endgame,Spider_Man}/{briefs_f1_topicos,briefs_f1_escenas,escenas}.json`,
`CAVA_minimo/outputs/<mov>/{topic_map.json,work/state.json,work/summaries.json,characters_registry.txt}`.

## 1. Qué aporta F1 a F5

| artefacto | unidades | estado | lo indexable |
|---|---:|---|---|
| `briefs_f1_escenas.json` Endgame | 66 | 66/66 `ok` | brief por escena F2 |
| `briefs_f1_escenas.json` Spider | 57 | 57/57 `ok` | brief por escena F2 |
| `briefs_f1_topicos.json` Endgame | 59 | 59/59 `ok` | brief por tópico default ≥ 30 s |
| `briefs_f1_topicos.json` Spider | 57 | 57/57 `ok` | brief por tópico default ≥ 30 s |

- **Brief estructurado** (`f1_briefs.py:37-42`): `characters[{id,name,description,evidence}]`,
  `actions[{who,what,evidence}]`, `states[{who,state,evidence}]`, `setting[{what,evidence}]`,
  `development` (2-3 frases), `uncertain[]`. En inglés en el 100 % (`not_english` es duro). Útil
  para BM25 y BGE en inglés y para fragmentar en ítems atómicos (acción/estado/ambiente), que F5 usa
  como unidad de rerank.
- **Ids de evidencia con tiempo real.** Los ids `E1..En` son **locales a cada unidad**, no globales,
  pero se reconstruyen de forma determinista con `f1_briefs.evidence_lines(spans, units, summaries,
  asr, mixed)`. `f5_index.py` replica esa función conservando `[t0, t1]` y tipo
  (VISION = bloque VJudge de ~40 s, DIALOGUE = segmento ASR) y **verifica igualdad exacta de las líneas y
  de `n_evidence` en las 239 unidades: 0 discrepancias**. Así cada afirmación del brief se puede llevar
  a un intervalo del film, sin re-ejecutar nada.
- **Intervalos reales.** Escenas F2: un intervalo contiguo `[t0, t1]` (`escenas.json`). Tópicos default:
  lista de `spans` (48/86 tópicos de Endgame y 42/96 de Spider tienen > 1 span). EXP-035b indexaba el
  tópico con la envolvente `spans[0][0]..spans[-1][1]` (`CAVA_minimo/scripts/scene_index.py:39-42`), que
  en la práctica llega a ~85 min (ver §3 y `F5_BASELINE.md`).
- **Avisos por unidad** (`problems.warn`, H1_CIERRE §2): `too_many_evidence_ids` 125/239 (52,3 %),
  `name_not_in_registry` 108/239 (45,2 %), `hedged_identity` 65/239 (27,2 %), `actor_name` 1/239.
  F5 los guarda en `warnings` de cada documento para filtrar o señalar resultados.
- **Enmienda 3500 → 8000 tokens** (H1_CIERRE §3): afecta a `44` (tópico Spider) y `S40` (escena Endgame).
  `S40` (01:17:25-01:22:10, 87 evidencias, 4054 tokens generados) está **dentro de la ventana test** y es
  justamente una de las escenas donde F5 más falla (§2): el brief que cerró a 8000 tiene solo
  **3 acciones** para 285 s de película. La enmienda garantizó un JSON válido, no una cobertura suficiente.

## 2. Qué falta o es riesgoso para F5

1. **F2 sin calibrar** (no existe `gold_*.csv`; parámetros por defecto `w=3, p=85, min_len=3`). Duración de
   las escenas que tocan la ventana test (01:10:00-01:35:00):
   Endgame `[20, 20, 20, 25, 85, 110, 150, 165, 165, 270, 280, 285]` s;
   Spider `[20, 25, 30, 40, 45, 50, 55, 55, 80, 115, 175, 555, 1105]` s.
   Máximos globales 1710 s (Endgame) y 1105 s (Spider). 65/66 y 57/57 escenas contienen ≥ 1 bloque VJudge
   que cruza frontera.
2. **Tope fijo de ítems por brief, sin importar la duración** (`f1_briefs.py:48`: ≤ 6 personajes,
   8 acciones, 6 estados, 4 ambientes). Ejemplos de la ventana test:
   Spider `S42` 1105 s / 155 evidencias → 5 acciones; Spider `S30` 555 s / 237 evidencias → 6 acciones;
   Endgame `S40` 285 s / 87 evidencias → 3 acciones; Endgame `S37` 270 s / 62 evidencias → 6 acciones.
   Los eventos que no entran en el brief **no son recuperables** desde el nivel escena. En la línea base,
   19 de los 21 fallos de `hybrid_rerank` caen en escenas ≥ 165 s (7 solo en Spider `S42`).
3. **Sin F3: identidades no ancladas.** `name_not_in_registry` 45 %; además el modelo escribió el
   **string literal `"null"`** como nombre en 145 personajes (49 + 32 Endgame esc./tóp., 30 + 34 Spider)
   y `null` JSON en otros 361. Hay nombres de rol o descripción como nombre ("Unnamed Man", "Woman",
   "Peter Parker (as Spider-Man)"). F5 normaliza `"null"/"none"/"unknown"` a sin nombre; el resto entra tal
   cual. Los errores de nombre del VJudge se heredan (p. ej. bloque 01:22:00 dice "Black Panther" y
   01:23:20 atribuye a "Captain America" una conversación sobre la Gema del Tiempo).
4. **Tópicos fine: etiqueta sin brief.** 457 (Endgame) y 337 (Spider) tópicos fine con `label` de una
   frase y spans, sin brief ni evidencia citada. Tópicos default < 30 s: 27 + 39 sin brief (solo etiqueta).
5. **Listas de evidencia ruidosas.** Ítems con > 3 ids: 32 % (Endgame esc.), 19 % (Endgame tóp.),
   34 % (Spider esc.), 34 % (Spider tóp.). p90 = 13 ids por ítem en escenas de Endgame, máx. 126 ids en un
   ítem. La envolvente de esos ids puede cubrir toda la escena: localizar por evidencia citada exige
   recortar (F5 se queda con las ≤ 3 líneas citadas más afines a la consulta).
6. **Fuente compartida.** Briefs, etiquetas y bloques EXP-035 salen del mismo ASR + VJudge. Toda consulta
   escrita mirando esa evidencia (como el conjunto provisional de F5) está sesgada a favor del sistema y,
   más aún, del nivel `block` de EXP-035, que indexa el resumen VJudge literal.

## 3. Implicaciones concretas para F5

**Campos del índice** (implementados en `exp036/f5/f5_index.py`): `movie`, `level`
(`scene|topic|fine`), `unit`, `spans` reales (lista, no envolvente), `t0/t1` + `hms`, `dur`,
`topic_dominante`, `pureza_topico`, `mixed`/`n_mixed_blocks` (escenas), `names` (normalizados),
`warnings`, `n_evidence`, `evidence_ids` citados, `uncertain` (guardado, **no** indexado), texto
estructurado; fragmentos por ítem con sus ids → `[t0, t1]`; líneas de evidencia citadas con su tiempo.

**Tipos de consulta** que F1 soporta razonablemente: acción ("X hace Y"), lugar/ambiente, estado
emocional/físico, entidad por descripción. Débiles hasta F3: entidad **por nombre** (identidades no
ancladas, 45 % de avisos de nombre) y consultas por **diálogo literal** (los briefs parafrasean; en la línea
base, `dialogue` es el tipo peor con R@3 = 0,40 en todos los métodos de nivel escena).

**Evaluación:**
- R@3 con solape ≥ 1 s **se gana con intervalos largos**: el nivel `scene` de EXP-035 (envolventes de
  tópicos multi-span, duración media devuelta 4334 s) da R@3 = 0,967 con IoU@3 = 0,022. Reportar siempre
  IoU@k y la duración devuelta junto a R@3; propuesta para el gold: R@3 **y** IoU@3 como métricas
  coprimarias, más R@3[IoU ≥ 0,1] como control (post-hoc en esta línea base).
- EXP-035 **nunca midió Recall@3** sobre un conjunto de consultas (solo una demo de n = 5,
  `CAVA_minimo/docs/EXP-035_escenas_largas.md`). El "EXP-035 + 15 pp" pre-registrado exige medir EXP-035
  con el mismo gold y el mismo código: `f5_search.py` ya incluye `exp035b` (réplica de `scene_search.py`
  sobre su `scene_index.npz`, solo lectura).
- Estratificar por duración de la escena correcta (la cobertura del brief depende de ella) y por tipo.
- Línea base de azar por escenas F2 y techo de IoU de una escena única (0,194 en el conjunto provisional):
  con F2 actual, ningún método de nivel escena sin localización puede pasar ese IoU medio.

**Dependencias de F3 (no implementado):** nombres anclados (ASR + x-vector, `persona_#`) para consultas por
entidad; re-brief de escenas largas o partición en tramos (requiere F2 calibrado o generación nueva, fuera
de alcance aquí). `f5_index.py --briefs-escenas '<ruta con {mov}>' --out <otro_dir>` indexa briefs F3 sin
cambiar código, siempre que conserven el esquema y la numeración de `evidence_lines`.
