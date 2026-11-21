#!/bin/bash
cd /data/tesis-cava/CAVA
source infra/env_cuda.sh /data/tesis-cava/CAVA_minimo/.venv
export HF_HOME=/data/tesis-cava/CAVA_minimo/models HF_HUB_CACHE=/data/tesis-cava/CAVA_minimo/models/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PATH=/data/tesis-cava/exp045/ffbin:$PATH LD_LIBRARY_PATH=/data/tesis-cava/exp045/ffbin/lib:$LD_LIBRARY_PATH
P=/data/tesis-cava/CAVA_minimo/.venv/bin/python
W=/data/tesis-cava/exp045/inputs/vox_dev; O=/data/tesis-cava/exp045/vox
$P -I scripts/exp045_vox.py --wavs $W --out $O --variant ref --stages asr
$P -I scripts/exp045_vox.py --wavs $W --out $O --variant fast --stages asr
$P -I scripts/exp045_vox.py --wavs $W --out $O --variant ref --stages xvec
$P -I scripts/exp045_vox.py --wavs $W --out $O --variant fast --stages xvec
echo VOX_DONE
