# Videos externos para pruebas manuales

Esta carpeta guarda videos descargados por nosotros y sus ejecuciones manuales.
No pertenece a `tests/` ni a los splits train/val/test de los corpus.
Los videos, metadatos del descargador y resultados locales se excluyen de Git.

- `videos/`: archivos originales y metadatos de procedencia.
- `results/<video_id>/`: protocolo, audio, transcripción, señales, tópicos y revisión HTML.
- `run_demo.py`: ejecuta el gestor multimodal real de CAVA con texto TF-IDF
  (Whisper tiny de SegLoop) y embeddings visuales SigLIP, sin fusionarlos.

## Caso solicitado: cLDm1TQOoGQ

Fuente: https://www.youtube.com/watch?v=cLDm1TQOoGQ

Título obtenido: The Wild Project #384 - Luisito Comunica | El podcast que llevabais años esperando.
Duración indicada por YouTube: 10767 segundos (2:59:27).

Estado al 2026-10-02: **video recibido del usuario y primera prueba completada**.
El archivo subido se movió a `videos/cLDm1TQOoGQ.mp4` (718 MB, AV1/Opus,
480p). Procedencia y SHA-256 en `source.json`. La descarga automática previa
había fallado por rechazos de YouTube.

Resultados de los primeros 600 segundos:

- 60 ventanas; todas con texto; 234 segmentos ASR.
- Señales: texto `(60, 555)` y visual `(60, 768)`, con valores finitos.
- Siete cortes de consenso: **1:40, 3:30, 5:00, 5:20, 6:40, 7:40, 8:40**.
- 20 grupos en total: 16 con soporte y cuatro singletons marcados sin tópico
  (3:20–3:30, 3:30–3:40, 6:40–6:50 y 6:50–7:00).
- Un grupo no contiguo enlaza 5:30–6:20 con 7:50–8:00. Es una hipótesis de
  retorno de tema, no una conclusión validada por anotación humana.

Revisión inicial del texto: el corte de 1:40 queda cerca de la transición de
presentación a conversación; el de 8:40 queda cerca del paso a problemas de
cobro con una compañía. Otros cortes subdividen conversaciones que continúan
sobre el mismo asunto, como la monetización de YouTube. Son observaciones
basadas en el ASR, que contiene errores; no constituyen métricas de calidad.
El número de grupos no equivale al número de cortes: el gestor calcula los
enlaces y el consenso de fronteras por mecanismos distintos.

## Ejecución del video completo

Completada el 2026-10-02 en `results/cLDm1TQOoGQ-full/`, conservando la prueba
de diez minutos. Comando:

```bash
/home/edgar.chambilla/.conda/envs/segloop/bin/python \
  test-video/run_demo.py test-video/videos/cLDm1TQOoGQ.mp4 \
  --seconds 0 --out test-video/results/cLDm1TQOoGQ-full
```

Resultados:

- Duración analizada: 10767,30 segundos (2:59:27), sin truncamiento.
- 1077 ventanas y frames; 1075 ventanas con texto; 4022 segmentos ASR.
- Señales: texto `(1077, 4517)` y visual `(1077, 768)`.
- 78 cortes de consenso y 103 grupos; 19 grupos sin tópico y 13 que necesitan revisión.
- 18 grupos no contiguos; el mayor reúne 165 ventanas (27:30 de contenido
  acumulado). Esto merece revisión por posible agrupación excesiva: el soporte
  de las señales expresa acuerdo del algoritmo, no calidad temática validada.
- Verificación: señales finitas, 1077 frames, cada ventana en exactamente un
  grupo, IDs alineados y cobertura hasta el final del video.

Abrir `results/cLDm1TQOoGQ-full/review.html` para revisar el contenido.
`summary.json` contiene el resumen y los 78 tiempos de corte en HH:MM:SS;
`topics.json` contiene grupos, soportes y banderas de revisión;
`run.log` registra la ejecución. No se midió precisión contra anotaciones.

Los cortes iniciales no tienen por qué coincidir con los de la prueba de diez
minutos: TF-IDF, percentiles de fronteras y percentiles de retorno se calculan
sobre el tramo analizado, aunque los parámetros se mantengan iguales.

## Clips exportados para revisión

