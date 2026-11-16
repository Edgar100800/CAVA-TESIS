# EXP-036 F5 — Línea base interna de búsqueda (consultas PROVISIONALES)

**Fecha:** 2026-11-15 · **Estado:** índice construido y evaluado; **no es el test pre-registrado.**

> **Aviso.** Las 60 consultas (`queries/queries_provisional_v0.json`) las escribió el agente de F5 a partir
> de la evidencia automática (ASR + resúmenes VJudge) de la ventana test 01:10:00-01:35:00, **antes** de
> construir el índice y sin leer los briefs F1 de esa ventana. Los intervalos de referencia son los
> tiempos de esa evidencia y **no se verificaron en el MP4**. No hay gold humano, ni segundo anotador, ni
> kappa. Ningún número de este documento sirve para afirmar el criterio pre-registrado
> "Recall@3 ≥ EXP-035 + 15 pp": eso solo podrá decirse con el conjunto gold (§6).

## 1. Qué se construyó

| fichero | función |
|---|---|
| `f5_common.py` | intervalos (unión, IoU, solape), BGE local, texto/fragmentos de brief, evidencia → tiempo |
| `f5_index.py` | índice por película: escenas F2 + brief F1 (nivel principal), tópicos default (+ brief F1 si ≥ 30 s), tópicos fine (etiqueta) |
| `f5_search.py` | búsqueda: `bm25`, `bge`, `hybrid`, `hybrid_rerank`, `hybrid_rerank_loc`, `exp035b*`; CLI y `--selftest` |
| `f5_eval.py` | R@1/3/5, IoU@1/3, MRR@10, duración devuelta, latencia, IC bootstrap, McNemar exacto |
| `f5_queries.py` | plantilla CSV de revisión humana y conversión CSV revisado → JSON gold; `--selftest` |
| `f5_smoke.py` | prueba de humo sobre el índice real |
| `queries/queries_provisional_v0.json` | 60 consultas provisionales (30/película; acción 21, estado 12, entidad 10, diálogo 10, lugar 7) |
| `queries/review_template_v0.csv` | plantilla de revisión: las 60 filas + 10 filas `NEW` por película |
| `index/<mov>.npz`, `index/<mov>.meta.json`, `index/bm25.sqlite` | artefactos del índice (≈ 27 MB) |
| `results/eval_provisional_v0.{json,log}`, `results/eval_provisional_v0_per_query.csv` | resultados medidos |

Contenido del índice (medido): Endgame 66 escenas + 86 tópicos default + 457 fine, 2164 fragmentos,
2143 líneas de evidencia citadas; Spider 57 + 96 + 337, 1879 fragmentos, 2090 líneas. Texto de escena:
mediana 172/181 tokens, máximo 416/435 (ninguno trunca a 512). Ids de evidencia de las 239 unidades F1
reconstruidos con 0 discrepancias (assert en `f5_index.py`).

## 2. Decisiones de diseño (fijadas antes de evaluar salvo donde se indica)

- **Documento** = texto estructurado del brief (`Characters/Actions/States/Setting/Development`), sin
  `uncertain`. Los nombres `"null"/"none"/"unknown"` se tratan como sin nombre.
- **BM25**: SQLite FTS5 (`porter unicode61`), `bm25()` por defecto (k1 = 1,2, b = 0,75); consulta = OR de
  términos sin stopwords. FTS5 disponible (SQLite 3.45.1): no hizo falta BM25 propio.
- **BGE**: `BAAI/bge-base-en-v1.5` local (`CAVA_minimo/models/hub`, offline), CLS + L2 como
  `narrative_eval.BgeEmbedder` (no se importa porque ese módulo importa `topicagg`). Documentos a 512 tokens;
  consultas con la instrucción oficial de bge-v1.5 para búsqueda, rellenadas a 128 tokens fijos.
- **Fusión**: RRF con k = 60 sobre los rankings BM25 y BGE. Se eligió RRF porque no requiere normalizar
  escalas de score ni ajustar pesos (no hay dev de consultas para ajustarlos).
