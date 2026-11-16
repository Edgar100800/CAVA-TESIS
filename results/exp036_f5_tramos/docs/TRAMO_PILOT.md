# EXP-036 F5 — Piloto de tramos: resultados

**Fecha:** 2026-11-15 · **Pre-registro:** `TRAMO_PILOT_PREREG.md`, escrito antes de generar.
**Veredicto pre-registrado: POSITIVO.** Se cumplen los 5 criterios.
**Recomendación: escalar a cobertura completa por tramos**, previa enmienda de congelación (§7).

> Las consultas son las **provisionales** (`queries/queries_provisional_v0.json`), no gold. Este piloto
> decide si escalar. No es un resultado pre-registrado de EXP-036 ni cambia el candidato congelado
> (`F5_METHOD_FREEZE.md`).

## 1. Generación (medida)

| concepto | valor |
|---|---|
| tramos | 56 (Endgame S37 7, S40 7; Spider S30 14, S42 28), fijos de 40 s desde `t0` de la escena |
| estado | **56/56 `ok`**, todos en el primer intento (presupuesto 900); 0 truncados, 0 reintentos |
| tokens generados | mediana 431, máx. 817; prompts: mediana 921, máx. 1566 tokens |
| modelo | Qwen2.5-14B-Instruct `cf98f3b3…`, bf16, `device_map=auto` (15 GiB en GPU + offload a CPU), greedy, prompt F1 |
| GPU | NVIDIA RTX PRO 4000 Blackwell (24 GB), un único trabajo cada vez |
| tiempo GPU | lote de prueba 8 tramos: 546,7 s · resto 48 tramos: 61,0 min · **total 70,1 min de generación** (+ 6 s de carga) |
| coste | **75 s de GPU por tramo** (lote 8); 5,3-6,4 tok/s agregados; ~1,04 s por paso de decodificación |
| logs | `tramos/logs/gen_run1.log`, `tramos/logs/gen_run2.log`, `tramos/gpu_time.jsonl` |

**Lote 8, elegido por medición.** El lote de prueba hizo 525 pasos en 547 s. La decodificación está limitada
por el offload: cada paso transmite los pesos alojados en CPU, sin importar el tamaño del lote. Lote 16 no se
midió. Con ~8 GB libres en GPU, un OOM haría caer el script a lote 1 (~6-7 min por tramo), así que no compensaba
arriesgar para ganar ~25 min.

**Validación de los 56.** El JSON tiene las 5 claves obligatorias y `validate()` de F1 no da problemas duros.
Los ids de evidencia se reconstruyen exactamente con `f1_briefs.evidence_lines` (assert en `tramo_index.py`):
538 fragmentos y 482 líneas de evidencia citadas, todas con intervalo real que toca su tramo. **Ninguno se
excluyó.** El índice congelado `exp036/f5/index/` sigue intacto (hashes iguales antes y después).

**Cobertura frente al brief de escena F1** (ítems totales):

| escena | dur. | brief F1 de escena: acciones/estados/ambiente | tramos: acciones/estados/ambiente |
|---|---:|---|---|
| Spider S42 | 1105 s | 5 / 4 / 4 | **67 / 50 / 39** |
| Spider S30 | 555 s | 6 / 4 / 4 | 34 / 28 / 23 |
| Endgame S40 | 285 s | 3 / 4 / 4 | 28 / 17 / 14 |
| Endgame S37 | 270 s | 6 / 5 / 4 | 17 / 12 / 10 |

## 2. Resultados (60 consultas provisionales; `hybrid_rerank_loc`, parámetros congelados)

B = candidato congelado (`scene,topic`, índice congelado); P = `scene,topic,tramo` sobre `tramos/index_add`;
P_rep = igual, pero sin los 4 documentos de escena largos (`tramos/index_replace`). L = 29 consultas cuya
referencia toca una escena seleccionada; C = las 31 restantes. IC 95 % por bootstrap.

