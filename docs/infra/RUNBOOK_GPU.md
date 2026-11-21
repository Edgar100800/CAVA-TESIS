# Runbook GPU — CAVA Signals

Fecha de referencia: 2026-11-20. Uso de `buffalo_l`: **solo investigación, no comercial**.
Este runbook cubre solo **velocidad y memoria**. La calidad de cualquier variante (FP8, int8_float16, AWQ, vLLM
frente a HF) está bloqueada por la preinscripción EXP-045-Q en `docs/EXPERIMENT_LOG.md`; no se midió ni se infiere de aquí.

## Máquinas y entornos

| Máquina | GPU / controlador | Uso | Entorno aislado |
|---|---|---|---|
| `.61` | RTX PRO 4000 Blackwell 24 GB (sm_120); 595.99.02 | Qwen2.5-14B FP8 (y AWQ plan B), faster-whisper | `/data/tesis-cava/envs/cava-vllm-033-uv`, `/data/tesis-cava/envs/cava-whisper-bench` |
| `.55` | idem; 580.126.09 | Qwen2.5-VL-7B BF16 | `/data/tesis-cava/envs/cava-vllm-033` |
| `.56` | local (laboratorio de producto) | InsightFace/ORT | `CAVA_minimo/.venv` (ver más abajo) |

Python 3.12.3 del sistema, sin `pip`/`ensurepip`/`curl` en `.55/.61`: se usa `uv` en `/data/tesis-cava/tools/uv`
(caché `UV_CACHE_DIR=/data/tesis-cava/cache/uv`). No se tocaron `~/thesis-venv` ni `~/dia-venv`.
Pesos (revisiones fijadas) en `/data/tesis-cava/models/`:

- `.61`: `bench-qwen25-14b-cf98f3b3/` (Qwen2.5-14B-Instruct `cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8`, 28 GB),
  `bench-faster-whisper-large-v3-edaa852/` (2,9 GB), `bench-qwen25-14b-awq/` (oficial `Qwen/Qwen2.5-14B-Instruct-AWQ`),
  y el preexistente `qwen2.5-32b-awq/` (19 GB, no usado).
- `.55`: `bench-qwen25-vl7b-cc594898/` (Qwen2.5-VL-7B-Instruct `cc594898137f460bfe9f0759e9844b3ce807cfb5`, 16 GB).

## Instalar vLLM (venv nuevo)

```bash
export UV_CACHE_DIR=/data/tesis-cava/cache/uv
UV=/data/tesis-cava/tools/uv; VENV=/data/tesis-cava/envs/cava-vllm-033
$UV venv --python /usr/bin/python3 $VENV
$UV pip install --python $VENV/bin/python --torch-backend=auto 'vllm==0.33.0'
$UV pip install --python $VENV/bin/python pip          # download-kernels invoca pip
$VENV/bin/vllm download-kernels                         # FlashInfer cubin + jit-cache (incl. sm120f)
```

Versiones verificadas en ambas máquinas: vLLM 0.33.0, PyTorch 2.14.0+cu132 (CUDA 13.2), arch list incluye `sm_120`,
FlashInfer 0.7.2.post1. El venv preexistente `~/exp036-vllm/venv` (vLLM 0.33.0, torch 2.14.0+cu130) no se usó ni modificó.

**Requisito del VL-7B (Triton):** el codificador de visión compila un stub en C. Faltan `python3-dev` y el alias `gcc`
en `.55`, así que se usa `CC=/usr/bin/gcc-12` y las cabeceras de un Python de `uv`
(`UV_PYTHON_INSTALL_DIR=/data/tesis-cava/tools/pythons uv python install 3.12`) vía `CPATH`. Sin esto el arranque falla con
`RuntimeError: Failed to find C compiler` y luego con falta de `Python.h`. El 14B (solo texto) no lo necesita.

## Arrancar y detener servidores

