#!/bin/bash
# Calibración de EXP-019g en DESARROLLO (47 train ya usadas). No toca train2.
source /etc/profile.d/lmod.sh; module load miniconda/3.0; conda activate segloop
export HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
M=data/topic_maps_train; S=data/vjudge_ledger_train8; F=scripts/exp016_train_films.txt
for a in ${CAL_ABS:-0.70 0.75 0.80 0.85}; do for m in 0.02 0.05 0.10; do
  n=cal_a${a}_m${m}
  python scripts/categorize_characters.py --maps $M --summary-dir $S --out data/$n --no-ids --registry-abs $a --registry-margin $m > /dev/null 2>&1
  python scripts/eval_categorization.py --films-file $F --maps $M --labels-dir data/$n --out results/exp019g_$n.json > /dev/null 2>&1
  echo "done $n"
done; done
echo CALIBRATION_DONE
