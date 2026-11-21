#!/bin/bash
# uso: chain.sh VARIANT NAME[,NAME...]   (ejecuta Pipeline por video con la variante dada)
V=$1; shift
cd /data/tesis-cava/CAVA
source infra/env_cuda.sh /data/tesis-cava/CAVA_minimo/.venv
export HF_HOME=/data/tesis-cava/CAVA_minimo/models HF_HUB_CACHE=/data/tesis-cava/CAVA_minimo/models/hub HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export PATH=/data/tesis-cava/exp045/ffbin:$PATH
export LD_LIBRARY_PATH=/data/tesis-cava/exp045/ffbin/lib:$LD_LIBRARY_PATH
for n in "$@"; do
  /data/tesis-cava/CAVA_minimo/.venv/bin/python -I - "$V" "$n" <<'PY'
import sys, json
sys.path.insert(0, "/data/tesis-cava/CAVA"); sys.path.insert(0, "/data/tesis-cava/CAVA/scripts")
from exp045_common import VIDEOS, STACK, EXP
from topicagg.pipeline import Pipeline
import os, topicagg.diarization as D
_orig = D.run_diarization
def _dia(*a, **k):
    # el LD_LIBRARY_PATH de env_cuda.sh (cuDNN del venv de producto) rompe el cuDNN de dia-venv: se quita para pyannote
    old = os.environ.pop("LD_LIBRARY_PATH", None)
    try:
        return _orig(*a, **k)
    finally:
        if old is not None:
            os.environ["LD_LIBRARY_PATH"] = old
D.run_diarization = _dia
v, n = sys.argv[1], sys.argv[2]
cfg = VIDEOS[n]
p = Pipeline(cfg["path"], EXP / "runs" / v / n, profile=cfg["profile"], stack=STACK, audio=cfg["audio"], variant=v)
print(json.dumps({"video": n, "variant": v, "G": p.run(cut=True)["G_version"]}), flush=True)
PY
done
echo CHAIN_DONE $V "$@"
