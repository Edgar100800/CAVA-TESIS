# Capa narrativa experimental

Plan de implementación: evidencia global completa -> descripciones de candidatos
con diez fotogramas -> acontecimientos y tópicos narrativos globales ->
correspondencia y funciones -> selección con antecedentes -> revisión de
continuidad -> clips e informes. Decisión: ADR-0002.

Se reutilizan `topic_map.json`, `work/state.json` y el video preparado de CAVA.
No se sustituye el mapa multimodal. Los tópicos narrativos globales son una
interpretación posterior, con IDs y evidencia propios.

El guion externo es opcional: lista JSON de objetos
`{"t0": 10, "t1": 30, "text": "acción o diálogo"}` en segundos de la copia
preparada. Se valida su cobertura temporal; no se acepta un TXT sin alinear.
Sin archivo externo se declara `script_source: asr_and_visual`, no guion real.

Antes de producción: pruebas CPU y prueba end-to-end en GPU alternativa;
producción DS depende de la finalización exitosa del smoke. Los prompts,
contratos de salida, parámetros y cambios en evidencia invalidan la caché.

## Ejecución

```bash
python scripts/cava_narrative.py data/films_runs/Avengers_Endgame \
  --out data/films_narrative_v1/Avengers_Endgame \
  --frames 10 --max-candidate-seconds 30 --budget-fraction 0.10 \
  --decode --require-continuity --validated-by data/films_narrative_smoke_v1
```

`scripts/narrative_smoke.sbatch` prueba ambas muestras reales en la A100 de
20 GB de ag001. Usa un presupuesto del 50 % para comprobar varias transiciones
en solo cuatro minutos; la producción usa 10 %. Modelo, prompts, extracción y
descripción son los mismos. No reutiliza etiquetas generadas con CPU.
`scripts/narrative_films.sbatch` procesa las dos películas secuencialmente en
DS; antes de cargar el modelo exige reportes smoke exitosos de las dos muestras
y hashes de código, revisión de modelo, número de imágenes y tamaño máximo de
candidato idénticos. No enviar ese trabajo hasta terminar la prueba GPU.

`scripts/narrative_dispatch.sbatch` es una tarea CPU que puede ponerse en cola
con `--dependency=afterok:<smoke>`. Después del éxito vuelve a comprobar los dos
reportes y solo entonces ejecuta `sbatch scripts/narrative_films.sbatch`.
Guarda el ID en `data/films_narrative_smoke_v1/ds_submission.json` y usa bloqueo
de archivo para evitar envíos duplicados. Si la prueba falla, el dispatcher no
se ejecuta y no existe envío a DS.

## Etapas y selección

1. Consumir todos los segmentos ASR, observaciones existentes y fragmentos de
   guion alineado, sin truncar el texto global; fragmentar entradas largas.
2. Extraer acontecimientos con referencias a las fuentes. Son hipótesis del
   modelo, no una anotación de verdad de referencia.
3. Construir candidatos desde todos los tramos del mapa, incluidos no_topic;
   cubrir huecos y cola y dividir tramos de más de 30 s. Un resto menor a un
   segundo se une al tramo anterior para no crear un candidato de solo audio
   por el desfase final entre pistas del contenedor.
4. Extraer diez imágenes por candidato, uniformemente distribuidas dentro del
   intervalo. Generar una descripción nueva con imágenes y diálogo; no copiar
   el resumen visual anterior como descripción nueva.
5. Reducir jerárquicamente acontecimientos y descripciones cronológicas a una
   sinopsis y hasta diez tópicos narrativos globales. No equivale a presentar
   toda la película en una sola ventana de contexto.
6. Evaluar por separado correspondencia global y etiqueta multimodal anterior;
   identificar función, importancia categórica y antecedentes conocidos.
7. Priorizar importancia, cobertura de cinco bandas temporales y funciones,
   diversidad de acontecimientos y orden temporal. No se fusionan scores o
   embeddings del gestor. Las razones del modelo y las de selección se guardan
   separadas. Créditos/logos y discordancias globales se excluyen explícitamente.
