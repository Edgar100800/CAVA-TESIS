#!/bin/bash
#SBATCH --job-name=v1_blind40a
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --exclude=g001
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=23:00:00
#SBATCH --output=logs/%x_%j.out
# Corrida limpia v1 (contrato cava-run-v1) con el stack final, en directorio nuevo: blind40a
set -euo pipefail
source /etc/profile.d/lmod.sh
module load miniconda/3.0 cuda/12.8
conda activate segloop
export PYTHONNOUSERSITE=1 HF_HOME=/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd /home/edgar.chambilla/Tesis/CAVA
python scripts/cava_run.py /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/2-NfbOCPd2Q.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/3BjmbSTedbM.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/6u6fG7DlAiU.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/adBuxEjVwYk.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/ajDInoZtYPM.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/ALJ8ZNS87uE.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/awZ741NmdWE.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/cHkIeur6WO4.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/dBocyTZH5CI.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/dh78fWEFhf0.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/dIUCRn01ecE.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/e7mehz2W85g.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/F6ZItLvQahk.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/FbBpusmV870.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/FkbJe8DjRu4.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/fUcDLGdB7VU.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/GPHr7RNKQyM.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/H-FtVFr1gng.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/hjUxTKMUxqg.mp4:documentary /home/edgar.chambilla/Tesis/SegLoop/data/vidchapters/blind40/videos/HmjKHAxRPqk.mp4:documentary --out data/cava_runs_v1
echo V1_DONE
