#!/bin/bash
#SBATCH --job-name=exp040_base
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=shard:rtxa6000:14
#SBATCH --nodelist=ds001
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=logs/%x_%j.out
# EXP-040 (pre-registro): versiones de las bases U (sin estructura) y S (solo
# señal visual) para el A/B con personas, sobre los 9 videos del abset ya
# corridos con el stack congelado en data/cava_runs_abset/. ASR, señales y
# resúmenes vienen de la caché de ese run: la única GPU es el modelo de
# etiquetas Qwen2.5-14B, el mismo que CAVA. Shards de RTX A6000 (el mismo
# recurso de abset_run 58338; gpu:1 genérico cayó en un MIG chico de ag001 y
# dio CUDA OOM) ds001: probe 61261 midió 48.1 GB libres de la tarjeta el
# 06-nov (los shards NO aíslan la VRAM: el primer 59261 COMPLETED con 18
# FALLÓ de OOM por otros procesos en la tarjeta). Reanudable: salta la
# variante cuyo
# run_manifest.json ya existe. Un comando por video: si uno falla, siguen los
# demás. stdin a /dev/null: ffmpeg consumía el resto del manifiesto (job 58337).
set -uo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PATH="$HOME/.conda/envs/segloop/bin:$PATH"
cd /home/edgar.chambilla/Tesis/CAVA
tail -n +2 data/abset/manifest.csv | while IFS=, read -r id url tipo perfil idioma notas; do
  [ -f "data/cava_runs_e040/${id}_u/run_manifest.json" ] && [ -f "data/cava_runs_e040/${id}_s/run_manifest.json" ] && { echo "YA HECHO: $id"; continue; }
  python scripts/exp040_baselines.py --only "$id" < /dev/null || echo "FALLÓ: $id"
done
# segunda pasada: rehace solo las variantes cuyo run_manifest.json no exista
python scripts/exp040_baselines.py < /dev/null || echo "FALLÓ: pasada 2"
echo E040_DONE
