#!/bin/bash
#SBATCH --job-name=cava_narrative
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --nodelist=ds001
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --array=0-1%1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x_%A_%a.out
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PATH="/home/edgar.chambilla/.conda/envs/segloop/bin:$PATH"
export OMP_NUM_THREADS=8
cd /home/edgar.chambilla/Tesis/CAVA
films=(Avengers_Endgame Spider_Man)
name="${films[$SLURM_ARRAY_TASK_ID]}"
python -u scripts/cava_narrative.py "data/films_runs/$name" \
  --out "data/films_narrative_v1/$name" --frames 10 --max-candidate-seconds 30 \
  --budget-fraction 0.10 --decode --require-continuity \
  --validated-by data/films_narrative_smoke_v1
