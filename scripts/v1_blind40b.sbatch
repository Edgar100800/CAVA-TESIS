#!/bin/bash
#SBATCH --job-name=v1_blind40b
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --exclude=g001
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=23:00:00
#SBATCH --output=logs/%x_%j.out
# Corrida limpia v1 (contrato cava-run-v1) con el stack final, en directorio nuevo: blind40b
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/cava_run.py /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/hRhmJwjAzdw.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/IqyJt5uEVIw.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/-mpWsmmp8Jw.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/mWNF_-L_Gz4.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/nj6ItJb1AbM.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/NwK8RYHN1EU.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/o8cZHbSjFuI.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/OZPJDwGkg68.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/pCAiLee4x9A.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/PRsRMx374Gk.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/sMfPCYyDnfA.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/t7eKAuJ8zg0.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/tpVZ15lsWvw.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/Tz1BI_eEVJ4.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/u5jv-nkV5OI.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/vHzX5ZUZNPs.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/vLFBnfo89NA.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/vobtL3s_iVk.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/XxTQZRYdjHw.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/zpWISMTZ_PM.mp4:documentary --out data/cava_runs_v1
echo V1_DONE
