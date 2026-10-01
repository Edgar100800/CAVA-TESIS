#!/bin/bash
#SBATCH --job-name=train_labels
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache
export HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
while [ ! -f logs/train_inputs.done ]; do sleep 60; done
# EXP-019e en train: etiquetas 019b y luego solo el registro (mismo código que val/test)
python scripts/vjudge_topic_labels.py --maps data/topic_maps_train --out data/topic_labels
python scripts/vjudge_topic_labels.py --maps data/topic_maps_train --out data/topic_labels_reg \
  --registry-from data/topic_labels --registry-only
echo TRAIN_LABELS_DONE
