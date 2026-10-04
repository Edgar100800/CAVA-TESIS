#!/bin/bash
#SBATCH --job-name=ami_signals_f3
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=20:00:00
#SBATCH --output=logs/%x_%j.out
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
# la descarga (nodo de login) debe terminar antes
while ! grep -q DOWNLOAD_DONE data/ami/download_fresh3.log; do sleep 120; done
python scripts/ami_signals.py --meetings data/ami/meetings_fresh3.txt
echo AMI_SIGNALS_DONE
