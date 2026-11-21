# EXP-046-STAB · Resultado

Corridas completadas: 40/60; faltan: ['R/Spider_Man/54', 'R/Spider_Man/55', 'R/ES2002c.Room/54', 'R/ES2002c.Room/55', 'R/bbc_01/54', 'R/bbc_01/55', 'R/com_en_01/54', 'R/com_en_01/55', 'R/com_es_01/54', 'R/com_es_01/55', 'D/Spider_Man/54', 'D/Spider_Man/55', 'D/ES2002c.Room/54', 'D/ES2002c.Room/55', 'D/bbc_01/54', 'D/bbc_01/55', 'D/com_en_01/54', 'D/com_en_01/55', 'D/com_es_01/54', 'D/com_es_01/55'].

## Lectura pre-declarada (aplicada literalmente)

Criterio: ARI >= 0,95 en todos los pares de la misma máquina en los 5 videos (modo D).

| video | piso de ruido ARI modo R (misma máquina) | ARI mínimo modo D (misma máquina) |
|---|---|---|
| Spider_Man | 0.2400 | 1.0000 |
| ES2002c.Room | 1.0000 | 1.0000 |
| bbc_01 | 0.4222 | 1.0000 |
| com_en_01 | 0.6093 | 1.0000 |
| com_es_01 | 0.4777 | 1.0000 |

**Adopción de D: SÍ**

## Piso de ruido — misma máquina (.56 r1-r3: 3 pares por video y modo)

Peor par por métrica (ARI/F1/IoU mínimos; Δ máximos). `id` = pares con partición unidad→tópico idéntica / pares.

| modo | video | pares | ARI min | F1 min | Δtóp max | Δret max | IoU hl min | IoU recap min | cap. min | G igual | id |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R | Spider_Man | 3 | 0.2400 | 0.9031 | 0.010 | 0.375 | 0.370 | 0.000 | 0.286 | True | 0/3 |
| R | ES2002c.Room | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| R | bbc_01 | 3 | 0.4222 | 0.7680 | 0.118 | 0.278 | 0.000 | 0.000 | 0.235 | True | 0/3 |
| R | com_en_01 | 3 | 0.6093 | 0.7077 | 0.115 | 0.286 | 0.000 | 0.000 | 0.280 | True | 0/3 |
| R | com_es_01 | 3 | 0.4777 | 0.7241 | 0.105 | 0.600 | 0.018 | 0.000 | 0.333 | True | 0/3 |
| D | Spider_Man | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | ES2002c.Room | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | bbc_01 | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | com_en_01 | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | com_es_01 | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |

## Piso de ruido — entre máquinas (solo los pares con corrida disponible; el diseño prevé 12 con .54/.55/.61)

Peor par por métrica (ARI/F1/IoU mínimos; Δ máximos). `id` = pares con partición unidad→tópico idéntica / pares.

| modo | video | pares | ARI min | F1 min | Δtóp max | Δret max | IoU hl min | IoU recap min | cap. min | G igual | id |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R | Spider_Man | 3 | 0.2424 | 0.8927 | 0.051 | 0.281 | 0.438 | 0.000 | 0.235 | True | 0/3 |
| R | ES2002c.Room | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| R | bbc_01 | 3 | 0.4282 | 0.7967 | 0.088 | 0.167 | 0.083 | 0.000 | 0.200 | True | 0/3 |
| R | com_en_01 | 3 | 0.4608 | 0.7123 | 0.115 | 1.000 | 0.000 | 0.000 | 0.174 | True | 0/3 |
| R | com_es_01 | 3 | 0.4132 | 0.8065 | 0.211 | 0.375 | 0.000 | 0.000 | 0.421 | True | 0/3 |
| D | Spider_Man | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | ES2002c.Room | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | bbc_01 | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | com_en_01 | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |
| D | com_es_01 | 3 | 1.0000 | 1.0000 | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | True | 3/3 |

## Diferencias por pista (peor par de la misma máquina; WER del ASR entre transcripciones, coseno SigLIP/bge, similitud del vjudge)

