#!/bin/bash
# Envoltorio para run_diarization en máquinas sin cava_dia instalado en dia-venv: recibe "-I -m cava_dia.run ARGS..."
# y ejecuta el mismo módulo del repo con el intérprete de ~/dia-venv (aislado con -I).
shift 3
exec $HOME/dia-venv/bin/python -I -c "import sys, runpy; sys.path.insert(0, '/data/tesis-cava/CAVA'); sys.argv = ['cava_dia.run'] + sys.argv[1:]; runpy.run_module('cava_dia.run', run_name='__main__')" "$@"
