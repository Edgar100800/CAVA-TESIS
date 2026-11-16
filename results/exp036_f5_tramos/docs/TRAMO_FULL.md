# EXP-036 F5 — Cobertura completa de tramos (F)

Generado automáticamente por `tramos/full_report.py` el 2026-11-15 19:22:27. Consultas **provisionales** (no gold). Reglas de adopción: `F5_METHOD_AMENDMENT_v1.md` §2.

## 1. Decisión: **F NO adoptado: el candidato sigue siendo B; tramos exploratorios**

| condición | medido | ¿cumple? |
|---|---|---|
| A1_coverage | `{"n_manifest": 501, "n_ok": 501, "covers_all": true, "disjoint": true, "tramo_docs_in_index": 501}` | sí |
| A2_confirms_pilot | `{"L_net_hits": 7, "IoU_L_F": 0.321, "IoU_L_B": 0.2}` | sí |
| A3_no_global_regression | `{"hits_F": 43, "hits_B": 37, "IoU_F": 0.377, "IoU_B": 0.301}` | sí |
| A4_C_no_worse_than_B | `{"hits_F": 23, "hits_B": 24, "IoU_F": 0.429, "IoU_B": 0.395}` | **no** |
| A5_latency | `{"p95_ms": 32.1}` | sí |

Ningún dato gold existe ni se ha visto (`gold_seen: false` en `tramos/full/adoption.json`).

## 2. Generación distribuida

| job | host | partición | asignados | inicio | fin | duración | rc | ok | gen (GPU) | carga |
|---|---|---|---:|---|---|---:|---|---:|---:|---:|
| s0_56_a1 | .56 | 0 | 112 | 2026-11-15 16:11:24 | 2026-11-15 18:17:11 | 126 min | 0 | 112 | 124.9 min | 2 s |
| s1_54_a1 | .54 | 1 | 111 | 2026-11-15 16:11:55 | 2026-11-15 18:31:17 | 139 min | 0 | 111 | 138.9 min | 2 s |
| s2_55_a1 | .55 | 2 | 111 | 2026-11-15 16:12:25 | 2026-11-15 18:25:15 | 133 min | 0 | 111 | 131.7 min | 2 s |
| s3_44_a1 | .44 | 3 | 111 | 2026-11-15 16:12:55 | 2026-11-15 18:45:19 | 152 min | 0 | 111 | 151.5 min | 3 s |
| repair_s0_56 | .56 | 0 | 8 | 2026-11-15 18:51:55 | 2026-11-15 19:18:50 | 27 min | 0 | 8 | 26.7 min | 2 s |
| repair_s1_54 | .54 | 1 | 8 | 2026-11-15 18:51:57 | 2026-11-15 19:03:47 | 12 min | 0 | 8 | 11.7 min | 2 s |
| repair_s2_55 | .55 | 2 | 8 | 2026-11-15 18:51:59 | 2026-11-15 19:05:50 | 14 min | 0 | 8 | 13.6 min | 2 s |

GPU de generación sumada en los 4 workers: **9.98 h** (81 s por tramo nuevo válido; piloto: 75 s/tramo). Tiempo de pared del orquestador: 178.4 min.

Eventos del orquestador (reintentos/reasignaciones/avisos):

- 2026-11-15 18:47 v1 adjudicada inválida: colisión de uid entre películas en tramo_briefs.py (registros indexados por uid, no por (película, uid)); 12 pares / 24 unidades afectadas (17 detectadas por la fusión v1, 7 más con las guardas nuevas)
- 2026-11-15 18:50 reparación intento 1: los 3 workers abortan (assert N=4 vs manifiesto de reparación N=3); sin generación; GPUs libres
- 2026-11-15 18:51 reparación intento 2: 3 jobs (.56/.54/.55), 24/24 ok; Av:S49_T00 truncado a 900 y cerrado a 1600

## 3. Validación y fusión

- Manifiesto: 501 tramos; válidos: **501/501**; ausentes: 0; inválidos: 0; particiones disjuntas: True; cobertura completa: **True** → A1 cumple.
- Unidades regeneradas en la reparación v2: 24.
- Por película: {'Avengers_Endgame': 280, 'Spider_Man': 221}. Por origen: `{"shard0": {"ok": 112}, "shard1": {"ok": 111}, "shard2": {"ok": 111}, "shard3": {"ok": 111}, "pilot": {"ok": 56}}`.
- Cada registro aceptado: misma evidencia (sha256) que el manifiesto, recalculada localmente; `validate()` de F1 re-ejecutado sobre la salida cruda sin problemas duros; JSON idéntico al guardado.

