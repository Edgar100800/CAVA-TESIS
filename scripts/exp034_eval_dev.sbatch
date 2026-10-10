#!/bin/bash
#SBATCH --job-name=exp034_dev
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=standard
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
# EXP-034: selección en AVA dev (congela el filtro); narrador dev solo descriptivo.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/exp034_eval.py --mode dev