| modo | video | WER ASR máx | segmentos ASR idénticos (pares) | SigLIP cos mín | bge transc. cos mín | vjudge cos mediana mín | vjudge idénticos mín | vjudge igual con misma entrada | voz idéntica |
|---|---|---|---|---|---|---|---|---|---|
| R | Spider_Man | 0.1094 | 0/3 | 1.00000 | 0.27224 | 0.8188 | 0.087 | 61/61 (con entrada distinta: 22/593) | True |
| R | ES2002c.Room | 0.0000 | 3/3 | 1.00000 | 1.00000 | 1.0000 | 1.000 | 180/180 (con entrada distinta: 0/0) | True |
| R | bbc_01 | 0.0852 | 0/3 | 1.00000 | 0.41995 | 0.9033 | 0.176 | 92/92 (con entrada distinta: 5/130) | True |
| R | com_en_01 | 0.0817 | 0/3 | 1.00000 | 0.64040 | 0.9002 | 0.229 | 68/68 (con entrada distinta: 0/76) | True |
| R | com_es_01 | 0.1663 | 0/3 | 1.00000 | 0.59673 | 0.8842 | 0.108 | 11/11 (con entrada distinta: 3/100) | True |
| D | Spider_Man | 0.0000 | 3/3 | 1.00000 | 1.00000 | 1.0000 | 1.000 | 654/654 (con entrada distinta: 0/0) | True |
| D | ES2002c.Room | 0.0000 | 3/3 | 1.00000 | 1.00000 | 1.0000 | 1.000 | 180/180 (con entrada distinta: 0/0) | True |
| D | bbc_01 | 0.0000 | 3/3 | 1.00000 | 1.00000 | 1.0000 | 1.000 | 222/222 (con entrada distinta: 0/0) | True |
| D | com_en_01 | 0.0000 | 3/3 | 1.00000 | 1.00000 | 1.0000 | 1.000 | 144/144 (con entrada distinta: 0/0) | True |
| D | com_es_01 | 0.0000 | 3/3 | 1.00000 | 1.00000 | 1.0000 | 1.000 | 111/111 (con entrada distinta: 0/0) | True |

## Atribución (pista de la corrida 2 sustituida en la corrida 1, misma máquina; ARI del mapa recalculado frente al de la corrida 1)

| modo | video | par | ARI a-vs-b | ARI ASR | ARI vjudge | ARI visual | ARI voz | fuente principal | recálculo reproduce a |
|---|---|---|---|---|---|---|---|---|---|
| R | Spider_Man | 56.1<-56.2 | 0.2783 | 0.5905 | 0.3078 | 1.0000 | 1.0000 | vjudge | True |
| R | Spider_Man | 56.1<-56.3 | 0.2974 | 0.5766 | 0.3695 | 1.0000 | 1.0000 | vjudge | True |
| R | Spider_Man | 56.2<-56.3 | 0.2400 | 0.6271 | 0.3102 | 1.0000 | 1.0000 | vjudge | True |
| R | ES2002c.Room | 56.1<-56.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| R | ES2002c.Room | 56.1<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| R | ES2002c.Room | 56.2<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| R | bbc_01 | 56.1<-56.2 | 0.4222 | 0.6073 | 0.5096 | 1.0000 | 1.0000 | vjudge | True |
| R | bbc_01 | 56.1<-56.3 | 0.4837 | 0.6035 | 0.5096 | 1.0000 | 1.0000 | vjudge | True |
| R | bbc_01 | 56.2<-56.3 | 0.6275 | 0.6275 | 1.0000 | 1.0000 | 1.0000 | asr | True |
| R | com_en_01 | 56.1<-56.2 | 0.6140 | 0.6406 | 0.7351 | 1.0000 | 1.0000 | asr | True |
| R | com_en_01 | 56.1<-56.3 | 0.6093 | 0.6644 | 0.7260 | 1.0000 | 1.0000 | asr | True |
| R | com_en_01 | 56.2<-56.3 | 0.8220 | 0.8042 | 0.8309 | 1.0000 | 1.0000 | asr | True |
| R | com_es_01 | 56.1<-56.2 | 0.5671 | 0.5471 | 0.6582 | 1.0000 | 1.0000 | asr | True |
| R | com_es_01 | 56.1<-56.3 | 0.4777 | 0.5136 | 0.4196 | 1.0000 | 1.0000 | vjudge | True |
| R | com_es_01 | 56.2<-56.3 | 0.6320 | 0.6821 | 0.7394 | 1.0000 | 1.0000 | asr | True |
| D | Spider_Man | 56.1<-56.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | Spider_Man | 56.1<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | Spider_Man | 56.2<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | ES2002c.Room | 56.1<-56.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | ES2002c.Room | 56.1<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | ES2002c.Room | 56.2<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | bbc_01 | 56.1<-56.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | bbc_01 | 56.1<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | bbc_01 | 56.2<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | com_en_01 | 56.1<-56.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | com_en_01 | 56.1<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | com_en_01 | 56.2<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | com_es_01 | 56.1<-56.2 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | com_es_01 | 56.1<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |
| D | com_es_01 | 56.2<-56.3 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | ninguna (ARI = 1 en todas) | True |

