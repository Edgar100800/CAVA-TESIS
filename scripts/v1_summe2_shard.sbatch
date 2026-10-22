#!/bin/bash
#SBATCH --job-name=v1_summe2s
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:14
#SBATCH --nodelist=g002
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=03:00:00
#SBATCH --output=logs/%x_%j.out
# Corrida limpia v1 en SumMe, segunda parte: los 6 videos que faltaron tras el job 56181 (falló en Scuba.mp4, sin pista de audio).
# Variante en shards de la RTX A6000 de g002 (sin A100 completa disponible; 57354 queda en cola como respaldo).
# Scuba y St Maarten Landing no tienen audio en la fuente (ni mp4 ni webm): entran con una pista silenciosa de su duración
# (data/summe_silent/). Un comando por video: si uno falla, los demás siguen.
set -uo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
for spec in "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Statue of Liberty.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Uncut_Evening_Flight.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Valparaiso_Downhill.mp4:film" \
            "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Scuba.mp4:film:data/summe_silent/Scuba.wav" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/St Maarten Landing.mp4:film:data/summe_silent/St Maarten Landing.wav" \
            "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos_corrupt/Cooking.mp4:film"; do
  python scripts/cava_run.py "$spec" --out data/cava_runs_v1_summe || echo "FALLÓ: $spec"
done
echo V1_DONE
