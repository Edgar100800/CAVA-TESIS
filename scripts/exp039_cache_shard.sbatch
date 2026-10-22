#!/bin/bash
#SBATCH --job-name=exp039_cache_s
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:14
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
# EXP-039: cachés de domix (mismo código de EXP-034).
# Variante en shards de RTX A6000 (g002 o ds001): el job 56271 con gpu:1 genérico cayó en un MIG chico de ag001 y dio CUDA OOM.
# El caché salta los items ya escritos, así que retoma donde quedó.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/exp034_cache.py --doms domix