## Re-evaluación de EXP-045-Q según la enmienda declarada

### vjudge vLLM BF16, fotogramas exactos (vjudge=fast_exact): extremo a extremo **NO PASA** frente al piso de R

| video | ARI (≥ piso) | F1 (≥) | Δtóp (≤) | Δret (≤) | IoU hl (≥) | IoU recap (≥) | pasa |
|---|---|---|---|---|---|---|---|
| Spider_Man | 0.3476 vs 0.2400 ✓ | 0.9375 vs 0.9031 ✓ | 0.0312 vs 0.0102 ✗ | 0.2647 vs 0.3750 ✓ | 0.5065 vs 0.3701 ✓ | 1.0000 vs 0.0000 ✓ | False |
| ES2002c.Room | 0.9528 vs 1.0000 ✗ | 0.8889 vs 1.0000 ✗ | 0.0000 vs 0.0000 ✓ | inf vs 0.0000 ✗ | 1.0000 vs 1.0000 ✓ | 1.0000 vs 1.0000 ✓ | False |
| bbc_01 | 0.5921 vs 0.4222 ✓ | 0.9016 vs 0.7680 ✓ | 0.0323 vs 0.1176 ✓ | 0.0000 vs 0.2778 ✓ | 0.3258 vs 0.0000 ✓ | 1.0000 vs 0.0000 ✓ | True |
| com_en_01 | 0.6088 vs 0.6093 ✗ | 0.8219 vs 0.7077 ✓ | 0.0417 vs 0.1154 ✓ | 0.4286 vs 0.2857 ✗ | 0.0000 vs 0.0000 ✓ | 0.0000 vs 0.0000 ✓ | False |
| com_es_01 | 0.9534 vs 0.4777 ✓ | 0.9825 vs 0.7241 ✓ | 0.0000 vs 0.1053 ✓ | 0.2000 vs 0.6000 ✓ | 1.0000 vs 0.0175 ✓ | 1.0000 vs 0.0000 ✓ | True |


## Notas y desviaciones

- **Corridas: 40/60.** `.54` y `.55` quedaron inalcanzables (ver el registro): faltan las 10 corridas de cada una (R y D × 5 videos). El piso de
  ruido y la lectura pre-declarada usan solo pares de la misma máquina (`.56`, 3 corridas por video y modo: completos). Entre máquinas solo hay
  pares `.56` × `.61` (3 por video y modo): no hay el diseño de 12 pares.
- Cada corrida parte del video (sin cachés), pila v1.1, sin etiquetas del LLM, hilos BLAS = 1, mismo commit de código (`dc4edac`) y mismas
  versiones de biblioteca en `.56` y `.61` (`env/<máquina>/pip_freeze.txt`; difieren el controlador NVIDIA, 580.178.04 frente a 595.99.02, y
  el equipo). No se cortaron mp4 (`cut=False`): IoU de highlights/recap se calcula sobre los segundos de `versions.json`.
- Varias corridas concurrentes por máquina (5 procesos con un libro de memoria de GPU de 22 GB por etapa): la concurrencia es una condición
  común a R y D; no se midió su efecto por separado.
- Atribución: la regla pre-declarada (la sustitución que más baja el ARI) devuelve ASR o vjudge, nunca visual ni voz. Diagnóstico añadido (no
  registrado): dado el mismo texto de entrada, el vjudge repite su salida (columna «vjudge igual con misma entrada»), de modo que sus
  diferencias son consecuencia del ASR; en D (ASR idéntico) todas las pistas son idénticas.
- ES2002c.Room (reunión): el modo R es estable en esta cadena (el ASR ref fue idéntico en las 3 corridas), así que su piso de ruido es 1,0 y la
  enmienda de EXP-045-Q, aplicada literalmente, exige a la variante una igualdad exacta en ese video.

