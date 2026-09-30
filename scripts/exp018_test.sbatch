#!/bin/bash
#SBATCH --job-name=exp018_test
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
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA

python scripts/exp018_test_films.py
python scripts/build_dialogue.py --films-file scripts/exp018_test_films.txt
(cd scripts && python vjudge_ledger.py --corpus ../data/movienet_topics --out ../data/vjudge_ledger_test8 \
   --summaries-only --fixed-units 8 --films $(cat exp018_test_films.txt))
# EXP-018: evaluación pre-registrada, una sola ejecución sobre test
python scripts/eval_topic_map.py --average --abstain --films-file scripts/exp018_test_films.txt \
  --dialogue-dir data/movienet_dialogue --summary-dir data/vjudge_ledger_test8 \
  --out results/exp018_test.json
echo EXP018_DONE
