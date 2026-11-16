#!/bin/bash
#SBATCH --job-name=cava_narrative_dispatch
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=standard
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=logs/%x_%j.out
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1
cd /home/edgar.chambilla/Tesis/CAVA
python -u scripts/narrative_dispatch.py
