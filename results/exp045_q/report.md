# EXP-045-Q · Resultado (2026-11-20/21)

**Decisión por pista (reglas del registro aplicadas literalmente; umbrales, refset y reglas sin cambios):**

| pista / variante | fila de la pista | extremo a extremo (sustitución de esa pista) | decisión |
|---|---|---|---|
| ASR int8_float16 | **falla**: WER 10,27 % > 3 %; filtro de habla idéntico 94,3 % < 99 % (ΔWER AMI vs GT −3,0 pp: cumple) | falla en los 5 videos (ARI 0,49–0,90) | **NO adoptada** |
| SigLIP decode-once + FP16 + lotes (`visual=fast`) | **falla**: mediana coseno 0,9796 < 0,995; p1 0,881 < 0,98 | falla (ARI 0,33–0,82) | **NO adoptada** |
| SigLIP solo FP16 + lotes sobre fotogramas exactos (`visual=fast_exact`) | cumple: mediana 1,0000; p1 0,99998 | pasa en los 5 videos (ARI 1,0) | **ADOPTADA** |
| bge GPU FP16 (`embed=fast`) | cumple: mediana 1,0000; p1 1,0000 (texto ASR y resúmenes) | pasa en los 5 videos (ARI ≥ 0,997) | **ADOPTADA** |
| WavLM FP16 (`speaker=fast`) | cumple: mediana 1,0000; p1 1,0000 (n = 2 316) | V# no entra en el mapa ni en highlights/recap/capítulos (por construcción; speakers corre tras el mapa) | **ADOPTADA** |
| VJudge vLLM BF16 en lote + decode-once (`vjudge=fast`) | **falla**: mediana coseno 0,892 < 0,90; 14,2 % idénticos | falla | **NO adoptada** |
| VJudge vLLM BF16 en lote, fotogramas exactos (`vjudge=fast_exact`) | automático cumple (mediana 1,000; 56,1 % idénticos); revisión humana pendiente | **falla** (ARI 0,35–0,95; Spider 0,348, Δretornos 26 %) | **NO adoptada** (falla extremo a extremo; la revisión humana no cambia la decisión) |
| Etiquetas Qwen2.5-14B FP8 vLLM (`labels=fast`) | automático cumple (mediana 0,980; 37,3 % idénticos); 20 pares a ciegas: **sin hacer** | sin efecto en mapa/versiones (las etiquetas se calculan después del mapa) | **pendiente de revisión humana** |
| NVENC h264 (`clips=fast`) | sin fila registrada; integridad: duración de clips = ref (desv. máx. 0,08 s, igual que libx264) | tiempos de corte idénticos por construcción | **ADOPTADA** (sin fila registrada; requiere `-pix_fmt yuv420p`, ver desviaciones) |
| Rostros | **no evaluada** (variante no definida; `buffalo_l` research_only fuera del producto) | — | sin decisión |
| Diarización | no se toca | — | n/a |

Combinación de las pistas adoptadas (`visual=fast_exact,embed=fast`): pasa extremo a extremo en los 5 videos (ARI 1,0 / 0,997 en Spider).
El pack `--variant fast` completo (todas las pistas) **falla** extremo a extremo en los 5 videos, por lo que `fast` no equivale a "adoptado":
solo se adoptan las pistas de la tabla. Lecturas fijadas al ejecutar (el registro no las precisa): WER agrupado por corpus; coseno agrupado por unidad;
umbrales de extremo a extremo exigidos a cada video; "mismos tópicos" = conjunto de unidades con Jaccard ≥ 0,9; decode-once y motor vLLM
se separaron en variantes distintas (`fast` = decode-once, `fast_exact` = fotogramas exactos).

**Contexto de ruido (no cambia ninguna decisión):** el propio `ref` no es reproducible entre ejecuciones/entornos: ASR ref vs ref (repetición, 20 VoxConverse,
misma máquina) WER 2,89 % (8/20 archivos difieren, máx. 21 %); ref nuevo vs salidas congeladas: WER 6,3 % (BBC) y 9,0 % (Spider-Man), ARI de mapa 0,285
(Spider-Man) y 0,437 (BBC), Δretornos 24 %. Los umbrales de extremo a extremo de ASR/vjudge/decode-once quedan por encima de ese piso.