Escuchan en `127.0.0.1:8000` (un servidor por máquina); desde fuera, túnel `ssh -L 8000:127.0.0.1:8000`. Arranque ≈ 2–3 min
(carga + compilación + grafos CUDA). No ejecutar los dos servidores en la misma GPU.

### `.61` — Qwen2.5-14B-Instruct FP8 dinámico (puerto 8000, modelo `qwen14b-fp8`)

```bash
V=/data/tesis-cava/envs/cava-vllm-033-uv; B=/data/tesis-cava/bench-data
nohup env HF_HUB_OFFLINE=1 $V/bin/vllm serve /data/tesis-cava/models/bench-qwen25-14b-cf98f3b3 \
  --served-model-name qwen14b-fp8 --quantization fp8 --dtype bfloat16 \
  --gpu-memory-utilization 0.90 --max-model-len 4096 --max-num-seqs 100 \
  --host 127.0.0.1 --port 8000 > $B/qwen14b-vllm.log 2>&1 &
echo $! > $B/qwen14b-vllm.pid
```
(`--quantization fp8` avisa de que está obsoleto; la alternativa es `fp8_per_tensor`. Pesos cargados: 15,38 GiB.)

### `.61` — plan B: Qwen2.5-14B-Instruct-AWQ oficial (puerto 8000, modelo `qwen14b-awq`)

```bash
nohup env HF_HUB_OFFLINE=1 $V/bin/vllm serve /data/tesis-cava/models/bench-qwen25-14b-awq \
  --served-model-name qwen14b-awq --quantization awq_marlin --dtype float16 \
  --gpu-memory-utilization 0.90 --max-model-len 4096 --max-num-seqs 100 \
  --host 127.0.0.1 --port 8000 > $B/qwen14b-awq-vllm.log 2>&1 &
echo $! > $B/qwen14b-awq-vllm.pid
```

### `.55` — Qwen2.5-VL-7B-Instruct BF16 (puerto 8000, modelo `qwen-vl7b-bf16`)

```bash
V=/data/tesis-cava/envs/cava-vllm-033; B=/data/tesis-cava/bench-data
nohup env CC=/usr/bin/gcc-12 \
  CPATH=/data/tesis-cava/tools/pythons/cpython-3.12.16-linux-x86_64-gnu/include/python3.12 HF_HUB_OFFLINE=1 \
  $V/bin/vllm serve /data/tesis-cava/models/bench-qwen25-vl7b-cc594898 \
  --served-model-name qwen-vl7b-bf16 --dtype bfloat16 \
  --gpu-memory-utilization 0.90 --max-model-len 4096 --max-num-seqs 100 \
  --host 127.0.0.1 --port 8000 > $B/qwenvl-vllm.log 2>&1 &
echo $! > $B/qwenvl-vllm.pid
```

### Comprobar y detener

```bash
python3 -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:8000/health").status)'   # 200
kill -TERM "$(cat $B/<modelo>.pid)"; sleep 15; nvidia-smi --query-gpu=memory.used --format=csv,noheader   # ≈ 200 MiB
```
No usar `pkill -f "vllm serve"` por ssh: la propia sesión ssh contiene esa cadena y se mata. Al cerrar este trabajo
**los tres servidores están detenidos** y las GPU de `.55/.61` quedan libres (≈ 200 MiB usados).

## Medición de rendimiento (solo velocidad/memoria)

Carga: `infra/prepare_label_bench.py` construye 100 prompts con la plantilla real de etiquetas (`topicagg/labels.py`) sobre
el mapa congelado de Spider-Man (57 tópicos ≥ 30 s, ciclados hasta 100). `infra/bench_vllm_api.py`: calentamiento fuera de
ventana, 100 peticiones concurrentes, `max_tokens=70`, temperatura 0; solo guarda tokens de uso, latencias y memoria
(`nvidia-smi` cada 200 ms); no guarda ni lee el texto generado. El benchmark de VL es **solo texto** (sin imágenes).
Con `--max-model-len 4096` y prefijo en caché activado, la **ejecución 1 (fría) es la cifra de referencia**; la 2 se beneficia
del caché de prefijos (mismos 100 prompts) y solo indica el techo.

