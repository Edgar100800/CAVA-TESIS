#!/bin/bash
#SBATCH --job-name=topic_labels
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=10:00:00
#SBATCH --output=logs/%x_%j.out

set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache
export HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
# los mapas con contexto se reconstruyen en CPU; esperar a que estén
while [ ! -f logs/maps_ctx.done ]; do sleep 60; done
python scripts/vjudge_topic_labels.py --maps data/topic_maps data/topic_maps_test --out data/topic_labels
echo TOPIC_LABELS_DONE
