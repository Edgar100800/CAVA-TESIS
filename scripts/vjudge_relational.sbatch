#!/bin/bash
#SBATCH --job-name=vj_relational
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA/scripts
python vjudge_relational.py --corpus ../data/movienet_topics --voters ../data/movienet_voters \
  --out ../data/vjudge_relational --top 100 --conditions mm frames
