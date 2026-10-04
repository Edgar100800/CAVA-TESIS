#!/bin/bash
#SBATCH --job-name=bbc_doc_b
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=20:00:00
#SBATCH --output=logs/%x_%j.out
# Producto: perfil documentary (EXP-025) en los 11 episodios BBC, con etiquetas 14B y clips mp4.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
S=/home/edgar.chambilla/Tesis/SegLoop/data
python scripts/cava_run.py  $S/bbc/raw/bbc_07.mp4:documentary $S/bbc/raw/bbc_08.mp4:documentary $S/bbc/raw/bbc_09.mp4:documentary $S/bbc/raw/bbc_10.mp4:documentary $S/bbc/raw/bbc_11.mp4:documentary --out data/cava_runs_doc
echo BBC_DOC_DONE
