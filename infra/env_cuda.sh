#!/usr/bin/env bash
# Cárguese con: source infra/env_cuda.sh [ruta-al-venv]
# ORT GPU 1.22.0 está enlazado a CUDA 12/cuDNN 9. El venv de CAVA incluye
# esas bibliotecas como paquetes NVIDIA, pero el cargador dinámico no las busca
# automáticamente en site-packages.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf 'Uso: source %s [ruta-al-venv]\n' "$0" >&2
    exit 2
fi

_infra_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
_default_venv="$(cd -- "${_infra_dir}/../../CAVA_minimo" && pwd)/.venv"
_venv="${1:-${_default_venv}}"
_python="${_venv}/bin/python"

if [[ ! -x "${_python}" ]]; then
    printf 'No existe el Python del venv: %s\n' "${_python}" >&2
    return 1
fi

_site="$(${_python} -c 'import site; print(site.getsitepackages()[0])')"
_cuda_dirs=(
    cublas/lib
    cuda_runtime/lib
    cuda_nvrtc/lib
    cudnn/lib
    cufft/lib
    curand/lib
    nvjitlink/lib
)
_paths=()
for _dir in "${_cuda_dirs[@]}"; do
    [[ -d "${_site}/nvidia/${_dir}" ]] && _paths+=("${_site}/nvidia/${_dir}")
done

if (( ${#_paths[@]} == 0 )); then
    printf 'No hay bibliotecas NVIDIA en %s\n' "${_site}" >&2
    return 1
fi

_joined="$(IFS=:; printf '%s' "${_paths[*]}")"
export LD_LIBRARY_PATH="${_joined}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
unset _infra_dir _default_venv _venv _python _site _cuda_dirs _paths _dir _joined
