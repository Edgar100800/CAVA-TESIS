# EXP-041-L — Enmienda al pre-registro de evaluación con usuarios (versión corta)

**Fecha:** 2026-11-16 · **Estado:** escrita **antes** de recolectar cualquier juicio.
**Base:** `reports/exp041/EXP-041_evaluacion_usuarios.docx` (diseño completo, 4 pares, 100 min).
**Motivo:** el plazo de entrega se comprimió a 3–5 días. Se reduce la sesión manteniendo la
pregunta principal y el control de sesgo. Todo lo no modificado aquí sigue vigente.

## 1. Qué cambia

| Elemento | EXP-041 completo | EXP-041-L (esta enmienda) |
|---|---|---|
| Sesión | 100 min, presencial, 4 pares | **~35 min, asíncrona o presencial**, 2 pares + control |
| Pares evaluados | T, H, control, S | **T (CAVA vs U), H (CAVA vs U), control (CAVA vs CAVA)** |
| Par S (mejor señal sola) | Sí, secundario | **Fuera**: se cubre en EXP-040 (9 videos) |
| Bloques B (recuerdo) y E (grupo focal) | Sí | **Fuera** de la comparación; se conserva una pregunta abierta |
| Meta de N | 60 (mínimo 40) | **20–30 (mínimo 20)**; por debajo, solo descriptivo |
| Hipótesis | PI1–PI5 | **H-Combinada**: CAVA > U en T y H |

## 2. Hipótesis y criterio

- **H1 (principal):** en elección forzada a ciegas, la proporción de juicios que prefiere CAVA
  frente a U, agregando T y H, es mayor que 0,5.
- **H2 (por formato):** la misma dirección en T y en H por separado (descriptiva; sin criterio
  confirmatorio por falta de potencia).
- **Control:** el par CAVA vs CAVA debe responder «Iguales»; si no, se reporta la tasa de
  inconsistencia y se analiza como sesgo de posición.
- **Criterio confirmatorio:** IC 95 % (Wilson por par; bootstrap clusterizado por persona para
  la combinada) que **excluya 0,5** a favor de CAVA. Si lo incluye: «sin evidencia
  concluyente», con la dirección observada y el efecto mínimo detectable (MDE).

## 3. Material (estímulos)

- Película: *Spider-Man: Brand New Day* (2026), 145 min, audio inglés con subtítulos en inglés.
- Corrida CAVA congelada: `data/films_runs/Spider_Man` (1 740 unidades, 104 tópicos, 45 con
  retornos, 8 grupos de voz).
- **T:** línea de tiempo de 145 min con bloques de capítulo, etiqueta y miniatura; clic reproduce
  el clip del capítulo. 3 min por lado.
- **H:** video continuo de **240 s** (presupuesto fijo del evento; el producto usa 10 % = 14,5 min)
  más su barra de clips. 4 min por lado.
- **U:** mismos capítulos (número y etiquetas del mismo modelo) con cortes equiespaciados;
  highlights de 240 s repartidos equiespaciados con las mismas duraciones.
- Generación: `scripts/exp041_stimuli.py` (CAVA y U desde la corrida congelada).
- **Declaración:** cambiar el presupuesto de highlights de 10 % a 240 s es un cambio de
  parámetro, no de código; se aplica igual a CAVA y a U.

## 4. Procedimiento

1. Consentimiento (A10) y filtro: estudiante UTEC, 18+, vio la película.
2. Instrucción: «vas a comparar dos versiones automáticas del mismo formato; no sabes cuál es cuál».
3. Par T (3 min por lado), elección forzada: A / B / Iguales.
4. Par H (4 min por lado), elección forzada.
5. Control (90 s por lado), elección forzada.
6. Pregunta abierta: «¿qué le falta a estas versiones para ser útiles?».
7. Debrief: se revela qué sistema produjo cada versión.

Lado de CAVA y orden T/H se contrabalancean con 4 secuencias asignadas por turno (idénticas a
EXP-041). El participante no ve nunca el nombre de los sistemas hasta el debrief.

## 5. Análisis (pre-declarado)

- Por par: proporción, IC 95 % de Wilson, prueba binomial exacta bilateral contra 0,5.
- Combinada: binomial sobre todos los juicios + bootstrap clusterizado por persona (10 000
  remuestreos).
- Control: tasa de «Iguales» esperada; se reporta como control de atención.
- Sin ajuste por múltiples comparaciones: hay **una** hipótesis confirmatoria.
- N < 20: solo descriptivo (porcentajes + Wilson), sin valor p en el texto principal.

**Interpretación escrita antes de ver datos**

| Resultado | Texto |
|---|---|
| IC excluye 0,5 y favorece a CAVA | «Evidencia piloto de preferencia por la organización CAVA frente a la versión sin estructura.» |
| IC incluye 0,5 | «Sin evidencia concluyente. Dirección observada X; con N=k el estudio solo detectaba efectos ≥ MDE.» |
| IC excluye 0,5 y favorece a U | Se reporta como resultado negativo, en la línea de H5. |

## 6. MDE con el N alcanzado (α 0,05 bilateral, potencia 0,8, sin empates)

| Juicios sin empate | Preferencia mínima detectable |
|---:|---:|
| 29 | 75 / 25 |
| 47 | 70 / 30 |
| 62 | 67,5 / 32,5 |
| 85 | 65 / 35 |

## 7. Desviaciones declaradas

- Se elimina el par S y los bloques B/E del diseño completo (motivo: plazo).
- Se permite modalidad asíncrona (formulario + clips) en lugar de sesión presencial.
- El piloto con 3 personas se mantiene si el tiempo lo permite; si no, se declara.
- El consentimiento y la convocatoria son gestionados por la facultad; esta enmienda no los
  modifica.
