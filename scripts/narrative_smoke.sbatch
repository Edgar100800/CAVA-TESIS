#!/bin/bash
#SBATCH --job-name=cava_narrative_smoke
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --nodelist=ag001
#SBATCH --gres=gpu:a100_3g.20gb:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x_%j.out
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PATH="/home/edgar.chambilla/.conda/envs/segloop/bin:$PATH"
export OMP_NUM_THREADS=8
cd /home/edgar.chambilla/Tesis/CAVA
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
for name in Avengers_Endgame Spider_Man; do
  # Existing four-minute baseline runs supply real audio, ASR, map and video.
  # A larger smoke budget exercises multiple transitions rather than a single shot.
  python -u scripts/cava_narrative.py "data/films_smoke/${name}_sample_660_240" \
    --out "data/films_narrative_smoke_v1/$name" --frames 10 --max-candidate-seconds 30 \
    --budget-fraction 0.5 --decode --require-continuity
done
echo NARRATIVE_SMOKE_DONE