- **Rerank** (no hay cross-encoder local): top-20 de RRF reordenado por
  `0,5·cos(consulta, doc) + 0,5·max cos(consulta, fragmento del brief)`. El reranker listwise con Qwen-14B
  queda como trabajo futuro (es GPU y su latencia superaría 2 s).
- **Localización** (`_loc`): el intervalo devuelto es la envolvente de las líneas de evidencia citadas por el
  fragmento ganador (las ≤ 3 más afines a la consulta si cita más), recortada a los spans del documento.
- **Comparación EXP-035**: `exp035b` replica `CAVA_minimo/scripts/scene_search.py` sobre su
  `scene_index.npz` (solo lectura): BGE sin instrucción, niveles `scene+block+topic` mezclados.
  `exp035b_scene` usa solo su nivel scene y `exp035b_noblock` usa scene+topic.
- **Filtro de película**: cada consulta busca solo en su película.
- **CPU**: `torch.set_num_threads(8)`. Esta máquina (Core Ultra 9 285K) tiene 8 núcleos P + 16 E sin SMT.
  Con 24 hilos, el embebido de la consulta se quedaba en ~1,3 s de forma intermitente (medido); con 8 hilos
  es estable. Es una decisión de despliegue y no cambia ningún ranking (verificado: métricas idénticas).

## 3. Resultados (medidos; 60 consultas provisionales; nivel `scene` salvo indicación)

`dur@3` = duración media del intervalo devuelto en el top-3. `R@3[IoU≥.1]` es **suplementaria post-hoc**:
acierto que además exige IoU ≥ 0,1. IC 95 % por bootstrap (2000 remuestreos).

| método | R@1 | R@3 (IC 95 %) | R@5 | R@3[IoU≥.1] | IoU@1 | IoU@3 | MRR@10 | dur@3 (s) | lat. media/p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0,400 | 0,583 [0,467-0,700] | 0,650 | 0,467 | 0,099 | 0,145 | 0,499 | 175 | <1/<1 |
| bge | 0,333 | 0,600 [0,483-0,717] | 0,683 | 0,467 | 0,076 | 0,139 | 0,469 | 246 | 30/32 |
| hybrid (RRF) | 0,400 | 0,600 [0,483-0,733] | 0,683 | 0,483 | 0,084 | 0,150 | 0,517 | 213 | 30/30 |
| hybrid + rerank | **0,433** | **0,650** [0,533-0,767] | 0,683 | 0,500 | 0,100 | 0,147 | 0,549 | 241 | 30/30 |
| hybrid + rerank + loc | 0,417 | 0,583 [0,450-0,717] | 0,600 | 0,500 | **0,196** | **0,265** | 0,506 | **44** | 30/30 |
| *variantes (secundarias)* | | | | | | | | | |
| hybrid+rerank+loc, scene+topic | 0,467 | 0,617 [0,483-0,750] | 0,683 | **0,567** | 0,196 | **0,301** | 0,556 | 33 | 30/31 |
| hybrid+rerank+loc, scene+topic+fine | 0,483 | 0,617 [0,500-0,733] | 0,683 | 0,567 | 0,176 | 0,297 | 0,572 | 34 | 32/34 |
| hybrid+rerank+loc, 1 línea (post-hoc) | 0,333 | 0,483 [0,350-0,617] | 0,500 | 0,400 | 0,167 | 0,229 | 0,415 | 20 | 66/135 |
| *referencias EXP-035 (mismas consultas)* | | | | | | | | | |
| exp035b (scene+block+topic) | 0,517 | 0,767 [0,650-0,867] | 0,867 | 0,517 | 0,221 | 0,300 | 0,648 | 1114 | 30/30 |
| exp035b_noblock (scene+topic) | 0,567 | 0,867 [0,783-0,950] | 1,000 | 0,033 | 0,009 | 0,021 | 0,741 | 3619 | 30/30 |
| exp035b_scene | 0,700 | 0,967 [0,917-1,000] | 1,000 | 0,033 | 0,011 | 0,022 | 0,831 | 4334 | 30/30 |
| *sin sistema* | | | | | | | | | |
| azar, 3 escenas F2 (esperanza exacta) | — | 0,055 | — | — | — | — | — | — | — |
| techo: mejor escena F2 única (IoU) | — | — | — | — | — | 0,194 | — | — | — |

