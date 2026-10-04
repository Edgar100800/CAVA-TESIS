#!/bin/bash
#SBATCH --job-name=exp023_confirm
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:4
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%j.out
# EXP-021c + EXP-022: confirmación pre-registrada en las 40 reuniones nuevas (una ejecución).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/eval_ami.py --meetings data/ami/meetings_fresh3.txt --percentile 95 --return-percentile 90 --turns-w 6 --out results/exp023_ami_fresh3.json
echo AMI_CONFIRM_DONE