# EXP-045-Q · Resultado de la validación de tolerancia de variantes `fast`

Umbrales, refset_v1 y reglas: los registrados en `docs/EXPERIMENT_LOG.md` (EXP-045-Q, commit a4a30ec). Sin cambios.

## 1. Pistas (variante vs ref)

### ASR (faster-whisper int8_float16 vs float16)

| métrica | valor | umbral | ok |
|---|---|---|---|
| WER(fast, ref) agrupado, 25 archivos | 10.27 % | ≤ 3 % | False |
| · pipeline (5 videos) / VoxConverse dev (20) | 11.38 % / 8.53 % | | |
| · peor archivo | {'vox:aisvi': 0.28663330950679056} | (informativo) | |
| · archivos con WER > 3 % | 20: Spider_Man, ES2002c.Room, bbc_01, com_en_01, com_es_01, vox:afjiv, vox:ahnss, vox:aisvi, vox:akthc, vox:ampme, vox:asxwr, vox:atgpi, vox:aufkn, vox:azisu, vox:bauzd, vox:blwmj, vox:bravd, vox:bspxd, vox:bxpwa, vox:bydui | (informativo) | |
| AMI ES2002c: WER ref vs GT / fast vs GT / Δ | 28.16 % / 25.15 % / -3.007 pp | Δ ≤ +0,5 pp | True |
| Filtro de habla por unidad idéntico (todas las unidades) | 94.33 % | ≥ 99 % | False |
| · pipeline / vox | 92.48 % / 99.41 % | | |

| archivo | palabras ref | WER vs ref | unidades con mismo filtro |
|---|---|---|---|
| Spider_Man | 10382 | 9.50 % | 90.40 % |
| ES2002c.Room | 6141 | 19.88 % | 96.65 % |
| bbc_01 | 2963 | 6.28 % | 89.17 % |
| com_en_01 | 6900 | 5.99 % | 100.00 % |
| com_es_01 | 4036 | 16.23 % | 98.30 % |
| vox:abjxc | 165 | 0.00 % | 100.00 % |
| vox:afjiv | 386 | 8.55 % | 100.00 % |
| vox:ahnss | 2584 | 8.48 % | 99.25 % |
| vox:aisvi | 1399 | 28.66 % | 94.68 % |
| vox:akthc | 328 | 3.96 % | 100.00 % |
| vox:ampme | 423 | 5.67 % | 100.00 % |
| vox:asxwr | 809 | 6.43 % | 100.00 % |
| vox:atgpi | 408 | 4.66 % | 100.00 % |
| vox:aufkn | 620 | 16.77 % | 97.30 % |
| vox:azisu | 651 | 17.36 % | 100.00 % |
| vox:bauzd | 1730 | 5.43 % | 100.00 % |
| vox:bdopb | 2914 | 2.13 % | 100.00 % |
| vox:bkwns | 173 | 0.00 % | 100.00 % |
| vox:blwmj | 955 | 15.71 % | 100.00 % |
| vox:bravd | 1319 | 7.43 % | 100.00 % |
| vox:bspxd | 1337 | 5.76 % | 100.00 % |
| vox:bwzyf | 213 | 0.00 % | 100.00 % |
| vox:bxpwa | 1196 | 6.27 % | 100.00 % |
| vox:bydui | 958 | 9.29 % | 100.00 % |
| vox:ccokr | 684 | 2.92 % | 100.00 % |

### Embeddings (coseno por unidad; ref vs fast)

| pista | n | mediana | p1 | mín | ok (≥0,995 / ≥0,98) |
|---|---|---|---|---|---|
| siglip_fast | 3246 | 0.97964 | 0.88145 | 0.4697 | False (['median_ge_0.995', 'p1_ge_0.98']) |
| siglip_fp16_exact_frames_diag | 3246 | 1.00000 | 0.99998 | 0.9998 | True (cumple) |
| bge_transcript_units | 3149 | 1.00000 | 1.00000 | 0.9997 | True (cumple) |
| bge_vjudge_blocks | 437 | 1.00000 | 1.00000 | 1.0000 | True (cumple) |
| wavlm_fp16 | 2316 | 1.00000 | 1.00000 | 1.0000 | True (cumple) |
| rostros | — | — | — | — | **no evaluada**: variante de rostros no definida entre las variantes de esta validación; buffalo_l es research_only y no está en el pipeline de producto |