## 4. Resultados (60 consultas provisionales; `hybrid_rerank_loc`)

B = candidato congelado (`scene,topic`); P = piloto (56 tramos en 4 escenas); F = cobertura completa (`scene,topic,tramo`). L = 29 consultas de las 4 escenas del piloto; C = 31 restantes.

| cond. | subconj. | n | R@3 (IC 95 %) | IoU@3 (IC 95 %) | R@3[IoU≥.1] | R@1 | dur@3 | lat. media/p95 |
|---|---|---:|---|---|---|---|---|---|
| B | all | 60 | 0.617 [0.483-0.750] | 0.301 [0.220-0.388] | 0.567 | 0.467 | 33 s | 33/44 ms |
| P | all | 60 | 0.767 [0.650-0.867] | 0.372 [0.289-0.456] | 0.667 | 0.617 | 30 s | 32/38 ms |
| F | all | 60 | 0.717 [0.600-0.833] | 0.377 [0.290-0.464] | 0.650 | 0.633 | 24 s | 31/32 ms |
| B | L_long | 29 | 0.448 [0.276-0.621] | 0.200 [0.103-0.310] | 0.448 | 0.345 | 33 s | 34/43 ms |
| P | L_long | 29 | 0.828 [0.690-0.966] | 0.390 [0.279-0.505] | 0.724 | 0.690 | 27 s | 32/37 ms |
| F | L_long | 29 | 0.690 [0.517-0.862] | 0.321 [0.206-0.448] | 0.586 | 0.621 | 22 s | 31/32 ms |
| B | C_rest | 31 | 0.774 [0.613-0.903] | 0.395 [0.275-0.520] | 0.677 | 0.581 | 32 s | 32/44 ms |
| P | C_rest | 31 | 0.710 [0.548-0.871] | 0.356 [0.233-0.483] | 0.613 | 0.548 | 32 s | 32/37 ms |
| F | C_rest | 31 | 0.742 [0.581-0.871] | 0.429 [0.310-0.546] | 0.710 | 0.645 | 26 s | 32/32 ms |

**Por escena larga** (R@3 / IoU@3, n):

| escena | B | P | F |
|---|---|---|---|
| Avengers_Endgame:S37 | 0.625 / 0.301 (8) | 1.000 / 0.534 (8) | 0.875 / 0.417 (8) |
| Avengers_Endgame:S40 | 0.625 / 0.183 (8) | 0.875 / 0.227 (8) | 0.750 / 0.222 (8) |
| Spider_Man:S30 | 0.000 / 0.000 (2) | 1.000 / 0.694 (2) | 1.000 / 0.694 (2) |
| Spider_Man:S42 | 0.273 / 0.176 (11) | 0.636 / 0.349 (11) | 0.455 / 0.257 (11) |

McNemar exacto (R@3, x frente a B): P vs B R@3 [all]: 11/2 (p = 0.0225); P vs B R@3 [L_long]: 11/0 (p = 0.001); P vs B R@3 [C_rest]: 0/2 (p = 0.5); F vs B R@3 [all]: 10/4 (p = 0.1796); F vs B R@3 [L_long]: 9/2 (p = 0.0654); F vs B R@3 [C_rest]: 1/2 (p = 1.0)

Frente a B, F gana 10 consultas (A06, A08, A14, S01, S02, S12, S24, S27, S28, S29) y pierde 4 (S06, S09, S20, S21); pérdidas en C: 2 (S06, S09). Piloto P perdía en C: S13, S19.

De los 21 fallos de `hybrid_rerank` a nivel escena (`F5_BASELINE.md`), F recupera **12** (A08, A13, A14, A15, A21, A22, A27, S02, S22, S24, S28, S29); P recuperaba 14.