Por película (R@3 / IoU@3): hybrid+rerank Endgame 0,633/0,146, Spider 0,667/0,148;
hybrid+rerank+loc Endgame 0,600/0,316, Spider 0,567/0,214; exp035b Endgame 0,867/0,342,
Spider 0,667/0,257. Por tipo, R@3 de hybrid+rerank: lugar 0,857, entidad 0,800, acción 0,714, estado 0,500,
diálogo 0,400 (n = 7/10/21/12/10).

Pruebas pareadas (McNemar exacto sobre R@3; "x/y" = solo x acierta / solo y acierta):
hybrid vs bge 4/4 (p = 1,0); hybrid vs bm25 4/3 (p = 1,0); hybrid+rerank vs hybrid 6/3 (p = 0,51);
hybrid+rerank vs exp035b 7/14 (p = 0,19); hybrid+rerank+loc vs exp035b 6/17 (p = 0,035);
hybrid+rerank vs exp035b_noblock 4/17 (p = 0,007).

**Latencia** (CPU, 8 hilos, modelo ya cargado): 30 ms de media y p95 ≤ 35 ms en todos los métodos
principales, frente al límite de 2 s. Carga del modelo e índice: 2,0 s. Primera consulta tras cargar:
196 ms. La prueba de humo mide 39 ms para `hybrid_rerank_loc`. Embebido del índice completo: 83 s en CPU
(una vez).

## 4. Lectura

1. **La señal existe pero es modesta.** Los métodos de nivel escena aciertan en el top-3 entre el 58 y el
   65 % (azar: 5,5 %). BM25, BGE y RRF quedan empatados dentro del ruido (n = 60). El rerank por fragmentos
   suma +5 pp de R@3 y +3 pp de R@1, sin significación estadística.
2. **La localización por evidencia es lo que más mueve el IoU.** IoU@3 pasa de 0,147 a 0,265 y la duración
   devuelta baja de 241 a 44 s; con tópicos, IoU@3 sube a 0,301. El coste son 4 aciertos de R@3 (A26, S01,
   S12, S27): el recorte a la evidencia citada deja de solapar la referencia aunque la escena era correcta.
   El IoU@3 localizado ya supera el **techo de una escena F2 entera (0,194)**.
3. **EXP-035b gana en R@3 con estas consultas, por dos artefactos que conviene separar:**
   - *Intervalos enormes:* sus niveles scene/topic usan la envolvente del tópico (duración media devuelta
     3600-4300 s). Por eso `exp035b_scene` saca R@3 = 0,967 con IoU@3 = 0,022 y R@3[IoU≥.1] = 0,033.
   - *Fuga de la fuente de las consultas:* su nivel `block` indexa el resumen VJudge literal, que es de
     donde se escribieron las consultas. De los 69 resultados de su top-3 que solapan la referencia, 34 son
     bloques (22 tópicos, 13 escenas).
   Con control de precisión (R@3[IoU≥.1]), F5 scene+topic+loc da 0,567 frente a 0,517 de exp035b, e IoU@3
   0,301 frente a 0,300, devolviendo intervalos 34 veces más cortos (33 s frente a 1114 s). **Ninguna de
   estas diferencias es concluyente con n = 60 provisional.**
4. **Fallo dominante: escenas F2 largas con brief de tamaño fijo.** 19 de los 21 fallos de hybrid+rerank
   tienen como escena correcta una de ≥ 165 s: Spider `S42` (1105 s) 7, Endgame `S40` (285 s, la unidad de
   la enmienda a 8000 tokens, solo 3 acciones en su brief) 5, Endgame `S37` (270 s) 2, `S44` 2, `S41` 1,
   Spider `S30` (555 s) 1 y `S36` 1. Los 2 restantes caen en escenas de 85 y 50 s. 16 consultas fallan con
   los 5 métodos F5. El evento simplemente no está en el brief. Esto no se arregla en el ranking: hace falta
   F2 calibrado (escenas más cortas) o un nivel "tramo" con su propio brief (F3/re-brief). Indexar la
   evidencia cruda arreglaría la cobertura, pero volvería a introducir la fuga del punto 3 con estas
   consultas.