| cond. | subconjunto | n | R@3 (IC 95 %) | IoU@3 (IC 95 %) | R@3[IoU≥.1] | R@1 | MRR@10 | dur@3 | lat. media/p95 |
|---|---|---:|---|---|---|---|---|---|---|
| B | todas | 60 | 0,617 [0,483-0,750] | 0,301 [0,220-0,388] | 0,567 | 0,467 | 0,556 | 33 s | 31/31 ms |
| **P** | todas | 60 | **0,767** [0,650-0,867] | **0,372** [0,289-0,456] | **0,667** | 0,617 | 0,706 | 30 s | 31/31 ms |
| P_rep | todas | 60 | 0,750 [0,633-0,850] | 0,341 [0,260-0,423] | 0,633 | 0,600 | 0,687 | 29 s | 31/31 ms |
| B | L (largas) | 29 | 0,448 [0,276-0,621] | 0,200 [0,103-0,310] | 0,448 | 0,345 | 0,424 | 33 s | 31/31 ms |
| **P** | L (largas) | 29 | **0,828** [0,690-0,966] | **0,390** [0,279-0,505] | **0,724** | 0,690 | 0,764 | 27 s | 31/31 ms |
| P_rep | L (largas) | 29 | 0,793 [0,621-0,931] | 0,326 [0,220-0,436] | 0,655 | 0,655 | 0,724 | 26 s | 31/31 ms |
| B | C (resto) | 31 | 0,774 [0,613-0,903] | 0,395 [0,275-0,520] | 0,677 | 0,581 | 0,680 | 32 s | 31/34 ms |
| P | C (resto) | 31 | 0,710 [0,548-0,871] | 0,356 [0,233-0,483] | 0,613 | 0,548 | 0,651 | 32 s | 31/31 ms |

B reproduce exactamente al candidato congelado (0,617 / 0,301).
McNemar exacto sobre R@3, P frente a B: todas 11/2 (p = 0,023); L 11/0 (p = 0,001); C 0/2 (p = 0,5).

**Por escena larga** (R@3 / IoU@3):

| escena | n | B | P | P_rep |
|---|---:|---|---|---|
| Spider S42 (1105 s) | 11 | 0,273 / 0,176 | **0,636 / 0,349** | 0,545 / 0,283 |
| Spider S30 (555 s) | 2 | 0,000 / 0,000 | **1,000 / 0,694** | 1,000 / 0,694 |
| Endgame S40 (285 s) | 8 | 0,625 / 0,183 | **0,875 / 0,227** | 0,875 / 0,128 |
| Endgame S37 (270 s) | 8 | 0,625 / 0,301 | **1,000 / 0,534** | 1,000 / 0,490 |

**Criterio pre-registrado (P frente a B):**

| # | condición | medido | ¿cumple? |
|---|---|---|---|
| 1 | R@3 en L: +0,10 (≥ 3 aciertos netos) | 0,448 → 0,828, **+11 aciertos netos** | sí |
| 2 | IoU@3 en L: P ≥ B | 0,200 → 0,390 | sí |
| 3 | sin regresión global | aciertos 37 → 46; IoU@3 0,301 → 0,372 | sí |
| 4 | latencia p95 < 2 s | 31 ms | sí |
| 5 | ≥ 95 % de briefs `ok` | 56/56 | sí |

**Los 21 fallos de `hybrid_rerank` a nivel escena** (de `F5_BASELINE.md`): P recupera **14**. 6 ya los
recuperaba B al añadir tópicos (A13, A15, A21, A22, A27, S22) y **8 son nuevos gracias a los tramos** (A08,
A10, A14, A17, S02, S24, S28, S29). De los 15 fallos situados en las 4 escenas largas, P recupera 11. Siguen
fallando 7: A12, A28, S11, S14, S25, S26 y S30.

## 3. Fallos y riesgos observados

- **Desplazamiento fuera de las escenas con tramos (C: −2 aciertos, S13 y S19).** Tramos densos de S42/S30
  pasan por delante de la escena correcta, más corta. En S19 el tramo ganador `S42_T00` (01:22:35) es
  contiguo a la referencia (01:21:20-01:21:54). La causa es la **asimetría**: solo 4 escenas tienen tramos.
  Cubrir todas las escenas debería neutralizarlo, pero eso no está medido.
- **Casi-aciertos:** S30 devuelve `S42_T18` en 01:35:00, justo donde termina la referencia
  (01:34:33-01:35:00). S25/S26 recuperan una conversación anterior de MJ y Peter (`S27`, 00:58), parecida
  en contenido.
- **Localización muy corta.** El intervalo localizado puede ser una sola línea ASR de 2 s (p. ej. A14
  01:19:00-01:19:02). Acierta R@3, pero con IoU bajo.
- **Identidades (sin F3):** `S37_T03` describe a Nebula con la descripción del registro de Thor
  ("Asgardian, long hair and beard, often with Mjolnir"). `S37_T05` le asigna a Nebula la descripción de
  "Trent" ("discussed in context of quantum physics"). Los dos se detectaron buscando descripciones del
  registro bajo otro nombre; es una heurística, puede haber más.
