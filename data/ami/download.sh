#!/bin/bash
# AMI (CC BY 4.0): audio Mix-Headset + cámara de sala de cada sitio (ES=Corner, IS=C, TS=Overview1).
# Resumible; reintenta errores transitorios; verifica tamaño mínimo.
cd "$(dirname "$0")"
B=https://groups.inf.ed.ac.uk/ami/AMICorpusMirror/amicorpus
for m in $(cat meetings_40.txt); do
  case $m in ES*) cam=Corner;; IS*) cam=C;; TS300[89]*|TS301*) cam=Overview2;; TS*) cam=Overview1;; esac
  mkdir -p media/$m
  for f in "audio/$m.Mix-Headset.wav:$m.Mix-Headset.wav" "video/$m.$cam.avi:$m.Room.avi"; do
    src=${f%%:*}; dst=media/$m/${f##*:}
    want=$(curl -sIL $B/$m/$src | grep -i content-length | tail -1 | tr -dc 0-9)
    if [ "$(stat -c %s $dst 2>/dev/null || echo 0)" != "$want" ]; then   # tamaño exacto del espejo
      curl -sSfL --retry 5 --retry-delay 10 -o $dst $B/$m/$src || echo "FAIL $m $src"
    fi
  done
  echo "ok $m"
done
echo DOWNLOAD_DONE
