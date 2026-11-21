#!/bin/bash
# servers.sh start|stop|health   (comandos exactos de docs/infra/RUNBOOK_GPU.md; PID guardado; nunca pkill -f)
K=/data/tesis-cava/exports/deploy_exp036_shards_20261111/id_ed25519
SSH="ssh -i $K -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15"
case "$1" in
start)
$SSH utec_alumno@10.100.41.61 'V=/data/tesis-cava/envs/cava-vllm-033-uv; B=/data/tesis-cava/bench-data
nohup env HF_HUB_OFFLINE=1 $V/bin/vllm serve /data/tesis-cava/models/bench-qwen25-14b-cf98f3b3 \
  --served-model-name qwen14b-fp8 --quantization fp8 --dtype bfloat16 \
  --gpu-memory-utilization 0.90 --max-model-len 4096 --max-num-seqs 100 \
  --host 127.0.0.1 --port 8000 > $B/exp045-qwen14b-vllm.log 2>&1 &
echo $! > $B/exp045-qwen14b-vllm.pid; echo started 61 $(cat $B/exp045-qwen14b-vllm.pid)'
$SSH utec_alumno@10.100.41.55 'V=/data/tesis-cava/envs/cava-vllm-033; B=/data/tesis-cava/bench-data
nohup env CC=/usr/bin/gcc-12 \
  CPATH=/data/tesis-cava/tools/pythons/cpython-3.12.16-linux-x86_64-gnu/include/python3.12 HF_HUB_OFFLINE=1 \
  $V/bin/vllm serve /data/tesis-cava/models/bench-qwen25-vl7b-cc594898 \
  --served-model-name qwen-vl7b-bf16 --dtype bfloat16 \
  --gpu-memory-utilization 0.90 --max-model-len 4096 --max-num-seqs 100 \
  --host 127.0.0.1 --port 8000 > $B/exp045-qwenvl-vllm.log 2>&1 &
echo $! > $B/exp045-qwenvl-vllm.pid; echo started 55 $(cat $B/exp045-qwenvl-vllm.pid)';;
stop)
$SSH utec_alumno@10.100.41.61 'B=/data/tesis-cava/bench-data; kill -TERM "$(cat $B/exp045-qwen14b-vllm.pid)"; sleep 20; nvidia-smi --query-gpu=memory.used --format=csv,noheader'
$SSH utec_alumno@10.100.41.55 'B=/data/tesis-cava/bench-data; kill -TERM "$(cat $B/exp045-qwenvl-vllm.pid)"; sleep 20; nvidia-smi --query-gpu=memory.used --format=csv,noheader';;
health)
for h in 61 55; do $SSH utec_alumno@10.100.41.$h 'python3 -c "import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8000/health\").status)" 2>&1 | tail -1; nvidia-smi --query-gpu=memory.used --format=csv,noheader'; done;;
esac
