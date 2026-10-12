#!/bin/bash
#SBATCH --job-name=exp039_ina
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=standard
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=12:00:00
# EXP-039: inaSpeechSegmenter sobre domix (env inaseg, CPU).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0

export PYTHONNOUSERSITE=1 CUDA_VISIBLE_DEVICES=""
cd /home/edgar.chambilla/Tesis/CAVA
~/.conda/envs/inaseg/bin/python scripts/exp034_ina.py --doms domix
