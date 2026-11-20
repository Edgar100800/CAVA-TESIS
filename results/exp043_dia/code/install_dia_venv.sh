#!/bin/bash
# Usage: install_dia_venv.sh <venv_dir> <python_with_pip>
# Separate venv for pyannote (does not touch thesis-venv / CAVA_minimo).
D=$1; PY=$2
rm -rf "$D"
python3 -m venv --without-pip "$D"
PIP_NO_CACHE_DIR=1 "$PY" -m pip --python "$D/bin/python" install -q "pyannote.audio>=4.0" pyannote.metrics 2>&1 | grep -v -i warn | tail -2
"$D/bin/python" -c "import torch,pyannote.audio as p;print(p.__version__,torch.__version__,torch.cuda.is_available(),torch.cuda.get_device_name(0))"
