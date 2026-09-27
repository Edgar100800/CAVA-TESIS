#!/bin/bash
#SBATCH --job-name=vjudge_movie
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA

python scripts/vjudge_movie_shots.py \
  --movies tt0047396 tt0049730 tt0061418 \
  --out /home/edgar.chambilla/Tesis/CAVA/data/mn_reasoning
