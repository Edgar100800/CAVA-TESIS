#!/bin/bash
#SBATCH --job-name=exp028
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
# EXP-028: WavLM speaker embedding frente a rasgos de voz en VoxConverse. Uso: sbatch exp028.sbatch dev|test
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/eval_speaker_embed.py --split $1 --out results/exp028_voxconverse_$1.json
echo EXP028_DONE