8. Reservar 15 % del presupuesto para contexto (salvo presupuesto del 100 %).
   Revisar cada transición; intentar hasta dos pasadas de inserción de contexto
   si sus dependencias caben. No ocultar incidencias irreparables.
9. Proponer un texto de narración lineal, exportar clips y concatenación; verificar
   canales, duración y decodificación cuando se usa `--decode`.

## Resultados por película

| Archivo | Contenido |
|---|---|
| `protocol.json` | Hashes de entradas/código, modelo y parámetros; impide reanudar con caché incompatible. |
| `evidence.json` | ASR, observaciones originales y guion opcional, con tiempos e IDs. |
| `events.json` | Acontecimientos y sus referencias temporales a evidencia. |
| `candidates.json`, `frames/` | Todos los candidatos, incluso descartados, con diez imágenes y descripciones. |
| `global_story.json` | Sinopsis, tópicos globales `gNNN` y fuentes de la reducción. |
| `narrative_topic_map.json` | Apariciones, candidatos y acontecimientos asociados a cada tópico global; permite varios temas por candidato. |
| `assessments.json` | Funciones, correspondencias, importancia y dependencias propuestas. |
| `selection.json`, `clip_decisions.jsonl` | Inclusiones y descartes, sus motivos y evidencia. |
| `continuity.json`, `continuity_history.json` | Incidencias y pasadas de reparación. |
| `narration.json/md` | Propuesta de narración escrita; no genera voz sintética. |
| `clip_times.csv` | Tiempos y decisiones para todos los candidatos. |
| `clips/`, `narrative_linear.mp4` | Fragmentos seleccionados y concatenación cronológica. |
| `linear_playlist.json` | Orden, tiempos fuente y duraciones reales de los archivos exportados. |
| `review.html/md` | Revisión con imágenes, descripciones, diálogo y motivos; el HTML filtra incluidos. |
| `run_report.json` | Comprobaciones técnicas, uso de caché y resultado de continuidad del modelo. |

`G_narrative` exige selección no vacía, cronología, presupuesto y antecedentes
válidos más continuidad sin incidencias según el modelo. No mide fidelidad
narrativa humana. Un fallo devuelve estado no exitoso con evidencias para
revisar; no habilita producción automáticamente.

Las fronteras siguen derivando de ventanas del mapa anterior y la división por
duración: esta versión no garantiza completar frases ni detectar todos los
cambios de plano. El análisis global es una capa posterior que puede cuestionar
etiquetas anteriores, sin reescribir las particiones del gestor.

## Vocabulario nuevo

- `event_id` (`eNNNNN`): acontecimiento con referencias a fuentes temporales.
- `global_topic_id` (`gNNN`): tema narrativo global; no equivale al ID multimodal.
- `candidate_id` (`cNNNNN`): tramo analizado antes de decidir su exportación.
- `topic_match`: correspondencia con los temas globales; `original_topic_match`
  evalúa por separado la etiqueta anterior. Valores: consistent, mixed,
  uncertain, mismatch (coincidente, mixto, incierto, discordante).
- `role`: setup (presentación), goal (objetivo), conflict (conflicto), development
  (desarrollo), turning_point (giro), consequence (consecuencia), resolution
  (resolución), transition (transición), credits (créditos), unknown (desconocido).
- `importance`: essential, supporting, optional, exclude: evaluación categórica
  del modelo, no probabilidad ni anotación humana.
- `prerequisite_candidate_ids`: antecedentes que deben estar incluidos para
  conservar el tramo; referencias futuras y ciclos se rechazan.
- `decision.reason`: motivo de inclusión o descarte bajo la política y el
  presupuesto; `assessment_reason` conserva el juicio descriptivo original.
- `needed_candidate_ids`: contexto que el revisor propone insertar para
  resolver un salto; puede no caber, en cuyo caso la incidencia queda abierta.
- `model_tasks_devices`: dispositivo real de generación (también en caché) por
  etapa; el control previo a DS exige CUDA en todas las etapas de ambas muestras.
