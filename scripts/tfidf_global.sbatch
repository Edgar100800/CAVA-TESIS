#!/bin/bash
#SBATCH --job-name=tfidf_global
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=standard
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1
cd /home/edgar.chambilla/Tesis/CAVA
export PYTHONPATH=/home/edgar.chambilla/Tesis/CAVA

python scripts/build_global_tfidf.py