5. **Diálogo literal** es el tipo más débil a nivel escena (R@3 = 0,40), porque los briefs parafrasean. Los
   tópicos ayudan (0,70 con scene+topic).

## 5. Limitaciones

- Consultas y referencias provisionales escritas por un solo autor (agente) desde la misma evidencia
  automática que generó los briefs: estimación optimista y sin verificar en video.
- n = 60. Los IC 95 % de R@3 tienen ±12 pp de ancho, así que las diferencias de 5 pp entre métodos no se
  pueden resolver.
- Las variantes `1 línea` y `R@3[IoU≥.1]` se añadieron después de ver resultados (marcadas post-hoc). Los
  hilos (8) y el relleno de consultas (128) se fijaron tras observar latencias, no rankings.
- Pesos del rerank (0,5/0,5), k de RRF (60), 20 candidatos y ≤ 3 líneas de localización son valores a
  priori, no ajustados. Ajustarlos exigiría un conjunto dev separado del gold.
- No hay cross-encoder ni reranker LLM. El "rerank" es BGE por fragmentos.
- F2 sin calibrar y F3/F4 no implementados: los nombres no están anclados.

## 6. Siguiente paso humano: revisión gold de consultas

1. Abrir `queries/review_template_v0.csv` (copiarlo como `review_v1_<anotador>.csv`). Mirar el MP4 de la
   ventana test **sin** mirar resultados del sistema ni briefs. Por fila: `keep` = Y / EDIT / N; si EDIT,
   rellenar `reviewer_query` y/o `reviewer_ref_*_hms` con el tramo donde ocurre el evento en pantalla;
   `ref_verified_on_video` = Y; `reviewer` = iniciales. Añadir consultas propias en las filas `NEW` (fijar
   `type` ∈ entity/action/place/state/dialogue y `keep` = NEW) hasta 30 por película, priorizando eventos
   visuales no dichos en el diálogo para reducir la fuga.
2. Segundo anotador en ≥ 10 consultas para medir el acuerdo de intervalos.
3. Convertir y evaluar (mismo código, incluye EXP-035b para el criterio + 15 pp):

```bash
cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python
$P -I exp036/f5/f5_queries.py to-gold --csv exp036/f5/queries/review_v1_<anotador>.csv \
   --out exp036/f5/queries/queries_gold_v1.json
$P -I exp036/f5/f5_eval.py --queries exp036/f5/queries/queries_gold_v1.json --tag gold_v1
```

Propuesta para fijar **antes** de correr el gold: método principal = `hybrid_rerank_loc` (niveles
scene+topic); comparador = `exp035b`; métricas coprimarias R@3 e IoU@3, con R@3[IoU≥.1] como control.

## 7. Comandos exactos (reproducción; CPU, sin GPU, sin descargas)

```bash
cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python
# autopruebas (sin modelo)
$P -I exp036/f5/f5_search.py --selftest
$P -I exp036/f5/f5_queries.py --selftest
# índice (≈ 85 s CPU; escribe solo en exp036/f5/index/)
$P -I exp036/f5/f5_index.py --device cpu
# humo sobre el índice real
$P -I exp036/f5/f5_smoke.py
# búsqueda interactiva
$P -I exp036/f5/f5_search.py "Thor talks with his mother in Asgard" --movie Avengers_Endgame --topk 5
$P -I exp036/f5/f5_search.py "Spider-Man fights the Hulk" --method hybrid_rerank_loc --levels scene,topic --json
# evaluación de esta línea base
$P -I exp036/f5/f5_eval.py --queries exp036/f5/queries/queries_provisional_v0.json --tag provisional_v0
# plantilla de revisión
$P -I exp036/f5/f5_queries.py template --queries exp036/f5/queries/queries_provisional_v0.json \
   --out exp036/f5/queries/review_template_v0.csv
```

La reconstrucción del índice desde cero reprodujo todas las métricas de la tabla de §3 sin diferencias
(comparación automática de `summary` entre dos ejecuciones).