| Modelo / máquina | Ejec. | Lote 100 (s) | Tokens salida/s | Tokens totales/s | Latencia med / p95 (s) | VRAM pico (MiB) |
|---|---|---:|---:|---:|---|---:|
| Qwen2.5-14B FP8 / `.61` | 1 (fría) | 9,10 | 285,8 | 6 085 | 7,31 / 8,91 | 20 917 |
| Qwen2.5-14B FP8 / `.61` | 2 (caché) | 7,41 | 344,3 | 7 463 | 5,55 / 7,07 | 20 917 |
| Qwen2.5-VL-7B BF16 / `.55` | 1 (fría) | 6,16 | 544,2 | 8 948 | 5,37 / 5,92 | 20 348 |
| Qwen2.5-VL-7B BF16 / `.55` | 2 (caché) | 2,34 | 1 452,5 | 23 586 | 1,30 / 1,91 | 20 348 |
| Qwen2.5-14B AWQ (`awq_marlin`, fp16) / `.61` | 1 (fría) | 10,62 | 233,7 | 5 203 | 9,73 / 9,94 | 20 973 |
| Qwen2.5-14B AWQ / `.61` | 2 (caché) | 2,48 | 1 002,8 | 22 321 | 1,63 / 1,81 | 20 973 |

Pesos AWQ cargados: 9,38 GiB. La ejecución 2 de FP8 (7,4 s) frente a la de AWQ/VL (≈ 2,4 s) no es comparable: con una sola
repetición por variante la caché de prefijos y la fase de calentamiento de grafos introducen mucha varianza; solo las
ejecuciones frías (1) son comparables entre sí, y aun así son una sola muestra (n = 1), no una distribución.

La VRAM (≈ 20 GB) es sobre todo caché KV reservado con `--gpu-memory-utilization 0.90`; el peso del 14B FP8 son 15,4 GiB.
Referencia de producto actual: 57 etiquetas de Spider-Man con HF + offload ≈ 886 s por película (plan §1); en esta carga
100 etiquetas tardan ≈ 9 s. No es comparable 1:1 (la carga y la longitud de salida difieren) y no implica calidad equivalente.

### faster-whisper large-v3 (clip de 10 min de `Spider_Man/work/audio.wav`, `.61`)

faster-whisper 1.2.1, CTranslate2 4.9.0, `vad_filter=True` (como el producto). Se consumen los segmentos; no se lee el texto.
Se repitió cada tipo dos veces (la 1.ª fp16 incluye arranque en frío).

| compute_type | Inferencia (s) | RTF | min audio / min pared | VRAM pico (MiB) |
|---|---:|---:|---:|---:|
| float16 (1.ª / 2.ª) | 23,84 / 18,02 | 0,0397 / 0,0300 | 25,2 / 33,3 | 5 815 |
| int8_float16 (1.ª / 2.ª) | 17,26 / 16,45 | 0,0288 / 0,0274 | 34,8 / 36,5 | 4 215 / 4 023 |

Comparando en caliente: int8_float16 es ≈ 1,10× más rápido y usa ≈ 1,4 GB menos (el 1,3–1,6× esperado en el plan no se
observó en este clip). Requiere CTranslate2 ≥ 4.9 en sm_120 (INT8 fue deshabilitado en 4.6.2 y rehabilitado después).

## ONNX Runtime / InsightFace en `.56` (`CAVA_minimo/.venv`)

