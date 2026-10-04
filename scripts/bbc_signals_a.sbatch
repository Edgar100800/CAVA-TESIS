#!/bin/bash
#SBATCH --job-name=bbc_sig_a
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=20:00:00
#SBATCH --output=logs/%x_%j.out
# EXP-025/026: señales CAVA (ASR, voz, visual, VJudge) + mapa de tópicos de episodios BBC Planet Earth.
# Sin etiquetas 14B ni cortes de clips: solo lo que usa la evaluación.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
S=/home/edgar.chambilla/Tesis/SegLoop/data
python scripts/cava_run.py  $S/bbc/raw/bbc_03.mp4:film $S/bbc/raw/bbc_04.mp4:film $S/bbc/raw/bbc_05.mp4:film $S/bbc/raw/bbc_06.mp4:film $S/bbc/raw/bbc_07.mp4:film --out data/cava_runs --no-cut --no-labels
echo BBC_SIGNALS_DONE
