#!/bin/bash
# EXP-034: audio de AVASpeech-SMAD (minutos 15–30 de cada video AVA, desde el S3 oficial de AVA) y MUSAN (OpenSLR 17).
set -u
cd /home/edgar.chambilla/Tesis/CAVA/data/gatebench
FF=~/.conda/envs/segloop/bin/ffmpeg
[ -f ava_files.txt ] || curl -s https://s3.amazonaws.com/ava-dataset/annotations/ava_file_names_trainval_v2.1.txt -o ava_files.txt
[ -f ava_files_test.txt ] || curl -s https://s3.amazonaws.com/ava-dataset/annotations/ava_file_names_test_v2.1.txt -o ava_files_test.txt
mkdir -p ava_audio
for f in "AVASpeech_Music_Labels/labels/speech labels"/*; do
  id=$(basename "$f"); id=${id%.*}
  [ -s ava_audio/$id.wav ] && continue
  F=$(grep -m1 -F -e "$id." ava_files.txt) && P=trainval || { F=$(grep -m1 -F -e "$id." ava_files_test.txt) && P=test; } || { echo "MISSING $id"; continue; }
  $FF -v error -y -ss 900 -i "https://s3.amazonaws.com/ava-dataset/$P/$F" -t 900 -vn -ac 1 -ar 16000 ava_audio/$id.wav || { echo "FAIL $id"; rm -f ava_audio/$id.wav; }
done
echo "AVA_DONE $(ls ava_audio | wc -l)"
[ -d musan ] || { curl -s -L -o musan.tar.gz https://www.openslr.org/resources/17/musan.tar.gz && tar xzf musan.tar.gz && rm musan.tar.gz; }
echo "MUSAN_DONE $(ls musan 2>/dev/null)"
