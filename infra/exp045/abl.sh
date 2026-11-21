#!/bin/bash
# abl.sh SPEC NAMES [--labels]
cd /data/tesis-cava/CAVA
source infra/env_cuda.sh /data/tesis-cava/CAVA_minimo/.venv
export HF_HOME=/data/tesis-cava/CAVA_minimo/models HF_HUB_CACHE=/data/tesis-cava/CAVA_minimo/models/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
/data/tesis-cava/CAVA_minimo/.venv/bin/python -I scripts/exp045_runs.py --spec "$1" --names "$2" ${3:+$3}
