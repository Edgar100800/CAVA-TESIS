#!/bin/bash
#SBATCH --job-name=train2_eval
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:4
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.out

# Evaluación pre-registrada de EXP-019f y EXP-019g en train2 (una sola ejecución).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
M=data/topic_maps_train2; S=data/vjudge_ledger_train2; F=scripts/exp019_train2_films.txt
python scripts/categorize_characters.py --maps $M --summary-dir $S --out data/t2_links --no-registry --no-ids
python scripts/categorize_characters.py --maps $M --summary-dir $S --out data/t2_019g --no-ids --registry-abs 0.50 --registry-margin 0.10
python scripts/categorize_characters.py --maps $M --summary-dir $S --out data/t2_ids --no-registry
python scripts/categorize_characters.py --maps $M --summary-dir $S --out data/t2_ids_filtered --no-registry --identity-min-words 2
python scripts/eval_categorization.py --films-file $F --maps $M --labels-dir data/t2_links --out results/exp019g_t2_links.json
python scripts/eval_categorization.py --films-file $F --maps $M --labels-dir data/t2_019g --out results/exp019g_t2_019g.json
python scripts/eval_identities.py --films-file $F --maps $M --cat data/t2_ids --out results/exp019f_t2_unfiltered.json
python scripts/eval_identities.py --films-file $F --maps $M --cat data/t2_ids_filtered --out results/exp019f_t2_filtered.json
echo TRAIN2_EVAL_DONE
