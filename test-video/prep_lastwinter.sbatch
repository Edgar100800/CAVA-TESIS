#!/bin/bash
#SBATCH --job-name=prep_lastwinter
#SBATCH --account=tesis
#SBATCH --qos=a-tesis
#SBATCH --partition=standard
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x_%j.out
# Caso manual test-video: TheLastWinter (pelicula, MKV HEVC 1080p + EAC3 5.1).
# Normaliza a MP4 480p H.264/AAC estereo con solo video+audio principal (sin portada
# MJPEG ni subtitulos, que el corte de clips sin -map podria elegir) y extrae los SRT eng.
set -euo pipefail
FF=/home/edgar.chambilla/.conda/envs/segloop/bin
cd /home/edgar.chambilla/Tesis/CAVA/test-video/videos
$FF/ffmpeg -v error -y -i TheLastWinter.mkv -map 0:s:0 TheLastWinter.eng.srt -map 0:s:1 TheLastWinter.eng.sdh.srt
$FF/ffmpeg -v error -y -i TheLastWinter.mkv -map 0:v:0 -map 0:a:0 -vf scale=-2:480 \
  -c:v libx264 -preset veryfast -crf 23 -threads 16 -c:a aac -ac 2 -b:a 128k \
  -movflags +faststart TheLastWinter.part.mp4
mv TheLastWinter.part.mp4 TheLastWinter.mp4
$FF/ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,channels -of compact TheLastWinter.mp4
sha256sum TheLastWinter.mkv TheLastWinter.mp4
echo PREP_LASTWINTER_DONE
