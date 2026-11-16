#!/bin/bash
#SBATCH --job-name=cava_films_smoke
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --nodelist=ds001
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
cd /home/edgar.chambilla/Tesis/CAVA
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv
if [[ "${CAVA_SMOKE_FULL_GPU:-0}" == 1 ]]; then
    python -c 'import torch; free, total = torch.cuda.mem_get_info(); assert free >= 35 * 2**30, "Need 35 GiB free for full GPU validation"'
    # Fresh intervals: CPU-generated labels from the first smoke are not reused.
    python -u scripts/run_uploaded_films.py 0 --sample-start 660 --sample-seconds 240
    python -u scripts/run_uploaded_films.py 1 --sample-start 660 --sample-seconds 240
else
    python -u scripts/run_uploaded_films.py 0 --sample-seconds 240 --smoke-cpu-labels
    python -u scripts/run_uploaded_films.py 1 --sample-seconds 240 --smoke-cpu-labels
fi
echo FILMS_SMOKE_DONE