- pérdida S06 (Frank says living like this is a sentence, not a choice, and he would ; ref [[4357, 4377]]): F top-3 = tramo:S43_T04 01:43:48-01:43:58, tramo:S30_T03 01:04:21-01:04:29, tramo:S46_T03 01:54:05-01:54:40
- pérdida S09 (Spider-Man warns Jean she is not getting inside the vault; ref [[4543, 4559]]): F top-3 = tramo:S35_T00 01:15:20-01:15:25, scene:S35 01:15:20-01:15:25, topic:T62 01:15:20-01:15:25
- pérdida S20 (a voice announces ninety seconds to detonation; ref [[4955, 4962]]): F top-3 = topic:T11 00:13:20-00:14:00, topic:T61 01:38:10-01:38:40, tramo:S19_T00 00:34:50-00:35:30
- pérdida S21 (Spider-Man tries to put the inhibitor on the Hulk but his skin is too ; ref [[4988, 5000]]): F top-3 = tramo:S40_T00 01:20:19-01:20:22, scene:S40 01:20:19-01:20:22, tramo:S30_T13 01:10:30-01:10:52

## 5. Calidad e identidades (sin F3)

Sobre 501 briefs de tramo válidos: avisos `{'too_many_evidence_ids': 188, 'hedged_identity': 134, 'name_not_in_registry': 144, 'actor_name': 2}`; nombres con el string literal "null": 126; descripciones del registro atribuidas a otro nombre (heurística): **7**.

- Avengers_Endgame S6_T02: name='Tony Stark' con la descripción del registro de Iron Man
- Avengers_Endgame S18_T00: name='Tony' con la descripción del registro de Iron Man
- Avengers_Endgame S37_T03: name='Nebula' con la descripción del registro de Thor
- Avengers_Endgame S37_T05: name='Nebula' con la descripción del registro de Trent
- Avengers_Endgame S43_T00: name='null' con la descripción del registro de Thanos
- Avengers_Endgame S49_T00: name='Tony Stark' con la descripción del registro de Iron Man
- Avengers_Endgame S58_T23: name='Tony Stark' con la descripción del registro de Iron Man

## 6. Índice F congelado (forma parte de la enmienda v1)

```
75663198a4c1d4cc f5/tramos/full_v2/index_add/Avengers_Endgame.meta.json
468979fbe93f6abe f5/tramos/full_v2/index_add/Avengers_Endgame.npz
372ef9aa0d574fa8 f5/tramos/full_v2/index_add/Spider_Man.meta.json
dd97a111310d7525 f5/tramos/full_v2/index_add/Spider_Man.npz
fe2ed00d4ab30718 f5/tramos/full_v2/index_add/bm25.sqlite
```

## 7. Límites

- Consultas provisionales escritas por el agente desde ASR/VJudge; referencias sin verificar en video; n = 60.
- L se definió con las escenas donde B fallaba (dentro de la muestra); C es la comprobación de desplazamiento.
- El objetivo + 15 pp frente a EXP-035 solo es afirmable sobre gold humano (`F5_METHOD_FREEZE.md` §2.2).

## 8. Reproducción

```bash
cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python; T=exp036/f5/tramos
python3 $T/repair_run.py                       # v2: regenera las 24 unidades de la colisión (GPU)
$P -I $T/full_merge.py --jobs $T/full_v2/jobs.json --out-dir $T/full_v2
$P -I $T/tramo_index.py --briefs-dir $T/full_v2 --out-root $T/full_v2 --variants index_add
$P -I $T/tramo_eval.py --tag eval_tramo_full_v2 --conds "B=exp036/f5/index:scene,topic" "P=exp036/f5/tramos/index_add:scene,topic,tramo" "F=exp036/f5/tramos/full_v2/index_add:scene,topic,tramo"
$P -I $T/full_report.py --full-dir $T/full_v2 --eval exp036/f5/results/eval_tramo_full_v2.json --adoption-out $T/full/adoption.json --notes $T/full_v2/LECTURA.md
```

## 9. Historia de la ejecución (v1 inválida → v2)

