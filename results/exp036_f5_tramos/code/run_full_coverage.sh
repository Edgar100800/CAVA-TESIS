#!/bin/bash
# EXP-036 F5: ejecución distribuida de la cobertura completa de tramos (F5_METHOD_AMENDMENT_v1.md).
# Lanzar desacoplado (sobrevive al cierre de la sesión):
#   setsid nohup bash exp036/f5/tramos/run_full_coverage.sh > exp036/f5/tramos/logs/full_orchestrator.out 2>&1 < /dev/null &
# Termina escribiendo exp036/f5/tramos/full_coverage.done (JSON) y exp036/f5/TRAMO_FULL.md.
# Log: exp036/f5/tramos/logs/full_orchestrator.log
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$HERE/logs" "$HERE/full"
echo $$ > "$HERE/full/orchestrator.pid"
exec /usr/bin/python3 "$HERE/full_orchestrator.py" "$@"
