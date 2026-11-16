#!/bin/bash
# EXP-036 F5 cobertura completa: ejecuta UNA partición del manifiesto en esta PC (una GPU, un trabajo).
# Uso: full_worker.sh K N CAVA_ROOT [OUTDIR]
#   CAVA_ROOT: /data/tesis-cava/CAVA_minimo (.56) o /data/tesis-cava/cava-exp036 (L507); contiene .venv y models/
#   OUTDIR   : por defecto <tramos>/full/shardK; los reintentos/reasignaciones usan otra carpeta
# Escribe en OUTDIR: pid, worker.log, briefs_tramos_<mov>.json, gpu_time.jsonl, rc, done.
# FAKE=1 (prueba del orquestador): no usa la GPU; duerme FAKE_SLEEP s y sale con FAKE_RC.
set -u
K=${1:?K}; N=${2:?N}; CR=${3:?CAVA_ROOT}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${4:-$HERE/full/shard$K}
mkdir -p "$OUT"
rm -f "$OUT/done" "$OUT/rc"
echo $$ > "$OUT/pid"
echo "$(date '+%F %T') inicio shard $K/$N host=$(hostname) out=$OUT" >> "$OUT/worker.log"
if [ "${FAKE:-0}" = 1 ]; then
  sleep "${FAKE_SLEEP:-10}"; rc=${FAKE_RC:-0}
else
  PY="$CR/.venv/bin/python"
  SP=$("$PY" -c "import site;print(site.getsitepackages()[0])")
  export LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib:$SP/nvidia/cuda_runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  "$PY" -I "$HERE/tramo_briefs.py" --cava "$CR" --manifest "${MANIFEST:-$HERE/full/manifest_full.json}" \
    --shard "$K/$N" --batch 8 --out-dir "$OUT" >> "$OUT/worker.log" 2>&1
  rc=$?
fi
echo "$rc" > "$OUT/rc"
echo "$(date '+%F %T') fin rc=$rc" >> "$OUT/worker.log"
date '+%F %T' > "$OUT/done"
