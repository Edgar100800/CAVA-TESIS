#!/bin/bash
#SBATCH --job-name=v1_summe
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --exclude=g001
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=23:00:00
#SBATCH --output=logs/%x_%j.out
# Corrida limpia v1 (contrato cava-run-v1) con el stack final, en directorio nuevo: summe (EXP-037/038 confirmación)
# Cooking (de videos_corrupt) va al final: si falla, los otros 24 ya están hechos.
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/cava_run.py "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Air_Force_One.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Base jumping.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Bearpark_climbing.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Bike Polo.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Bus_in_Rock_Tunnel.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/car_over_camera.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Car_railcrossing.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Cockpit_Landing.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Eiffel Tower.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Excavators river crossing.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Fire Domino.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Jumps.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Kids_playing_in_leaves.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Notre_Dame.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Paintball.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/paluma_jump.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/playing_ball.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Playing_on_water_slide.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Saving dolphines.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Scuba.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Statue of Liberty.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/St Maarten Landing.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Uncut_Evening_Flight.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos/Valparaiso_Downhill.mp4:film" "/home/edgar.chambilla/Tesis/SegLoop/data/summe/videos_corrupt/Cooking.mp4:film" --out data/cava_runs_v1_summe
echo V1_DONE