Antes: `onnx 1.23.2`, `onnxruntime 1.31.1`, `onnxruntime-gpu 1.22.0` (el módulo cargado era 1.22.0 y el CUDA EP caía a CPU).
Después: `onnx 1.23.2`, `onnxruntime-gpu 1.22.0` (se desinstaló `onnxruntime` CPU y se reinstaló el wheel GPU).
El CUDA EP de ORT 1.22 enlaza `libcublasLt.so.12`, `libcublas.so.12`, `libcurand.so.10`, `libcufft.so.11`, `libcudart.so.12`,
`libcudnn.so.9`, `libnvrtc.so.12`; están en `site-packages/nvidia/*/lib` pero el cargador no las busca: se usa
`source infra/env_cuda.sh` (ajusta `LD_LIBRARY_PATH`). Verificación hecha por el agente principal en `.56` con ese script:
`FaceAnalysis(buffalo_l)` prepare + detección real, providers `['CUDAExecutionProvider', 'CPUExecutionProvider']`. Alternativa en código:
`onnxruntime.preload_dlls(directory="")`. `infra/verify_face_cuda.py` es la prueba reutilizable.

## Incidencias conocidas

- `pip check` advierte que `insightface` y `faster-whisper` piden `onnxruntime` (CPU). No reinstalarlo: pisa el módulo del wheel GPU.
- faster-whisper 1.2.1 con PyAV ≥ 19: `TypeError: open() got an unexpected keyword argument 'metadata_errors'`. Fijar `av<19`
  (se usó 18.1.0) hasta que haya release con el arreglo ya fusionado en master.
- `bench_whisper.py` necesita el WAV legible por `wave` (usa PCM 16 kHz) y `env_cuda.sh <venv>` para cuBLAS/cuDNN.
- vLLM imprime `Failed to get device capability: RuntimeError('SM 120 requires CUDA >= 12.8')` en procesos auxiliares; es
  ruido de detección (el motor corre en sm_120).
- `.56`: ssh con la clave del laboratorio devuelve `Permission denied`; es la máquina local, no hace falta ssh.
- No ejecutar trabajos GPU en `.54`/`.56`; no modificar `thesis-venv`/`dia-venv`.

## Lecciones operativas de EXP-045-Q (2026-11-20)

- `.54/.55/.61` **no tienen `ffmpeg`/`ffprobe`** (ni sudo). Se copió el binario de `.56` con sus bibliotecas (`ldd`, 236 MB) a
  `/data/tesis-cava/exp045/ffbin/{ffmpeg,ffprobe,lib}` y se usa con `PATH` y `LD_LIBRARY_PATH` (NVENC funciona con el controlador).
- La red `.56 → .54` rinde ≈ 10 MB/s: no copiar los Qwen (44 GB). Las corridas ref con HF (VL-7B, 14B) se hacen donde están los pesos
  (`.56`); `.54` solo recibió el venv de producto (8,2 GB), los modelos de codificadores y las entradas.
- Con `source infra/env_cuda.sh` el subproceso de pyannote falla (`CUDNN_STATUS_SUBLIBRARY_LOADING_FAILED`) porque hereda el
  `LD_LIBRARY_PATH` con el cuDNN del venv de producto: quitar `LD_LIBRARY_PATH` solo para `run_diarization` (ver `exp045/chain.sh`).
- El 14B BF16 (29,5 GB) no cabe en 24 GB: la etapa de etiquetas ref usa `device_map="auto"` con `max_memory={0:"21GiB","cpu":"55GiB"}`
  cuando la GPU tiene < 40 GB (misma numérica; solo cambia la colocación de capas).
- Clientes de vLLM: túneles `ssh -N -L 8100:127.0.0.1:8000 .55` (VL) y `-L 8200:127.0.0.1:8000 .61` (14B) desde `.56`, y
  `-R 8100:… -R 8200:…` hacia `.54`; nada se expone en la LAN. `topicagg/variants.py` lee `CAVA_VLLM_{VL,TXT}_URL`.
- `repetition_penalty=1.05` (de `generation_config.json`) se envía explícito a vLLM; `HF generate(do_sample=False)` lo conserva.
