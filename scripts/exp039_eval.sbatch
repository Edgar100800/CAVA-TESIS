#!/bin/bash
#SBATCH --job-name=exp039_eval
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=standard
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=02:00:00
# EXP-039: detectores, selección en dev y confirmación (CPU sobre las cachés).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/exp039_detect.py
