#!/bin/bash
#SBATCH --job-name=run_zifr
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
# Caso manual test-video: Zifr_c0dTlc (resumen narrado de pelicula, 35:11),
# perfil documentary (EXP-025, narrador unico) con etiquetas 14B y clips mp4.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/cava_run.py \
  test-video/Zifr_c0dTlc/Zifr_c0dTlc.mp4:documentary \
  --out test-video/Zifr_c0dTlc
echo RUN_ZIFR_DONE