### VJudge / etiquetas (coseno bge entre textos ref y fast)

| pista | n | mediana cos | p1 | % idénticos | automático (mediana ≥ 0,90) | revisión humana (≥ 18/20) |
|---|---|---|---|---|---|---|
| vjudge_vllm_exact_frames | 437 | 1.0000 | 0.6628 | 56.06 % | True | pendiente de revisión humana |
| vjudge_vllm_decode_once | 437 | 0.8921 | 0.4829 | 14.19 % | False | pendiente de revisión humana |
| vjudge_chain_fast_all_tracks | 437 | 0.8208 | 0.4375 | 2.75 % | False | pendiente de revisión humana |
| labels_vllm_fp8 | 126 | 0.9797 | 0.7967 | 37.30 % | True | pendiente de revisión humana |

Diarización: **no se toca** (EXP-045-Q: «si se toca»); sin variante. Rostros: ver arriba.

## 2. Extremo a extremo (cada video; lectura estricta: todos los videos deben pasar)

Columnas: ARI unidad→tópico (≥0,95) · F1 fronteras ±1 (≥0,95) · Δ nº tópicos (≤2 %) · Δ retornos (≤2 %) · G-versión igual · IoU highlights10pct / recap60 (≥0,90) · capítulos con mismo tópico, Jaccard ≥ 0,9 (≥95 %).

### asr=fast — FALLA en: Spider_Man, ES2002c.Room, bbc_01, com_en_01, com_es_01

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.560 | 0.910 | 11.5 % (96→85) | 11.8 % (34→30) | True | 0.432 | 0.000 | 0.365 | False |
| ES2002c.Room | 0.904 | 0.800 | 40.0 % (5→7) | 0.0 % (0→0) | True | 1.000 | 1.000 | 0.600 | False |
| bbc_01 | 0.487 | 0.839 | 0.0 % (31→31) | 9.1 % (11→12) | True | 0.168 | 0.000 | 0.355 | False |
| com_en_01 | 0.651 | 0.806 | 8.3 % (24→26) | 14.3 % (7→6) | True | 0.000 | 0.000 | 0.435 | False |
| com_es_01 | 0.791 | 0.800 | 0.0 % (22→22) | 0.0 % (5→5) | True | 1.000 | 1.000 | 0.455 | False |

### visual=fast — FALLA en: Spider_Man, ES2002c.Room, bbc_01, com_en_01, com_es_01

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.327 | 0.848 | 1.0 % (96→97) | 44.1 % (34→49) | True | 0.468 | 0.000 | 0.271 | False |
| ES2002c.Room | 0.712 | 0.750 | 0.0 % (5→5) | 0.0 % (0→0) | True | 0.000 | 0.000 | 0.400 | False |
| bbc_01 | 0.556 | 0.857 | 6.5 % (31→33) | 36.4 % (11→15) | True | 0.180 | 0.000 | 0.387 | False |
| com_en_01 | 0.727 | 0.800 | 8.3 % (24→22) | 14.3 % (7→8) | True | 0.000 | 0.000 | 0.435 | False |
| com_es_01 | 0.821 | 0.857 | 9.1 % (22→24) | 20.0 % (5→4) | True | 1.000 | 1.000 | 0.500 | False |

### vjudge=fast — FALLA en: Spider_Man, ES2002c.Room, bbc_01, com_en_01, com_es_01

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.264 | 0.917 | 3.1 % (96→99) | 11.8 % (34→38) | True | 0.462 | 0.000 | 0.344 | False |
| ES2002c.Room | 0.923 | 0.667 | 20.0 % (5→6) | 0.0 % (0→0) | True | 1.000 | 1.000 | 0.600 | False |
| bbc_01 | 0.517 | 0.898 | 9.7 % (31→34) | 18.2 % (11→13) | True | 0.553 | 1.000 | 0.290 | False |
| com_en_01 | 0.537 | 0.816 | 8.3 % (24→26) | 71.4 % (7→12) | True | 0.000 | 0.000 | 0.261 | False |
| com_es_01 | 0.847 | 0.947 | 0.0 % (22→22) | 0.0 % (5→5) | True | 1.000 | 1.000 | 0.682 | False |

