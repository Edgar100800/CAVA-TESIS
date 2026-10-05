#!/bin/bash
#SBATCH --job-name=exp030_asr
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=20:00:00
#SBATCH --output=logs/%x_%j.out
# EXP-030: transcripciones Parakeet por unidad + Whisper en VoxConverse.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/exp030_cache.py
echo EXP030_CACHE_DONE
