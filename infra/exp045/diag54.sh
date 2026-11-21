#!/bin/bash
cd /data/tesis-cava/CAVA
source infra/env_cuda.sh /data/tesis-cava/CAVA_minimo/.venv
export HF_HOME=/data/tesis-cava/CAVA_minimo/models HF_HUB_CACHE=/data/tesis-cava/CAVA_minimo/models/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PATH=/data/tesis-cava/exp045/ffbin:$PATH LD_LIBRARY_PATH=/data/tesis-cava/exp045/ffbin/lib:$LD_LIBRARY_PATH
/data/tesis-cava/CAVA_minimo/.venv/bin/python -I scripts/exp045_diag.py
echo DIAG_DONE