### vjudge=fast_exact(diag) — FALLA en: Spider_Man, ES2002c.Room, bbc_01, com_en_01, com_es_01

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.348 | 0.938 | 3.1 % (96→99) | 26.5 % (34→43) | True | 0.506 | 1.000 | 0.448 | False |
| ES2002c.Room | 0.953 | 0.889 | 0.0 % (5→5) | inf % (0→1) | True | 1.000 | 1.000 | 0.600 | False |
| bbc_01 | 0.592 | 0.902 | 3.2 % (31→30) | 0.0 % (11→11) | True | 0.326 | 1.000 | 0.452 | False |
| com_en_01 | 0.609 | 0.822 | 4.2 % (24→23) | 42.9 % (7→10) | True | 0.000 | 0.000 | 0.391 | False |
| com_es_01 | 0.953 | 0.982 | 0.0 % (22→22) | 20.0 % (5→6) | True | 1.000 | 1.000 | 0.818 | False |

### embed=fast — PASA en todos los videos

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.997 | 0.996 | 0.0 % (96→96) | 0.0 % (34→34) | True | 1.000 | 1.000 | 0.990 | True |
| ES2002c.Room | 1.000 | 1.000 | 0.0 % (5→5) | 0.0 % (0→0) | True | 1.000 | 1.000 | 1.000 | True |
| bbc_01 | 1.000 | 1.000 | 0.0 % (31→31) | 0.0 % (11→11) | True | 1.000 | 1.000 | 1.000 | True |
| com_en_01 | 1.000 | 1.000 | 0.0 % (24→24) | 0.0 % (7→7) | True | 1.000 | 1.000 | 1.000 | True |
| com_es_01 | 1.000 | 1.000 | 0.0 % (22→22) | 0.0 % (5→5) | True | 1.000 | 1.000 | 1.000 | True |

### ALL_fast_chain — FALLA en: Spider_Man, ES2002c.Room, bbc_01, com_en_01, com_es_01

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.187 | 0.805 | 3.1 % (96→93) | 20.6 % (34→41) | True | 0.462 | 0.000 | 0.188 | False |
| ES2002c.Room | 0.679 | 0.667 | 80.0 % (5→9) | 0.0 % (0→0) | True | 0.000 | 0.000 | 0.200 | False |
| bbc_01 | 0.380 | 0.752 | 3.2 % (31→32) | 36.4 % (11→15) | True | 0.103 | 0.000 | 0.129 | False |
| com_en_01 | 0.645 | 0.781 | 4.2 % (24→25) | 14.3 % (7→6) | True | 0.000 | 0.000 | 0.391 | False |
| com_es_01 | 0.633 | 0.679 | 4.5 % (22→23) | 20.0 % (5→6) | True | 1.000 | 1.000 | 0.318 | False |

### visual-fast_exact — PASA en todos los videos

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 1.000 | 1.000 | 0.0 % (96→96) | 0.0 % (34→34) | True | 1.000 | 1.000 | 1.000 | True |
| ES2002c.Room | 1.000 | 1.000 | 0.0 % (5→5) | 0.0 % (0→0) | True | 1.000 | 1.000 | 1.000 | True |
| bbc_01 | 1.000 | 1.000 | 0.0 % (31→31) | 0.0 % (11→11) | True | 1.000 | 1.000 | 1.000 | True |
| com_en_01 | 1.000 | 1.000 | 0.0 % (24→24) | 0.0 % (7→7) | True | 1.000 | 1.000 | 1.000 | True |
| com_es_01 | 1.000 | 1.000 | 0.0 % (22→22) | 0.0 % (5→5) | True | 1.000 | 1.000 | 1.000 | True |

