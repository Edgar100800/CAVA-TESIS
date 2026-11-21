#!/bin/bash
# launch.sh ARGS...   — entorno de EXP-046-STAB (igual que infra/exp045/chain.sh) y exec de scripts/exp046_run.py
# En .55/.61/.54 pyannote usa ~/dia-venv vía el envoltorio dia_py.sh (CAVA_DIA_PYTHON / CAVA_DIA_HF_CACHE).
cd /data/tesis-cava/CAVA
source infra/env_cuda.sh /data/tesis-cava/CAVA_minimo/.venv
export HF_HOME=/data/tesis-cava/CAVA_minimo/models HF_HUB_CACHE=/data/tesis-cava/CAVA_minimo/models/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PATH=/data/tesis-cava/exp045/ffbin:$PATH
export LD_LIBRARY_PATH=/data/tesis-cava/exp045/ffbin/lib:$LD_LIBRARY_PATH
if [ ! -d /data/tesis-cava/dia-venv ]; then
  export CAVA_DIA_PYTHON=/data/tesis-cava/exp046/dia_py.sh CAVA_DIA_HF_CACHE=$HOME/exp043_dia/hf_dia
fi
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 TOKENIZERS_PARALLELISM=false
exec /data/tesis-cava/CAVA_minimo/.venv/bin/python -I scripts/exp046_run.py "$@"
