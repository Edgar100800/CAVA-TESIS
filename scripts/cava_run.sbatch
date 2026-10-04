#!/bin/bash
#SBATCH --job-name=cava_run
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
# Contenido largo real con audio: 2 episodios BBC Planet Earth (~50 min, perfil film),
# 1 reunión AMI (perfil meeting) y 1 video TVSum (film).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
S=/home/edgar.chambilla/Tesis/SegLoop/data
python scripts/cava_run.py \
  $S/tvsum/ydata-tvsum50-v1_1/video/98MoyGZKHXc.mp4:film \
  data/ami/media/IS1000c/IS1000c.Room.avi:meeting:data/ami/media/IS1000c/IS1000c.Mix-Headset.wav \
  $S/bbc/raw/bbc_01.mp4:film \
  $S/bbc/raw/bbc_02.mp4:film \
  --out data/cava_runs
echo CAVA_RUN_DONE
