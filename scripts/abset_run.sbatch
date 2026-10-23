#!/bin/bash
#SBATCH --job-name=abset_run
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:14
#SBATCH --nodelist=g002
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.out
# Conjunto propio para la evaluación A/B (data/abset/manifest.csv): CAVA con el stack congelado, contrato cava-run-v1,
# directorio nuevo. Perfil por video según el manifiesto (conversación → meeting; el resto → documentary).
# Shards de la RTX A6000 de g002 (sin A100 completa disponible). Un comando por video: si uno falla, los demás siguen.
# stdin de cada corrida a /dev/null: ffmpeg consumía el resto del manifiesto (job 58337 solo corrió el primer video).
set -uo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
tail -n +2 data/abset/manifest.csv | while IFS=, read -r id url tipo perfil idioma notas; do
  [ -f "data/cava_runs_abset/$id/clips.jsonl" ] && { echo "YA HECHO: $id"; continue; }
  python scripts/cava_run.py "data/abset/videos/$id.mp4:$perfil" --out data/cava_runs_abset < /dev/null || echo "FALLÓ: $id"
done
echo ABSET_DONE
