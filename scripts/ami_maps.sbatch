#!/bin/bash
#SBATCH --job-name=ami_maps
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:tesla:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
# Regenera los mapas AMI de producto (120 reuniones) con identidades xvec (EXP-028) y detector de un hablante (EXP-029).
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/build_ami_topic_maps.py --meetings data/ami/meetings_all120.txt
echo AMI_MAPS_DONE