Se exportaron los **79 tramos consecutivos** definidos por los 78 cortes de
consenso a `results/cLDm1TQOoGQ-full/clips/`. Son MP4 H.264/AAC, con imagen
y audio originales recodificados. Conservan todo el video en orden; los grupos
no contiguos no se concatenaron. Ocupan aproximadamente 1,04 GiB.

Abrir `results/cLDm1TQOoGQ-full/clips/index.html` para reproducir o descargar
cada clip y desplegar su transcripción. `manifest.json` registra los tiempos de
origen, duración prevista y real, tamaño y texto de cada archivo.

```bash
/home/edgar.chambilla/.conda/envs/segloop/bin/python \
  test-video/export_clips.py test-video/results/cLDm1TQOoGQ-full
```

La exportación permite reanudar: valida los archivos completados y evita
sobrescribirlos. Comprueba que la fuente y el protocolo coincidan.
Los límites son los del algoritmo y pueden caer dentro de una frase.
Verificación: 79 archivos, límites de origen consecutivos sin huecos,
canales H.264/AAC en todos, enlaces de la página completos, sin archivos
parciales pendientes y diferencia máxima de duración de 0,030 s por clip.
Se comprobó también decodificación de audio e imagen del primer y último clip.

## Caso Zifr_c0dTlc

Fuente: https://www.youtube.com/watch?v=Zifr_c0dTlc

Título: AVENGERS: ENDGAME ENCORE (2026) RESUMEN EN MINUTOS.
Duración indicada por YouTube: 35:11. Resumen narrado de una película
(una sola voz sobre imágenes de archivo), 480p H.264/AAC, 88 MB.

Estado al 2026-10-04: **descargado y corrida completa en curso** (job SLURM
54456, perfil documentary). Primera descarga rechazada con HTTP 403 por la
versión antigua de yt-dlp; resuelto actualizándola a 2026.08.19. Video y
metadatos en `Zifr_c0dTlc/`; procedencia y SHA-256 en `source.json`.

Resultados (job 54456 completado el 2026-10-05, 9 min de GPU):

- Duración analizada: 35,2 min; G-versión True.
- 28 tópicos, 8 con retornos; etiquetas 14B coherentes con la narrativa del
  video (apertura de Barton, plan de tiempo-travel, sacrificios, multiverso).
- Voces: 1 grupo acústico V1 al 100% (narrador único, esperado con
  `documentary`/acoustic_group; no hay identidad por hablante).
- Versiones: full_chapters (28 clips), recap60, highlights10pct, threads
  (0/1/2) y speaker_threads_0; 54 mp4 en `clips/` más 7 playlists completas
  (`version_*.mp4`). Total 409 MB.
- Verificación: primer y último clip decodifican H.264/AAC con duraciones
  correctas (30,0 s y 60,0 s); `index.md` lista rangos, duración, retornos,
  grupo acústico y etiqueta por tópico.
- Sin ground truth: la corrida demuestra funcionamiento del stack completo
  sobre un video externo; la calidad de clips sigue sin medirse.

Corrida end-to-end con el pipeline completo (`scripts/cava_run.py`), a
diferencia del caso cLDm1TQOoGQ que usó el demo ligero `run_demo.py`:

```bash
sbatch test-video/run_zifr.sbatch
# equivale a:
python scripts/cava_run.py \
  test-video/Zifr_c0dTlc/Zifr_c0dTlc.mp4:documentary \
  --out test-video/Zifr_c0dTlc
```

