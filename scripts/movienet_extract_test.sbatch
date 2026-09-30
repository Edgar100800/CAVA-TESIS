#!/bin/bash
#SBATCH --job-name=mn_signals_test
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:32
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache
export HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA

python scripts/extract_movienet_signals.py --split test --require-story
