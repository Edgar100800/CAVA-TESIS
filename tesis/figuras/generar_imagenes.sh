#!/usr/bin/env bash
# Genera íconos e ilustraciones con la herramienta de imágenes de Codex a partir de
# los prompts en figuras/prompts/. Uso: ./generar_imagenes.sh [nombre ...]
# Salida: images/iconos/<n>.png (fondo transparente, 256 px) e images/ilustraciones/<n>.jpg
set -euo pipefail
cd "$(dirname "$0")/.."
gen() {
  local kind=$1 name=$2 ext=png; [[ $1 == ilustraciones ]] && ext=jpg
  local out="images/$1/$2.$ext"
  [[ -s $out ]] && { echo "ya existe $out"; return; }
  local tmp; tmp=$(mktemp -d)
  codex exec --skip-git-repo-check -s workspace-write -C "$tmp" \
    "Generate exactly one image with your image generation tool using this prompt, without changing it: $(cat figuras/prompts/$kind/$name.txt) Then copy the generated PNG into the current directory as out.png." >"$tmp/log" 2>&1 || true
  if [[ ! -s $tmp/out.png ]]; then echo "FALLÓ $kind/$name (log: $tmp/log)"; return; fi
  if [[ $kind == iconos ]]; then
    magick "$tmp/out.png" -fuzz 12% -transparent white -trim +repage -resize 256x256 "$out"
  else
    magick "$tmp/out.png" -resize 960x -quality 88 "$out"
  fi
  echo "ok $out"
}
export -f gen
if (($#)); then for n in "$@"; do k=iconos; [[ -f figuras/prompts/ilustraciones/$n.txt ]] && k=ilustraciones; gen $k "$n"; done; exit; fi
{ for f in figuras/prompts/iconos/*.txt; do echo "iconos $(basename "$f" .txt)"; done
  for f in figuras/prompts/ilustraciones/*.txt; do echo "ilustraciones $(basename "$f" .txt)"; done; } \
  | xargs -P 4 -L 1 bash -c 'gen "$0" "$1"'