Perfil documentary (EXP-025): percentil 90, snap visual 30 s (EXP-027),
voces como grupos acústicos por narrador único (EXP-028). ASR Whisper;
Parakeet (EXP-030) seguía en prueba al lanzar la corrida, así que no es el
stack final. Salida esperada en `Zifr_c0dTlc/Zifr_c0dTlc/`: topic_map.json,
versions.json, index.md/json, clips/*.mp4, version_documentary_*.mp4 y
run_report.json.

## Caso TheLastWinter

Fuente: archivo MKV subido por el usuario el 2026-10-05 (película, sin URL de origen).
Original: 1:37:23 (5843 s), HEVC 1920x960, audio EAC3 5.1 en inglés, subtítulos
SRT eng/eng SDH/hin/hin SDH y una portada MJPEG 4K como segundo stream de video; 5,6 GB.

Organización, como en el caso cLDm1TQOoGQ:

- `videos/TheLastWinter.mkv`: original intacto.
- `videos/TheLastWinter.mp4`: copia de trabajo 480p H.264/AAC estéreo, con solo el
  video y el audio principales. Se normaliza porque el corte de clips de
  `topicagg/pipeline.py` llama a ffmpeg sin `-map` y podría tomar la portada o
  los subtítulos. Los casos anteriores eran también 480p H.264/AAC.
- `videos/TheLastWinter.eng.srt` y `.eng.sdh.srt`: subtítulos de referencia. No
  entran al pipeline; quedan para comparar con el ASR.
- Procedencia y SHA-256 de ambos archivos en `source.json`.

Preparación (CPU) y corrida completa (GPU) encadenadas:

```bash
sbatch test-video/prep_lastwinter.sbatch                           # MKV -> MP4 + SRT
sbatch --dependency=afterok:<job_prep> test-video/run_lastwinter.sbatch
# equivale a:
python scripts/cava_run.py test-video/videos/TheLastWinter.mp4:film --out test-video/results
```

Perfil film: unidades de 5 s, percentil 80 y retorno 90, snap visual 30 s y
voces por K con BIC. Salida en `results/TheLastWinter/`: topic_map.json,
versions.json, index.md/json, clips/*.mp4, version_*.mp4 y run_report_<job>.json
en `results/`.

Estado al 2026-10-05: **MP4 listo y verificado** (prep job 54566, 10:40 en CPU: 960x480 H.264/AAC, 562 MB, 5843,045 s, decodifica al inicio y al final; la pista de capítulos del MKV queda como stream de datos). Corrida job 54567 en
cola. No había GPU libre con VRAM suficiente para el Qwen 14B en bf16 (unos 30 GB):
la T4 de g001 y los MIG del A100 no alcanzan. 54567 espera la A6000 de ds001 cuando
termine v1_blind40a (54536); a v1_blind40b (54537) se le subió el nice a 500 para que
no se adelante.

## Descargar

Desde la raíz de CAVA, con acceso de red:

```bash
/home/edgar.chambilla/.conda/envs/segloop/bin/yt-dlp \
  --no-playlist --write-info-json \
  --ffmpeg-location /home/edgar.chambilla/.conda/envs/segloop/bin \
  -f 'bv*[height<=480]+ba/b[height<=480]/b' --merge-output-format mp4 \
  -o 'test-video/videos/%(id)s.%(ext)s' \
  'https://www.youtube.com/watch?v=cLDm1TQOoGQ'
```

Si YouTube mantiene el rechazo, colocar una copia descargada del video en
`videos/` y ejecutar el comando siguiente con su ruta.

## Ejecutar y revisar

Prueba inicial sobre los primeros diez minutos:

```bash
/home/edgar.chambilla/.conda/envs/segloop/bin/python \
  test-video/run_demo.py test-video/videos/cLDm1TQOoGQ.mp4 --seconds 600
```

Para analizar el video completo, usar `--seconds 0`; requiere más tiempo y memoria.
La extracción usa CPU y los modelos ya almacenados en la caché de SegLoop.
La prueba emplea ventanas de 10 segundos y un frame central por ventana,
no el extractor de shots ni todos los canales del pipeline MovieNet.
Los parámetros quedan registrados en `protocol.json` antes de la extracción.
El consenso exige ambas señales. Los grupos permiten retornos de tema con
enlace promedio y abstención de las ventanas sin texto.

Abrir `results/cLDm1TQOoGQ/review.html` para inspeccionar frames,
transcripción y pertenencia a grupos. `topics.json` registra cortes en segundos,
cortes por señal, soporte, grupos sin tópico y grupos que necesitan revisión.
No hay ground truth: esta ejecución demuestra funcionamiento y permite revisión
cualitativa, pero no mide precisión ni asigna nombres semánticos a los tópicos.

Verificación realizada: ejecución sobre el video real, señales finitas y alineadas,
cobertura de las 60 ventanas exactamente una vez entre los grupos, generación
de 60 frames y del informe HTML. FFmpeg extrae los frames por software porque
el decodificador AV1 de OpenCV falla en este entorno. La transcripción se reutiliza
si el protocolo coincide; usar una carpeta de salida nueva al sustituir el video.
