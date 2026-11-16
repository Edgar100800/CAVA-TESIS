# ADR-0002: Capa narrativa con evidencia temporal verificable

- Estado: **Aceptado para implementación experimental** (2026-11-07)
- Contexto: solicitud de análisis global, diez fotogramas por candidato,
  descripciones y resumen lineal sobre las dos películas externas.

## Contexto

El mapa multimodal agrupa similitud temática, pero duración y retornos no
expresan función narrativa. Una etiqueta posterior no corrige esa selección.
El texto ASR no es un guion cinematográfico; puede omitir acciones y equivocarse.

## Decisión

Agregar una capa independiente sobre las salidas existentes, sin modificar ni
fusionar las representaciones o scores del gestor (ADR-0001). Mantener como
evidencia separada ASR, observaciones visuales, votos del mapa y guion opcional.
Analizar todos los tramos candidatos, incluidos los descartados por el gestor,
dividiendo tramos largos antes de extraer diez imágenes por candidato.

Construir acontecimientos locales con referencias temporales, reducirlos a una
estructura global y contrastar cada candidato con ella. Registrar decisiones y
dependencias narrativas explícitas; seleccionar cadenas de antecedentes dentro
del presupuesto y conservar orden temporal. Revisar continuidad con un segundo
paso, sin presentar el juicio del modelo como validación humana.

El guion opcional se proporciona como JSON de fragmentos con tiempos ya
alineados al video preparado. Un TXT no alineado se rechaza: no atribuir a una
escena evidencia externa por coincidencias débiles. Esta versión no realiza
alineación automática de un guion sin tiempos.

## Consecuencias

- Nuevos resultados en carpetas separadas; los resultados originales permanecen
  como evidencia de origen. Modelos, revisiones, hashes, prompts y parámetros
  forman parte de la procedencia y de la clave de caché.
- La selección explica inclusiones y descartes; las dependencias desconocidas,
  futuras o circulares se rechazan antes de exportar.
- La continuidad se informa como hipótesis del modelo; problemas pendientes
  impiden el éxito de la validación GPU que habilita producción en DS.
- Diez imágenes no garantizan observar toda la acción; el audio/texto conserva
  su propia procedencia y se indican incertidumbres.

## Validación pre-registrada

CPU: cobertura sin huecos, alineación de evidencia, referencias válidas,
dependencias y presupuesto, caché incompatible y exportación fallida.
GPU alternativa: dos muestras reales completas (sin omitir etapas), diez
imágenes decodificables por candidato, JSON válido, cobertura de fuentes,
selección no vacía, continuidad sin incidencias pendientes y MP4 decodificables
con error de duración <= 0,15 s. Después, y solo con éxito, enviar DS con la
misma revisión del modelo y parámetros de análisis. Una muestra verifica el
funcionamiento; la calidad narrativa sobre películas completas exige revisión.
