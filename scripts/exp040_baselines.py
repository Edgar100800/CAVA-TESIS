"""EXP-040 (pre-registro): versiones de las bases U y S sobre el abset, para el
A/B con personas. Salida en data/cava_runs_e040/<id>_u y <id>_s (directorio
nuevo, contrato cava-run-v1, git_dirty false, gt_used false).

Misma maquinaria que CAVA (reporte 2026-10-23, "solo cambia qué se elige"):
unidades de la rejilla del perfil (5 s documentary, 10 s meeting), el mismo
corte y codificación (ffmpeg + concat), el mismo presupuesto por formato y el
mismo modelo de etiquetas (Qwen2.5-14B, mismo prompt que pipeline.labels).

Asdr, señales y resúmenes NO se recalculan: se copian de work/ del run fuente
(data/cava_runs_abset/<id>, corrido con el stack congelado).

  Base U (sin estructura):
    - full_chapters: cortes uniformes, mismo número de capítulos que el mapa
      CAVA (sin no_topic), etiquetados por el mismo modelo.
    - recap60 / highlights10pct: las mismas duraciones de los clips de CAVA en
      esas versiones, repantalladas equiespaciadas en la duración del video,
      etiqueta por clip (mismo modelo).
    - threads: no aplica (sin retornos, como declara el diseño del A/B).
    - speaker_threads: los 3 bloques contiguos más largos de unidades con
      habla (turnos de ASR, sin modelo de identidad), un clip por bloque.
  Base S (mejor señal sola, visual):
    - mapa con solo la señal visual (link_quorum 1, mismos percentiles del
      perfil, sin snap: ADR-0001, gestión con un solo votante); build_versions
      tal cual, así los hilos salen del mapa visual si hay retornos.
    - speaker_threads: identidades por rasgos de voz (log-mel + Ward + BIC,
      EXP-022d), voz dominante del tramo (misma anotación que Pipeline.speakers).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from topicagg.pipeline import PROFILES, TXT, Pipeline  # noqa: E402
from topicagg.versions import _clip, _trim, build_versions, check_versions  # noqa: E402
from topicagg.topic_map import _span_context, _spans, build_topic_map  # noqa: E402

SRC = ROOT / "data/cava_runs_abset"
VIDEOS = ROOT / "data/abset/videos"
SPEECH_COVER = 0.5  # EXP-026: unidad con habla si ASR cubre >= 50 %

def _run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True)


def _load_manifest():
    with open(ROOT / "data/abset/manifest.csv", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _source_state(src: Path):
    state = json.loads((src / "work/state.json").read_text())
    for f in ("state.json", "signals.npz", "summaries.json"):
        if not (src / "work" / f).exists():
            raise FileNotFoundError(f"{src}/work/{f} no existe (corrida fuente incompleta)")
    return state


def _copy_work(src: Path, out: Path):
    (out / "work").mkdir(parents=True, exist_ok=True)
    for f in ("state.json", "signals.npz", "summaries.json", "audio.wav"):
        if (src / "work" / f).exists():
            (out / "work" / f).write_bytes((src / "work" / f).read_bytes())


def _speech_mask(units, asr_segments):
    return np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in asr_segments)
                     >= SPEECH_COVER * (u1 - u0) for u0, u1 in units])


def _label_of(unit_i, summaries, n_units):
    """Etiqueta base: resumen VJudge con más shots en el tramo (misma regla de
    topics_from_plan); si no hay, el del centro."""
    best, best_k = None, -1
    for s in summaries:
        k = sum(1 for u in range(n_units) if s["lo"] <= u < s["hi"] and (unit_i is None or u == unit_i))
        if best_k < k:
            best, best_k = s["summary"], k
    return best or "(sin resumen)"


def _pseudo_topic(topic_id, a, b, unit_times, summaries, unit_texts, provenance, label_unit=None):
    """Tópico sintético con el contrato exacto del mapa: shots contiguos, spans,
    contexto por tramo (seen/said) y etiqueta base; la etiqueta fina la pone el
    mismo modelo de etiquetas en label_topics()."""
    shots = list(range(a, b))
    if not shots:
        return None
    t0, t1 = round(unit_times[a][0], 2), round(unit_times[b - 1][1], 2)
    return {"topic_id": topic_id, "shots": shots,
            "spans": [[t0, t1]],
            "duration_s": round(t1 - t0, 2), "returns": 0,
            "label": _label_of((a + b - 1) // 2 if summaries else None, summaries, len(unit_times)) or "(sin resumen)",
            "provenance": provenance, "flags": {"no_topic": False, "needs_review": False},
            "context": [_span_context(a, b - 1, summaries, unit_texts)]}


def label_topics(topics, cache_path: Path, device: str, summary_fallback=True):
    """Mismo modelo y mismo prompt que pipeline.labels(): Qwen2.5-14B,
    clave id@spans, salida 'CHARACTERS: ... | TOPIC: ...' limpiada, caché por
    etiqueta escrita al vuelo. sin min_dur: los clips equiespaciados pueden ser
    cortos y también reciben etiqueta del modelo."""
    from vjudge_topic_labels import PROMPT, clean_label, stretches_text
    done = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    key = lambda t: f'{t["topic_id"]}@' + ",".join(f"{a:.1f}-{b:.1f}" for a, b in t["spans"])  # noqa: E731
    todo = [t for t in topics if key(t) not in done]
    model = None
    try:
        if todo:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(TXT[0], revision=TXT[1])
            model = AutoModelForCausalLM.from_pretrained(TXT[0], revision=TXT[1], torch_dtype=torch.bfloat16,
                                                         device_map=device).eval()
            for t in todo:
                chat = tok.apply_chat_template([{"role": "user", "content": PROMPT.format(
                    stretches=stretches_text(t, 8))}], tokenize=False, add_generation_prompt=True)
                inp = tok([chat], return_tensors="pt").to(model.device)
                with torch.inference_mode():
                    g = model.generate(**inp, max_new_tokens=70, do_sample=False)
                txt = tok.decode(g[0, inp.input_ids.shape[1]:], skip_special_tokens=True)
                done[key(t)] = txt.strip().splitlines()[0]
                cache_path.write_text(json.dumps(done, ensure_ascii=False))
    finally:
        del model
    for t in topics:
        if summary_fallback or key(t) in done:
            t["topic_label"] = clean_label(done.get(key(t), t["label"]))


def render(video: Path, out: Path, v: dict, audio_src=None, cut=True):
    """Mismo corte y concat que pipeline.versions_and_clips: ffmpeg libx264/aac
    por clip y concat -c copy por playlist; nunca reutiliza y reescribe
    versions.json con las rutas de los mp4."""
    clips_dir = out / "clips"
    clips_dir.mkdir(exist_ok=True)
    made = 0
    for prof, spec in v.items():
        for k, pl in enumerate(spec.get("playlists", [])):
            if not pl:
                continue
            parts = []
            for j, c in enumerate(pl):
                name = re.sub(r"[^\w.-]+", "_", f"{prof}_{k}_{j:03d}_{c['t0']:.2f}-{c['t1']:.2f}")[:90]
                dst = clips_dir / f"{name}.mp4"
                if cut and not dst.exists():
                    span = ["-ss", f"{c['t0']:.2f}", "-to", f"{c['t1']:.2f}"]
                    inputs = span + ["-i", str(video)]
                    maps = []
                    if audio_src:
                        inputs += span + ["-i", str(audio_src)]
                        maps = ["-map", "0:v:0", "-map", "1:a:0"]
                    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, *maps, "-c:v", "libx264",
                                    "-preset", "veryfast", "-crf", "23", "-c:a", "aac", str(dst)],
                                   capture_output=True)
                c["file"] = str(dst.relative_to(out))
                if dst.exists():
                    parts.append(dst)
                    made += 1
            if cut and parts:
                lst = clips_dir / f"{prof}_{k}.txt"
                lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                                "-c", "copy", str(out / f"version_{prof}_{k}.mp4")], capture_output=True)
    (out / "versions.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
    return made


def clips_jsonl(out: Path, video_id: str, profile: str, v: dict, topics_by_id: dict):
    """Una fila por clip con el mismo contrato que pipeline._clips_jsonl."""
    rows = []
    for prof, spec in v.items():
        for k, pl in enumerate(spec.get("playlists", []) or []):
            for j, c in enumerate(pl or []):
                t = topics_by_id.get(c["topic_id"], {})
                span = next((sp for sp in t.get("spans", [])
                             if sp[0] <= c["t0"] + 1e-6 and c["t1"] <= sp[1] + 1e-6), None)
                ctx = t["context"][t["spans"].index(span)] if span and "context" in t else {}
                rows.append({
                    "clip_id": f"{video_id}:{c['t0']:.2f}-{c['t1']:.2f}",
                    "video": video_id, "profile": profile, "version": prof,
                    "playlist": k, "order": j, "file": c.get("file"),
                    "t0": round(float(c["t0"]), 2), "t1": round(float(c["t1"]), 2),
                    "duration_s": round(float(c["t1"] - c["t0"]), 2),
                    "budget_s": spec.get("budget_s"), "topic_id": c["topic_id"],
                    "topic_label": c.get("label"), "topic_duration_s": t.get("duration_s"),
                    "topic_returns": t.get("returns"), "topic_span": span,
                    "trimmed": bool(span and (c["t1"] - c["t0"]) < (span[1] - span[0]) - 1e-6),
                    "provenance": t.get("provenance"), "flags": t.get("flags"),
                    "speakers": (ctx or {}).get("speakers", t.get("speakers")),
                    "seen": (ctx or {}).get("seen"), "said": (ctx or {}).get("said"),
                })
    with open(out / "clips.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _git(args):
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def write_manifest(out: Path, variant: str, src: Path, perfil_cfg, n_units, gate, timings, sig_names):
    src_man = json.loads((src / "run_manifest.json").read_text())
    man = {"schema": "cava-run-v1", "variant": variant, "source_run": str(src),
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
           "video": src_man["video"], "profile": dict(perfil_cfg),
           "code": {"git_commit": _git(["rev-parse", "HEAD"]),
                    "git_dirty": bool(_git(["status", "--porcelain", "--untracked-files=no",
                                            "--", "topicagg", "scripts"])),
                    "python": subprocess.run([sys.executable, "-V"], capture_output=True,
                                             text=True).stdout.strip().split()[1]},
           "labels": True,
           # misma maquinaria: revisiones de modelos heredadas del run fuente (shipment congelado)
           "models": src_man["models"],
           "outputs": {"n_units": n_units, "signals": sig_names,
                       "G_version": gate["G_version"],
                       "files": ["topic_map.json", "versions.json", "clips.jsonl", "index.json"]},
           "gt_used": False, "timings_s": timings}
    (out / "run_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))


def base_u(state, out: Path, perfil_cfg, src: Path, summaries, unit_texts, unit_times, n, D, cap):
    """Pseudo-mapa uniforme + recap/highlights equiespaciados + bloques de habla."""
    src_map = json.loads((src / "topic_map.json").read_text())
    src_topics = [t for t in src_map["levels"]["default"]["topics"]
                  if not t["flags"]["no_topic"] and t["duration_s"] >= 5.0]
    K = max(1, len(src_topics))
    src_versions = json.loads((src / "versions.json").read_text())
    topics, tid = [], 0
    cuts = [round(i * n / K) for i in range(K + 1)]

    # capítulos: mismo número que el mapa CAVA, cortes equiespaciados sobre la rejilla
    for i in range(K):
        t = _pseudo_topic(tid, cuts[i], cuts[i + 1], unit_times, summaries, unit_texts,
                          {"base": "U", "kind": "uniform_chapters"})
        if t:
            topics.append(t)
            tid += 1

    # recap60 / highlights10pct: mismas duraciones que CAVA, clips equiespaciados
    equip = {}
    for prof in ("recap60", "highlights10pct"):
        durs = [round(c["t1"] - c["t0"], 2)
                for pl in src_versions[prof]["playlists"] for c in pl]
        if not durs or sum(durs) >= D:
            equip[prof] = {"budget_s": src_versions[prof]["budget_s"], "playlists": []}
            continue
        gap = (D - sum(durs)) / (len(durs) + 1)  # mismo espaciado uniforme que rewards_tvsum
        t, pl = gap, []
        for j, d in enumerate(durs):
            a = np.searchsorted([u[0] for u in unit_times], t, side="right") - 1
            b = min(n, np.searchsorted([u[1] for u in unit_times], t + d, side="left") + 1)
            p = _pseudo_topic(0, max(a, 0), max(a, 0) + 1, unit_times, summaries, unit_texts,
                              {"base": "U", "kind": "equispaced"})
            if p:
                p["topic_id"] = tid
                p["spans"] = [[round(t, 2), round(t + d, 2)]]
                p["duration_s"] = round(d, 2)
                p["context"] = [_span_context(max(a, 0), max(a, 0), summaries, unit_texts)]
                topics.append(p)
                tid += 1
                pl.append(_clip(p, p["spans"][0]))
            t += d + gap
        equip[prof] = {"budget_s": src_versions[prof]["budget_s"], "playlists": [pl]}

    # speaker_threads: bloques contiguos por turnos de habla, sin modelo de identidad
    asr_seg = state.get("asr_segments") or []
    speech = _speech_mask(state["units"], asr_seg)
    blocks, start = [], None
    for i, sp in enumerate(speech):
        if sp and start is None:
            start = i
        if not sp and start is not None:
            blocks.append((start, i))
            start = None
    if start is not None:
        blocks.append((start, n))
    blocks = sorted(sorted(blocks, key=lambda x: unit_times[x[1] - 1][1] - unit_times[x[0]][0],
                           reverse=True)[:3], key=lambda x: x[0])
    sp_playlists = []
    for st, en in blocks:
        p = _pseudo_topic(0, st, en, unit_times, summaries, unit_texts,
                          {"base": "U", "kind": "speech_turns"})
        if not p:
            continue
        p["topic_id"] = tid
        topics.append(p)
        tid += 1
        s = _trim(p, p["spans"][0], cap, unit_times) or p["spans"][0]
        sp_playlists.append([_clip(p, s) | {"speaker": "TURN"}])

    doc = {"video_id": state.get("video_id", ""), "n_units": n, "duration_s": round(D, 2),
           "signals": ["uniform"], "unit_times": unit_times,
           "params": {"base": "U", "profile": perfil_cfg["profile"], "n_chapters": K},
           "levels": {"default": {"n_topics": len(topics), "n_returning": 0, "topics": topics}},
           "voice_identity_signal": None, "voice_identity_kind": None}
    chapters = [[_clip(t, t["spans"][0]) for t in sorted(
        [q for q in topics if q["provenance"]["kind"] == "uniform_chapters"], key=lambda q: q["shots"][0])]]
    v = {"full_chapters": {"budget_s": None, "playlists": chapters},
         "recap60": equip["recap60"], "highlights10pct": equip["highlights10pct"],
         "threads": {"budget_s": cap, "playlists": [], "applicable": False},  # sin retornos (diseño A/B)
         "speaker_threads": {"budget_s": cap, "playlists": sp_playlists,
                             "applicable": bool(sp_playlists)}}
    return doc, v


def base_s(state, out: Path, perfil_cfg, summaries, unit_texts, unit_times, n, D, cap, arrays):
    """Mapa con solo la señal visual (un solo votante, quorum 1: ADR-0001) +
    hablantes por rasgos de voz EXP-022d, y build_versions tal cual."""
    sig = {"visual": np.asarray(arrays["visual"], np.float32)[:n]}
    doc = build_topic_map(state.get("video_id", ""), sig, state["units"],
                          unit_summaries=summaries, percentile=perfil_cfg["percentile"],
                          return_percentile=perfil_cfg["return_percentile"], link_quorum=1,
                          abstain=True, unit_texts=unit_texts)
    doc["params"]["profile"] = perfil_cfg["profile"]
    from eval_voice_identities import identities
    from build_ami_topic_maps import speakers_of
    asr_seg = state.get("asr_segments") or []
    speech = _speech_mask(state["units"], asr_seg)
    x = np.asarray(arrays["voice"], np.float32)[:n]
    full_vid = np.full(n, -1)
    if speech.sum() >= 10:  # EXP-026: misma puerta que Pipeline.speakers
        full_vid[speech] = identities(x[speech], "ward", k_rule="bic")
    for level in doc["levels"].values():
        for t in level["topics"]:
            t["speakers"] = speakers_of(t["shots"], full_vid)
            for c, (a, b) in zip(t["context"], t["spans"]):
                c["speakers"] = speakers_of([u for u in t["shots"]
                                             if unit_times[u][0] >= a - 1e-6
                                             and unit_times[u][1] <= b + 1e-6], full_vid)
    doc["voice_identities"] = sorted({f"V{int(vv)}" for vv in full_vid if vv >= 0})
    doc["voice_identity_kind"] = "speaker" if perfil_cfg["profile"] == "meeting" else "acoustic_group"
    doc["voice_identity_signal"] = "voice_features"
    v = build_versions(doc)
    for k, dflt in (("threads", cap), ("speaker_threads", cap)):
        v.setdefault(k, {"budget_s": dflt, "playlists": [], "applicable": False})
    return doc, v


def run_video(row, args):
    vid, perfil = row["id_propio"], row["perfil"]
    src, video = SRC / vid, VIDEOS / f"{vid}.mp4"
    state = _source_state(src)
    units, asr = state["units"], state.get("asr", [])
    n, D = len(units), units[-1][1] - units[0][0]
    unit_times = [[round(a, 2), round(b, 2)] for a, b in units]
    cap = 0.10 * D
    cfg = dict(PROFILES[perfil]) | {"profile": perfil}
    summaries = [dict(s) for s in json.loads((src / "work/summaries.json").read_text())]
    for variant, fn in (("u", base_u), ("s", base_s)):
        out = Path(args.out) / f"{vid}_{variant}"
        if (out / "run_manifest.json").exists():
            print(f"[e040] {vid}_{variant}: YA HECHO", flush=True)
            continue
        timings = {}
        _copy_work(src, out)
        t0 = time.time()
        if variant == "u":
            doc, v = fn(state, out, cfg, src, summaries, asr, unit_times, n, D, cap)
        else:
            p = Pipeline(video, out, profile=perfil, device=args.device, labels=args.labels)
            p.prepare(); p.signals(); p.vjudge()
            doc, v = fn(p.state, out, cfg, summaries, asr, unit_times, n, D, cap, p.arrays)
        timings["map"] = round(time.time() - t0, 1)
        doc["video_id"] = vid
        t0 = time.time()
        topics = doc["levels"]["default"]["topics"]
        if args.labels:
            label_topics(topics, out / "work/topic_labels.json", args.device)
        timings["labels"] = round(time.time() - t0, 1)
        t0 = time.time()
        made = render(video, out, v, cut=args.cut)
        gate = check_versions(v)
        topics_by_id = {t["topic_id"]: t for t in doc["levels"]["default"]["topics"]}
        clips_jsonl(out, vid, perfil, v, topics_by_id)
        (out / "topic_map.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        (out / "index.json").write_text(json.dumps(
            {"video": vid, "variant": variant, "profile": perfil, "gate": gate,
             "versions": {k: {"n_playlists": len([p for p in s.get("playlists", []) if p]),
                              "budget_s": s.get("budget_s"),
                              "applicable": s.get("applicable", True)} for k, s in v.items()}},
            ensure_ascii=False, indent=1))
        timings["render"] = round(time.time() - t0, 1)
        write_manifest(out, {"u": "baseU", "s": "baseS"}[variant], src, cfg, n, gate, timings,
                       doc["signals"])
        d = doc["levels"]["default"]
        print(f"[e040] {vid}_{variant}: G-versión {gate['G_version']}, {made} clips, "
              f"{d['n_topics']} tópicos", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "data/cava_runs_e040"))
    ap.add_argument("--only", help="id_propio del abset; vacío = todos")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-cut", action="store_true", help="no corta mp4 (smoke test)")
    ap.add_argument("--no-labels", action="store_true")
    args = ap.parse_args()
    args.cut, args.labels = not args.no_cut, not args.no_labels
    rows = _load_manifest()
    if args.only:
        rows = [r for r in rows if r["id_propio"] == args.only]
        if not rows:
            sys.exit(f"--only {args.only}: no está en el manifiesto del abset")
    for row in rows:
        try:
            run_video(row, args)
        except Exception as e:  # un video que falla no detiene al resto
            import traceback
            print(f"[e040] FALLÓ {row['id_propio']}: {e}\n{traceback.format_exc()}", flush=True)


if __name__ == "__main__":
    main()
