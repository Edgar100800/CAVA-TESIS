#!/bin/bash
#SBATCH --job-name=cava_films
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --nodelist=ds001
#SBATCH --array=0-1%1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=logs/%x_%A_%a.out
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PATH="/home/edgar.chambilla/.conda/envs/segloop/bin:$PATH"
cd /home/edgar.chambilla/Tesis/CAVA
python -c 'import torch; free, total = torch.cuda.mem_get_info(); print(f"GPU free: {free / 2**30:.1f} GiB", flush=True); assert free >= 35 * 2**30, "CAVA requires at least 35 GiB free for the 14B labels model; retry when GPU is free"'
python -u scripts/run_uploaded_films.py "$SLURM_ARRAY_TASK_ID" < /dev/null
