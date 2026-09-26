# ADR-0009: Pivote de evaluación a contenido formato podcast

- Estado: **Propuesto** (2026-09-22) — decisión del humano sobre corpus
- Contexto: ADR-0008 (evaluación desalineada) · objetivo A2SUM-X: clips + contexto +
  versiones adaptadas al consumidor

## Por qué formato podcast es el objetivo correcto

El producto real de A2SUM-X (clips íntegros + contexto + versiones por consumidor) coincide
con el caso de uso más fuerte del contenido long-form hablado: **podcasts en video** — capítulos
por tema, clips virales de 60s, recaps. Además: (1) TransNetV2 no encuentra cortes en
talking-heads (lección SumMe) → la segmentación útil aquí es **temática** (chapters), no visual;
(2) el transcript temporizado es la señal estructural — justo la fortaleza text-side del stack
(transcript_loader → text_segmenter → time_mapper + nuestro alineador guion→srt).

## Panorama verificado (2026-09-22)

| Candidato | Videos | GT | Acceso raw | Veredicto |
|---|---|---|---|---|
| **How2** (2,000h instructional) | ❌ **eliminados de YouTube** (aviso oficial del README) | transcripts 2,000h + abstractive summaries + features pre-extraídas | texto/features ✓ | text-side a escala; visual N/A |
| **TED talks** | ✅ YouTube/TED (CC-BY-NC-ND) | solo títulos/descripciones (estilo TEDXSum) — sin chapters GT | ✓ con ToS NC | corpus construible; GT propia |
| **Podcasts CC en YouTube** (filtro license=cc) | ✅ canal por canal | **chapters publicados por los creadores** (timestamps de temas) = GT de segmentación temática natural | ✓ yt-dlp (GUIA repo) | **mejor señal GT para el propósito** |
| BLiSS (local) | ❌ crudos no públicos | importancia + summaries + transcript temporizado | features/text ✓ | complemento in-domain |
| Spotify/MediaSum | ❌ audio/texto | descriptions/transcripts | ✓ audio | text-side complemento |

**Dato estructural:** no existe dataset público de video-podcast con GT de segmentación
temática. Los creators publican **chapters** (timestamps temáticos) — ese es el GT natural, y
nadie lo ha curado como benchmark.

## Decisión propuesta

**Construir nuestro propio corpus "PodcastChapters"** (fill del hueco, en lugar de forzar
datasets ajenos):

1. **Curaduría**: 30-50 videos podcast (YouTube, filtro CC o con permiso, duración ≥30min,
   con chapters publicados; géneros: tech/interviews/educational).
2. **GT temática**: chapters oficiales (timestamps + títulos) → segmentos temáticos
   (`gt/chapters.ndjson`) — GT de frontera TEMA, no visual.
3. **Pipeline**: descarga → transcript (ASR repo o subtitles de YouTube) → alineador →
   segmentación temática (nueva señal text-side) + SegLoop segment-level (visual, modo 2s) →
   VJudge para contexto de cada capítulo.
4. **Benchmark de consumidor** (ADR-0008 M3): capítulos = clips; versiones por presupuesto
   (recap 60s, capítulo completo, multi-capítulo); explicación por capítulo.

### Gates pre-registrados

- **G1 (corpus)**: ≥30 videos con chapters válidos y transcript obtenido (≥90% cobertura de
  duración).
- **G2 (segmentación temática)**: precisión de fronteras temáticas del transcript-alineador
  vs chapters oficiales ≥ 0.5 con tolerancia ±15s (temas son difusos; tolerancia ancha y
  declarada).
- **G3 (consumidor)**: playlists por presupuesto cumplen 100% del presupuesto y ≥1 versión por
  perfil; evaluación VLM-as-judge de coherencia temática de cada clip.

## Consecuencias

- Cómo contribuimos: primer benchmark de segmentación temática para video-podcast (hueco real).
- Cómo no contribuimos: no reemplaza TVSum/SumMe como comparativas externas; queda como
  evaluación purpose-aligned propia (ADR-0008) + How2 text-side si se requiere escala.
- Riesgo: calidad variable de chapters de creators → G1 filtra; tolerancia ±15s definida antes
  de medir.
