#!/bin/bash
#SBATCH --job-name=ami_eval
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:4
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%j.out
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/eval_ami.py --meetings data/ami/dev_20.txt --out results/exp020_ami_dev.json
python scripts/eval_ami.py --meetings data/ami/conf_20.txt --out results/exp020_ami_conf.json
echo AMI_EVAL_DONE