### visual-fast_exact+embed-fast — PASA en todos los videos

| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |
|---|---|---|---|---|---|---|---|---|---|
| Spider_Man | 0.997 | 0.996 | 0.0 % (96→96) | 0.0 % (34→34) | True | 1.000 | 1.000 | 0.990 | True |
| ES2002c.Room | 1.000 | 1.000 | 0.0 % (5→5) | 0.0 % (0→0) | True | 1.000 | 1.000 | 1.000 | True |
| bbc_01 | 1.000 | 1.000 | 0.0 % (31→31) | 0.0 % (11→11) | True | 1.000 | 1.000 | 1.000 | True |
| com_en_01 | 1.000 | 1.000 | 0.0 % (24→24) | 0.0 % (7→7) | True | 1.000 | 1.000 | 1.000 | True |
| com_es_01 | 1.000 | 1.000 | 0.0 % (22→22) | 0.0 % (5→5) | True | 1.000 | 1.000 | 1.000 | True |

### Piso de ruido: corrida ref de este experimento vs salidas congeladas (otra GPU/versión de biblioteca)

| video | ARI | F1 | Δtóp | Δret | IoU hl | IoU recap |
|---|---|---|---|---|---|---|
| Spider_Man | 0.285 | 0.905 | 0.0 % | 19.0 % | 0.375 | 0.000 |
| bbc_01 | 0.437 | 0.810 | 3.1 % | 26.7 % | 0.269 | 0.000 |

## 3. Tiempos (s por hora de video; ref y fast, misma familia de GPU)

| etapa | ref s/h | fast s/h | aceleración |
|---|---|---|---|
| prepare | 1.4 | 6.1 | 0.23× |
| asr | 139.6 | 154.5 | 0.90× |
| signals | 116.8 | 42.4 | 2.75× |
| vjudge | 118.6 | 20.7 | 5.72× |
| topic_map | 6.1 | 0.6 | 10.46× |
| labels | 362.5 | 2.7 | 133.89× |
| speakers | 78.4 | 43.6 | 1.80× |
| versions_and_clips | 151.2 | 143.6 | 1.05× |
| **total** | 974.5 | 414.2 | 2.35× |


## 4. Aceleración medida y desviaciones

- Cadena `fast` completa (no adoptada): 974,5 → 414,2 s/h (2,35×) sobre los 5 videos (4,84 h). Por etapa: etiquetas 362,5 → 2,7 s/h (FP8+vLLM, pendiente de humano), vjudge 118,6 → 20,7, signals 116,8 → 42,4,
  mapa 6,1 → 0,6 (bge GPU), clips 151,2 → 143,6 (NVENC), ASR 139,6 → 154,5 (int8 **no** acelera: incluye carga/cuantización del modelo por video; VoxConverse 232,9 → 241,9 s/h).
- Conjunto adoptado (SigLIP FP16 exacto + bge GPU + WavLM FP16 + NVENC): mejora ≈ 1,0–1,1× extremo a extremo (estimación por etapas; la extracción ffmpeg por unidad domina `signals` y no cambia).
  Si la revisión humana aprueba las etiquetas FP8, la estimación por etapas es ≈ 1,6×.
- Cronometraje con ruido: la cadena ref se solapó con corridas auxiliares en la misma máquina (pyannote, idéntico en ref/fast, midió 322 s vs 161 s en Spider-Man). ref de Spider-Man: asr/signals/vjudge/labels
  reconstruidos por mtimes de la 1.ª pasada (falló pyannote por `LD_LIBRARY_PATH`; reanudación sin cronómetro). Fast de Spider-Man y docs en `.54` (misma GPU RTX PRO 4000, otra unidad): fast docs en `.54`, ref docs en `.56`.
- NVENC falló en la 1.ª pasada de Spider-Man (fuente H.264 High 10 bits: `CreateInputBuffer failed: invalid param (8)`); se añadió `-pix_fmt yuv420p` y se repitió solo la etapa de clips.
- R1/R3 tras los cambios: ver `nonregression_after/` (R3 PASS; R1 FAIL por ruido de 1e-7 en `provenance.transcript.coherence`, ver log).