- **Otros avisos en los 56 tramos:** `too_many_evidence_ids` 36, `name_not_in_registry` 22,
  `hedged_identity` 10, y 13 personajes con el string literal `"null"` como nombre.
- **Fuga de contexto:** los bloques VISION de 40 s pueden extenderse fuera del tramo (la rejilla no
  coincide). El brief puede describir algo de un tramo vecino; la localización recorta al tramo.
- **Sesgo de diseño:** se eligieron las escenas donde B falla con estas mismas consultas (selección por el
  resultado, dentro de la muestra). El mecanismo es claro (cobertura de 5 → 67 acciones en S42), pero la
  magnitud de la ganancia está sobreestimada para consultas nuevas.

## 4. Lectura

Los tramos atacan exactamente el fallo diagnosticado: el evento no estaba en el brief de escena. Con el mismo
modelo, prompt y validador, la cobertura sube un orden de magnitud y R@3 e IoU@3 suben a la vez, sin coste de
latencia. P_rep (sustituir la escena por sus tramos) es peor que P (añadirlos) en IoU (0,341 frente a 0,372):
conservar el documento de escena ayuda.

A título informativo, y **sin valor de afirmación**: con las consultas provisionales, P iguala el R@3 de
`exp035b` (0,767), con IoU@3 0,372 frente a 0,300 y intervalos de 30 s frente a 1114 s. Comparar con EXP-035
solo vale sobre el gold (`F5_METHOD_FREEZE.md` §2).

## 5. Coste de escalar (estimado con los 75 s/tramo medidos, lote 8, esta GPU)

| alcance (excluye los 56 ya hechos) | escenas | tramos | GPU estimada |
|---|---:|---:|---:|
| escenas > 250 s | 20 | 238 | 5,0 h |
| escenas > 165 s | 33 | 304 | 6,3 h |
| escenas > 120 s | 41 | 335 | 7,0 h |
| **todas las escenas** (cobertura completa de ambas películas) | 119 | 445 | **9,3 h** |

Esto no es "claramente barato", así que **no se ejecutó**. Más indexado (CPU, ~1 min) y evaluación (~1 min).

## 6. Recomendación

**Escalar, con cobertura completa (445 tramos, ~9,3 h de GPU en un solo trabajo nocturno, lote 8).**
- Preferible a un umbral de duración: el único efecto negativo medido (desplazamiento en C) viene de que solo
  algunas escenas tienen tramos. Cobertura completa cuesta solo +2,3 h más que el umbral de 120 s.
- Mantener el diseño "añadir" (P), no "sustituir" (P_rep).
- Tras escalar, repetir `tramo_eval.py` (con los índices nuevos) y verificar que C ya no pierde aciertos.

## 7. Qué implica para el candidato congelado, F2 y F3

- **Candidato:** por `F5_METHOD_FREEZE.md` §2.5, P **no** sustituye al candidato salvo con una **enmienda
  fechada antes de ver cualquier gold**, con el índice de tramos completo y sus hashes congelados. Decisión
  pendiente del equipo: (a) escalar → enmendar → evaluar el gold con el candidato de tramos; o (b) evaluar el
  gold con el candidato actual y tratar los tramos como exploratorios.
- **F2:** los tramos compensan la granularidad gruesa de F2 para la búsqueda, pero no sustituyen la
  calibración. El criterio de fronteras de F2 sigue necesitando `gold_*.csv` (`exp036/f2/ANOTACION.md`).
- **F3:** los errores de identidad (S37_T03, S37_T05, 22/56 nombres fuera del registro) persisten a cualquier
  granularidad. Las consultas por entidad seguirán siendo frágiles hasta tener identidades ancladas.

## 8. Reproducción

```bash
cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python
$P -I exp036/f5/tramos/tramo_briefs.py --selftest
$P -I exp036/f5/tramos/tramo_briefs.py --dry-run
$P -I exp036/f5/tramos/tramo_briefs.py --batch 8          # GPU; reanuda solo lo que no está ok
$P -I exp036/f5/tramos/tramo_index.py                     # CPU; escribe tramos/index_add e index_replace
$P -I exp036/f5/tramos/tramo_eval.py                      # -> results/eval_tramo_pilot.{json,log}, _per_query.csv
```

Artefactos: `tramos/briefs_tramos_{Avengers_Endgame,Spider_Man}.json`, `tramos/index_add/`,
`tramos/index_replace/`, `results/eval_tramo_pilot.json`, `results/eval_tramo_pilot.log`,
`results/eval_tramo_pilot_per_query.csv`.
