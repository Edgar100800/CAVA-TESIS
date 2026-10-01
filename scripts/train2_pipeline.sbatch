#!/bin/bash
#SBATCH --job-name=train2_pipe
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:rtxa6000:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=23:30:00
#SBATCH --output=logs/%x_%j.out

# EXP-019f/g: conjunto de confirmación nuevo (91 películas train nunca usadas).
# Solo genera datos con el mismo código que val/test/train; la evaluación se
# hace aparte con las reglas pre-registradas. Cada paso es resumible.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
F=scripts/exp019_train2_films.txt
python scripts/extract_movienet_signals.py --split train --films-file $F
python scripts/build_dialogue.py --films-file $F
(cd scripts && python vjudge_ledger.py --corpus ../data/movienet_topics --out ../data/vjudge_ledger_train2 \
   --summaries-only --fixed-units 8 --films $(cat exp019_train2_films.txt))
python scripts/build_topic_maps.py --films-file $F --dialogue-dir data/movienet_dialogue \
  --summary-dir data/vjudge_ledger_train2 --out data/topic_maps_train2
python scripts/build_content_gt.py --films-file $F
python scripts/vjudge_topic_labels.py --maps data/topic_maps_train2 --out data/topic_labels
python scripts/vjudge_topic_labels.py --maps data/topic_maps_train2 --out data/topic_labels_reg \
  --registry-from data/topic_labels --registry-only
echo TRAIN2_PIPELINE_DONE
