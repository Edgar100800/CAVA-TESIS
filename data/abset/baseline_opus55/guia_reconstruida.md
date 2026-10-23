# Guía de etiquetado (reconstruida, versión 0.1-r)

Reconstrucción de `guia_etiquetado.md` v0.1 a partir del esquema y del estilo de las 12 segmentaciones de
`reports/2026-10-23/anexos/visor.html`. El original no está en el clúster; si aparece, se rehace la línea base con él.

## Entrada
Solo la transcripción del video (subtítulos de YouTube con marcas de tiempo `[mm:ss]`). No se usan capítulos del
autor, descripción ni comentarios.

## Tarea
Dividir el video completo en segmentos temáticos contiguos y describir cada uno.

## Reglas de segmentación
1. **Cobertura total:** el primer segmento empieza en 0 y el último termina en la duración del video. Sin huecos ni
   solapes: el `fin` de un segmento es el `inicio` del siguiente.
2. **Frontera = cambio de tema o de función.** En entrevistas y conversaciones, casi siempre una pregunta nueva del
   conductor; en documentales, el paso a otra historia, especie, lugar o etapa; en tutoriales, el paso a otra parte del
   trabajo. Si la pregunta queda pegada al final de la respuesta anterior, la frontera va donde empieza el tema nuevo.
3. **Granularidad:** segmentos de unos 2 a 5 minutos de media. Una dinámica larga y continua (un ranking, una lista)
   se puede dividir en tandas para no perder granularidad. Los bloques breves con función propia (intro, publicidad,
   despedida) son segmentos aunque duren menos de un minuto.
4. **Tiempos en segundos enteros**, tomados de las marcas de la transcripción.

## Campos por segmento
- `id`: 1, 2, 3… en orden.
- `inicio`, `fin`: segundos.
- `tipo`: uno de
  - `intro` (gancho, adelanto, autopromoción inicial),
  - `presentacion` (presentación del invitado o del tema),
  - `relato` (narración continua de un caso o una historia),
  - `tema` (bloque temático o de explicación; el tipo más frecuente),
  - `anecdota` (historia breve y autocontenida),
  - `reflexion` (opinión, valoración o consejo personal),
  - `publicidad` (sponsor, aunque esté integrado en la conversación),
  - `recomendacion` (recomienda libros, cursos, canales, productos propios),
  - `cierre` (despedida y agradecimientos).
- `tema`: título corto del segmento (≤ 10 palabras), en español.
- `resumen`: una o dos frases en español con lo que se dice, atribuyendo las afirmaciones a quien las hace.
- `subtemas`: lista de `{inicio, titulo}` con los cambios internos del segmento (vacía si no hay).
- `palabras_clave`: 2 a 6 términos (nombres propios, conceptos).
- `confianza`: `alta`, `media` o `baja`, sobre si la frontera y el tema están bien definidos.

## Campos por video
- `estructura.formato`: qué tipo de pieza es y quiénes participan.
- `estructura.patron`: la secuencia de bloques, con `->`.
- `estructura.observaciones`: cómo se marcan las fronteras, temas recurrentes, publicidad y errores visibles del
  subtítulo automático (nombres deformados), sin corregir el contenido.

Todo el texto descriptivo se escribe en español, aunque el video esté en inglés.
