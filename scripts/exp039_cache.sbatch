#!/bin/bash
#SBATCH --job-name=exp039_cache
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
# EXP-039: cachés de domix (mismo código de EXP-034).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/exp034_cache.py --doms domix
