#!/bin/bash
# EXP-044-TURN: descarga AMI (CC BY 4.0) de las 15 reuniones de confirmación (meetings_exp044.txt).
# Igual que download_fresh3.sh; uso: download_exp044.sh <dir_ami_con_meetings_exp044.txt>
cd "${1:-$(dirname "$0")}"
B=https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus
for m in $(cat meetings_exp044.txt); do
  case $m in ES*) cam=Corner;; IS*) cam=C;; *) cam=$(curl -sL $B/$m/video/ | grep -oE "$m\.Overview[0-9]\.avi" | grep -v _orig | sort -u | head -1 | sed -E "s/$m\.(Overview[0-9])\.avi/\1/");; esac
  mkdir -p media/$m
  for f in "audio/$m.Mix-Headset.wav:$m.Mix-Headset.wav" "video/$m.$cam.avi:$m.Room.avi"; do
    src=${f%%:*}; dst=media/$m/${f##*:}
    want=$(curl -sIL $B/$m/$src | grep -i content-length | tail -1 | tr -dc 0-9)
    if [ -z "$want" ]; then echo "NOFILE $m $src"; continue; fi
    if [ "$(stat -c %s $dst 2>/dev/null || echo 0)" != "$want" ]; then
      curl -sSfL --retry 5 --retry-delay 10 -o $dst $B/$m/$src || echo "FAIL $m $src"
    fi
  done
  echo "ok $m"
done
echo DOWNLOAD_DONE