- **v1 (inválida):** la fusión dio 484/501. La causa **no** era la rejilla ni la evidencia: el manifiesto, los
  workers y la fusión calculan intervalos y evidencia con las mismas funciones (`make_tramos` +
  `evidence_lines`), y la comprobación previa de los workers pasó. El fallo estaba en `tramo_briefs.py`, que
  indexaba los registros por `uid` y no por `(película, uid)`. Los uid `S<n>_T<k>` se repiten entre Endgame y
  Spider-Man, así que cuando ambos caían en la misma partición compartían un registro: dos generaciones en
  `attempts` (`[900, 900]`), metadatos de la última película y el mismo objeto escrito en ambos ficheros.
  Afectó a **12 pares = 24 unidades**: la fusión v1 detectó 17 y otras 7 pasaban por coincidencia de
  metadatos (contenido de origen incierto). Además, el A1 de v1 aceptaba ≥ 95 %, contra la enmienda (§2 A1
  exige cobertura completa). Los artefactos de v1 se conservan como `tramos/full/*_v1_invalid.*`.
- **Correcciones:**
  - generador indexado por `(película, uid)`, con asserts de que cada registro corresponde a su unidad;
  - la fusión rechaza `movie_field_mismatch` y `attempts_not_increasing` (las firmas de la colisión);
  - A1 = `n_ok == n_manifest` y `covers_all` y disjunto.
- **v2:** se regeneraron solo las 24 unidades. Cada par se puso en la **misma** partición para ejercitar el
  arreglo. El primer intento abortó sin generar (assert de número de particiones); el segundo dio 24/24 `ok`.
  Verificación independiente: 501/501 registros, sin duplicados ni ausentes; intervalo, sha256 de evidencia
  y `validate()` de F1 correctos en los 501; cada reparado lleva la evidencia de su propia película.

## 10. Lectura: resultado negativo

**La cobertura completa no confirmó el piloto, y F no se adopta.** Falla A4: en C (las 31 consultas fuera de
las escenas del piloto), F acierta 23 frente a 24 de B. Pierde S06 y S09 (S09 es un casi-acierto a 18 s de
la referencia) y gana S12. No se ajusta ningún umbral.

- **La ganancia del piloto era en parte dentro de la muestra y por asimetría.** En el piloto solo 4 escenas
  tenían tramos, y esos tramos no competían con tramos de otras escenas. Con cobertura completa compiten en
  todas partes:
  - R@3 en L baja de 0,828 (P) a 0,690 (F);
  - A10, A17, S20 y S21 caen ante tramos de **otras** escenas (por ejemplo, el top-3 de A17 son tres
    tramos sin relación);
  - F frente a B ya no es significativo: 10/4, p = 0,18 (P frente a B: 11/2, p = 0,02).
  Además, las 4 escenas del piloto se eligieron mirando dónde fallaba B con estas mismas consultas.
- **Lo que sí mejora F:** precisión temporal y rango 1. IoU@3 global 0,377 frente a 0,301; R@1 0,633 frente
  a 0,467; R@3[IoU ≥ 0,1] 0,650 frente a 0,567; intervalos devueltos de 24 s frente a 33 s. En C, F tiene
  más IoU (0,429 frente a 0,395) aunque un acierto menos. Es decir: F localiza mejor cuando acierta, pero no
  recupera más, y fuera de las escenas largas desplaza resultados correctos.
- **Con n = 60 provisional y una diferencia de 1 consulta en C**, ninguna de estas diferencias es concluyente
  en ningún sentido. La regla pre-registrada decide, no el tamaño del efecto.

## 11. Recomendación

1. **Candidato para el gold: B** (`hybrid_rerank_loc[scene,topic]`, índice congelado, hashes de
   `F5_METHOD_FREEZE.md` §4), tal como prevé la enmienda cuando F no se adopta.
2. **Tramos: exploratorios**, no candidatos. Se recomienda evaluar F sobre el gold solo como brazo
   **exploratorio declarado de antemano**, con el índice v2 congelado (hashes en §6). No cuesta GPU y es lo
   único que puede decir si la mejora de IoU/R@1 se sostiene con consultas humanas. No sirve para afirmar
   el criterio + 15 pp.
3. **No gastar más GPU en tramos antes del gold.** Variantes como el rerank jerárquico (escena → tramo) o los
   tramos solo en escenas largas responderían a lo visto en estas consultas provisionales. Si se prueban,
   tiene que ser con un pre-registro nuevo y sobre el gold o un conjunto dev separado, no sobre estas 60.
4. **Implicación para F2/F3:** el problema de fondo sigue siendo la unidad de indexado (escenas F2 sin
   calibrar) y las identidades sin anclar. Partir en tramos fijos no lo resuelve; añade documentos que
   compiten. La siguiente palanca es calibrar F2 con `gold_*.csv`.
