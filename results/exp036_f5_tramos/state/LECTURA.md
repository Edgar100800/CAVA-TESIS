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
