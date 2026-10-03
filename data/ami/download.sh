#!/bin/bash
# AMI (CC BY 4.0): audio Mix-Headset + cámara de sala de cada sitio (ES=Corner, IS=C, TS=Overview1).
# Resumible; reintenta errores transitorios; verifica tamaño mínimo.
cd "$(dirname "$0")"
B=https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus
for m in $(cat meetings_40.txt); do
  case $m in ES*) cam=Corner;; IS*) cam=C;; TS*) cam=Overview1;; esac
  mkdir -p media/$m
  for f in "audio/$m.Mix-Headset.wav:$m.Mix-Headset.wav" "video/$m.$cam.avi:$m.Room.avi"; do
    src=${f%%:*}; dst=media/$m/${f##*:}
    if [ "$(stat -c %s $dst 2>/dev/null || echo 0)" -lt 1000000 ]; then
      curl -sSfL --retry 5 --retry-delay 10 -o $dst $B/$m/$src || echo "FAIL $m $src"
    fi
  done
  echo "ok $m"
done
echo DOWNLOAD_DONE
