#!/bin/bash
#SBATCH --job-name=exp039_mix
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --output=logs/%x_%j.out
#SBATCH --partition=standard
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
# EXP-039: genera domix (voces dominantes con estructura de documental).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/exp039_mix.py
