"""Conjunto de videos propio para la evaluación A/B: descarga con yt-dlp y verificación.

Entrada: data/abset/manifest.csv con columnas  id_propio,url,tipo,perfil,idioma,notas
  (tipo = película, documental, reunión, podcast, charla, tutorial, vlog, deporte, ...;
   perfil = film | documentary | meeting, el perfil de CAVA con que se corre)
Salida, por video:
  data/abset/videos/<id_propio>.mp4        (≤ 480p, H.264 + AAC, con pista de audio)
  data/abset/videos/<id_propio>.info.json  (metadatos de yt-dlp: título, canal, duración, licencia)
  data/abset/download.jsonl                (estado, sha256, duración, streams; una fila por intento)
Reanudable: un video ya verificado no se vuelve a descargar. Solo en el nodo de login (los nodos de cómputo no tienen
internet). No se evaden bloqueos de contenido: si YouTube rechaza un video, queda registrado como fallido.
"""
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ENV = Path.home() / ".conda/envs/segloop/bin"
YTDLP, FFPROBE = str(ENV / "yt-dlp"), str(ENV / "ffprobe")
D = Path("data/abset")
FORMATS = "135+140/134+140/bv*[height<=480][vcodec^=avc1]+ba[ext=m4a]/b[height<=480]"


def probe(f: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type,codec_name,height",
                          "-of", "json", str(f)], capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    st = j.get("streams", [])
    return {"duration_s": round(float(j["format"]["duration"]), 2),
            "video": next((s["codec_name"] for s in st if s["codec_type"] == "video"), None),
            "height": next((s.get("height") for s in st if s["codec_type"] == "video"), None),
            "audio": next((s["codec_name"] for s in st if s["codec_type"] == "audio"), None)}


def sha256(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def download(row: dict) -> dict:
    vid = row["id_propio"]
    mp4 = D / "videos" / f"{vid}.mp4"
    rec = {"id_propio": vid, "url": row["url"], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if not mp4.exists():
        cmd = [YTDLP, "--no-playlist", "--ffmpeg-location", str(ENV), "-f", FORMATS, "--merge-output-format", "mp4",
               "--write-info-json", "--no-write-comments", "-o", str(D / "videos" / f"{vid}.%(ext)s"), row["url"]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not mp4.exists():
            return rec | {"status": "failed", "error": (r.stderr or r.stdout).strip().splitlines()[-1:]}
    p = probe(mp4)
    ok = p["video"] is not None and p["audio"] is not None
    info = D / "videos" / f"{vid}.info.json"
    meta = json.loads(info.read_text()) if info.exists() else {}
    return rec | p | {"status": "ok" if ok else "no_audio" if p["audio"] is None else "no_video", "sha256": sha256(mp4),
                      "youtube_id": meta.get("id"), "title": meta.get("title"), "channel": meta.get("channel"),
                      "license": meta.get("license"), "tipo": row["tipo"], "perfil": row["perfil"], "idioma": row["idioma"]}


def main():
    (D / "videos").mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(D / "manifest.csv", encoding="utf-8")))
    done = set()
    log = D / "download.jsonl"
    if log.exists():
        done = {json.loads(l)["id_propio"] for l in log.read_text().splitlines() if json.loads(l).get("status") == "ok"}
    for row in rows:
        if row["id_propio"] in done:
            continue
        rec = download(row)
        with open(log, "a") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[abset] {rec['id_propio']}: {rec['status']} {rec.get('duration_s', '')} {rec.get('title') or rec.get('error', '')}",
              flush=True)


if __name__ == "__main__":
    sys.exit(main())
