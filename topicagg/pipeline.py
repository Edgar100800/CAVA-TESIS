"""Pipeline CAVA de punta a punta: video largo (con audio) -> tópicos -> clips.

Etapas (cada una cacheada en <out>/work, resumible):
  1 probe     duración, pistas
  2 audio     wav mono 16 kHz (ffmpeg)
  3 units     unidades fijas (perfil film 5 s, meeting 10 s)
  4 asr       faster-whisper large-v3 -> texto por unidad
  5 voice     espectrograma log-mel + tono por unidad (topicagg.voice)
  6 visual    SigLIP del fotograma central de cada unidad
  7 vjudge    Qwen2.5-VL-7B frozen: un resumen por bloque de ~--summary-s segundos
              (3 fotogramas + ASR), asignado a sus unidades
  8 embed     bge del ASR y de los resúmenes
  9 map       manage(): retornos + enlace promedio + abstención, perfil
              (film p80/r90, meeting p95/r90), sin fusión -> topic_map.json
 10 labels    etiqueta de nivel tópico, Qwen2.5-14B frozen (EXP-019b)
 11 speakers  identidades de voz, ward + K por BIC (EXP-022d) por tópico y clip
 12 versions  perfiles de consumo (versions.py) + G-versión
 13 clips     mp4 por clip (ffmpeg) + un mp4 por playlist + index.json/index.md
Ningún GT entra en el pipeline. Configuración validada en EXPERIMENT_LOG.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import numpy as np

PROFILES = {"film": {"unit_s": 5.0, "percentile": 80, "return_percentile": 90, "snap_visual_s": 30.0,  # EXP-027
                     "speaker_embed": True},  # EXP-028
            "documentary": {"unit_s": 5.0, "percentile": 90, "return_percentile": 90,  # EXP-025
                            "snap_visual_s": 30.0, "speaker_embed": True,
                            # narrador único: K por BIC nunca da 1 y sobre-divide (EXP-028, BBC 4.1 grupos)
                            "speaker_kind": "acoustic_group"},
            "meeting": {"unit_s": 10.0, "speaker_embed": True,  # EXP-028 (AMI ARI 0.29 → 0.73)
                        "percentile": 95, "return_percentile": 90,
                        "speaker_turns_w": 6}}  # EXP-023
HF = "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache"
VL = ("Qwen/Qwen2.5-VL-7B-Instruct", "cc594898137f460bfe9f0759e9844b3ce807cfb5")
TXT = ("Qwen/Qwen2.5-14B-Instruct", "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8")
SUMMARY_PROMPT = ("These {n} frames come from one continuous stretch of a video.\nSpeech: \"{speech}\"\n\n"
                  "In ONE sentence, say what happens here: who is involved, where, and what event or "
                  "discussion takes place. Plain text, no preamble.")


def _run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True)


def _frame(video, t, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=448:-2", str(out)], capture_output=True)
    return out if Path(out).exists() and Path(out).stat().st_size > 0 else None


class Pipeline:
    def __init__(self, video, out, profile="film", summary_s=40.0, device="cuda", labels=True, audio=None):
        self.video, self.out = Path(video), Path(out)
        self.audio_src = Path(audio) if audio else None   # p. ej. AMI: video sin pista de audio
        self.cfg = PROFILES[profile] | {"profile": profile}
        self.summary_s, self.device, self.do_labels = summary_s, device, labels
        self.work = self.out / "work"
        self.work.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("HF_HOME", HF)
        self.state_f = self.work / "state.json"
        self.state = json.loads(self.state_f.read_text()) if self.state_f.exists() else {}

    def _save(self):
        self.state_f.write_text(json.dumps(self.state, ensure_ascii=False))

    def log(self, msg):
        print(f"[cava] {self.video.stem}: {msg}", flush=True)

    # 1-3
    def prepare(self):
        if "duration" not in self.state:
            d = float(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                            str(self.video)]).stdout.decode().strip())
            self.state["duration"] = d
        wav = self.work / "audio.wav"
        if not wav.exists():
            _run(["ffmpeg", "-v", "error", "-y", "-i", str(self.audio_src or self.video), "-ac", "1", "-ar", "16000",
                  str(wav)])
        if "units" not in self.state:
            u, d = self.cfg["unit_s"], self.state["duration"]
            self.state["units"] = [[float(s), float(min(s + u, d))] for s in np.arange(0, d - 1, u)]
        self._save()
        self.log(f"{self.state['duration'] / 60:.1f} min, {len(self.state['units'])} unidades "
                 f"({self.cfg['profile']})")

    # 4
    def asr(self):
        if "asr" in self.state:
            return
        from faster_whisper import WhisperModel
        wm = WhisperModel("large-v3", device=self.device,
                          compute_type="float16" if self.device == "cuda" else "int8")
        segs, _ = wm.transcribe(str(self.work / "audio.wav"), vad_filter=True)
        segs = [(s.start, s.end, s.text.strip()) for s in segs]
        self.state["asr_segments"] = segs
        self.state["asr"] = [" ".join(t for a, b, t in segs if a < u1 and b > u0) for u0, u1 in self.state["units"]]
        self._save()
        self.log(f"ASR {len(segs)} segmentos")

    # 5-6
    def signals(self):
        f = self.work / "signals.npz"
        arr = dict(np.load(f)) if f.exists() else {}
        if "voice" not in arr:
            from .voice import load_audio, voice_features
            arr["voice"] = voice_features(load_audio(str(self.work / "audio.wav")), self.state["units"])
        if "visual" not in arr:
            import torch
            from PIL import Image
            from transformers import AutoModel, AutoProcessor
            proc = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
            sm = AutoModel.from_pretrained("google/siglip-base-patch16-224").to(self.device).eval()
            fr = self.work / "frames"
            fr.mkdir(exist_ok=True)
            vecs = []
            for k, (u0, u1) in enumerate(self.state["units"]):
                p = _frame(self.video, (u0 + u1) / 2, fr / f"u{k:05d}.jpg")
                if p is None:
                    vecs.append(np.zeros(768, np.float32))
                    continue
                with torch.inference_mode():
                    o = sm.get_image_features(**proc(images=[Image.open(p).convert("RGB")],
                                                     return_tensors="pt").to(self.device))
                    o = (o.pooler_output if hasattr(o, "pooler_output") else o[0]).float().cpu().numpy()[0]
                vecs.append(o)
            arr["visual"] = np.stack(vecs).astype(np.float32)
        np.savez_compressed(f, **arr)
        self.arrays = arr

    # 7
    def vjudge(self):
        f = self.work / "summaries.json"
        units = self.state["units"]
        per = max(1, int(round(self.summary_s / self.cfg["unit_s"])))
        blocks = [(lo, min(lo + per, len(units))) for lo in range(0, len(units), per)]
        sums = json.loads(f.read_text()) if f.exists() else []
        if len(sums) >= len(blocks):
            self.summaries = sums
            return
        import torch
        from PIL import Image
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration
        vp = AutoProcessor.from_pretrained(VL[0], revision=VL[1])
        vm = Qwen2_5_VLForConditionalGeneration.from_pretrained(VL[0], revision=VL[1], torch_dtype=torch.bfloat16,
                                                                device_map=self.device).eval()
        fr = self.work / "frames"
        fr.mkdir(exist_ok=True)
        for b, (lo, hi) in enumerate(blocks[len(sums):], start=len(sums)):
            t0, t1 = units[lo][0], units[hi - 1][1]
            ps = [_frame(self.video, t0 + (t1 - t0) * q, fr / f"b{b:05d}_{int(q * 100)}.jpg") for q in (0.15, 0.5, 0.85)]
            imgs = [Image.open(p).convert("RGB").resize((448, 252)) for p in ps if p]
            speech = " ".join(self.state["asr"][lo:hi])[:500] or "(no speech)"
            content = [{"type": "image", "image": im} for im in imgs]
            content.append({"type": "text", "text": SUMMARY_PROMPT.format(n=len(imgs), speech=speech)})
            chat = vp.apply_chat_template([{"role": "user", "content": content}], tokenize=False,
                                          add_generation_prompt=True)
            inp = vp(text=[chat], images=imgs or None, padding=True, return_tensors="pt").to(vm.device)
            with torch.inference_mode():
                g = vm.generate(**inp, max_new_tokens=60, do_sample=False)
            sums.append({"unit": b, "lo": lo, "hi": hi,
                         "summary": vp.batch_decode(g[:, inp.input_ids.shape[1]:], skip_special_tokens=True)[0].strip()})
            if len(sums) % 20 == 0:
                f.write_text(json.dumps(sums, ensure_ascii=False))
        f.write_text(json.dumps(sums, ensure_ascii=False))
        del vm
        self.summaries = sums
        self.log(f"VJudge {len(sums)} resúmenes")

    # 8-9
    def topic_map(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from narrative_eval import BgeEmbedder
        from .topic_map import build_topic_map
        bge = BgeEmbedder()
        n = len(self.state["units"])
        e = bge([s["summary"] for s in self.summaries])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for s, v in zip(self.summaries, e):
            vj[s["lo"]:s["hi"]] = v
        sig = {"voice": self.arrays["voice"][:n], "visual": self.arrays["visual"][:n],
               "transcript": bge(self.state["asr"]), "vjudge": vj}
        bnd = None
        if self.cfg.get("speaker_turns_w"):
            from eval_voice_identities import identities
            from speaker_turns import speaker_turn_scores
            vid = identities(np.asarray(sig["voice"], np.float32), "ward", k_rule="bic")
            bnd = {"turns": speaker_turn_scores(vid, self.cfg["speaker_turns_w"])}
        self.doc = build_topic_map(self.video.stem, sig, self.state["units"], unit_summaries=self.summaries,
                                   boundary_signals=bnd, snap_visual_s=self.cfg.get("snap_visual_s"),
                                   percentile=self.cfg["percentile"],
                                   return_percentile=self.cfg["return_percentile"], abstain=True,
                                   unit_texts=self.state["asr"])
        self.doc["params"]["profile"] = self.cfg["profile"]
        d = self.doc["levels"]["default"]
        self.log(f"mapa: {d['n_topics']} tópicos ({d['n_returning']} con retornos)")

    # 10
    def labels(self, min_dur=30.0):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from vjudge_topic_labels import PROMPT, clean_label, stretches_text
        topics = [t for t in self.doc["levels"]["default"]["topics"] if t["duration_s"] >= min_dur]
        f = self.work / "topic_labels.json"
        done = json.loads(f.read_text()) if f.exists() else {}
        # clave = id + tramos: un mapa nuevo (otro perfil u otros votantes) no hereda etiquetas de otro tópico
        key = lambda t: f'{t["topic_id"]}@' + ",".join(f"{a:.1f}-{b:.1f}" for a, b in t["spans"])  # noqa: E731
        todo = [t for t in topics if key(t) not in done]
        if todo and self.do_labels:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(TXT[0], revision=TXT[1])
            m = AutoModelForCausalLM.from_pretrained(TXT[0], revision=TXT[1], torch_dtype=torch.bfloat16,
                                                     device_map=self.device).eval()
            for t in todo:
                chat = tok.apply_chat_template([{"role": "user", "content": PROMPT.format(
                    stretches=stretches_text(t, 8))}], tokenize=False, add_generation_prompt=True)
                inp = tok([chat], return_tensors="pt").to(m.device)
                with torch.inference_mode():
                    g = m.generate(**inp, max_new_tokens=70, do_sample=False)
                done[key(t)] = tok.decode(g[0, inp.input_ids.shape[1]:], skip_special_tokens=True).strip().splitlines()[0]
                f.write_text(json.dumps(done, ensure_ascii=False))
            del m
        for t in self.doc["levels"]["default"]["topics"]:
            t["topic_label"] = clean_label(done.get(key(t), t["label"]))

    # 11
    def speakers(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from build_ami_topic_maps import speakers_of
        from eval_voice_identities import identities
        units = self.state["units"]
        x = np.asarray(self.arrays["voice"][:len(units)], np.float32)
        # EXP-026: solo unidades con habla ASR (≥ 50 % cubierta); no inferior en AMI, menos grupos espurios en BBC
        speech = np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in self.state["asr_segments"])
                           >= 0.5 * (u1 - u0) for u0, u1 in units])
        if self.cfg.get("speaker_embed"):
            # EXP-028: identidad por embedding de hablante (WavLM-sv), no por rasgos de voz
            f = self.work / "speaker_xvec.npy"
            if f.exists():
                x = np.load(f)
            else:
                from .speaker import XVec
                from .voice import load_audio
                x = XVec(self.device)(load_audio(str(self.work / "audio.wav")), units, speech)
                np.save(f, x)
        vid = np.full(len(units), -1)
        if speech.sum() >= 10:
            vid[speech] = identities(x[speech], "ward", k_rule="bic")
        for level in self.doc["levels"].values():
            for t in level["topics"]:
                t["speakers"] = speakers_of(t["shots"], vid)
                for c, (a, b) in zip(t["context"], t["spans"]):
                    c["speakers"] = speakers_of([u for u in t["shots"] if units[u][0] >= a - 1e-6
                                                 and units[u][1] <= b + 1e-6], vid)
        self.doc["voice_identities"] = sorted({f"V{int(v)}" for v in vid if v >= 0})
        # EXP-020/022: con rasgos de voz, V# = hablante solo en habla conversacional (meeting); fuera de ella la
        # voz agrupa la escena acústica (EXP-026). EXP-028: el embedding de hablante sí identifica hablantes
        # en material de difusión (VoxConverse), así que con él V# vuelve a ser "hablante".
        self.doc["voice_identity_kind"] = self.cfg.get("speaker_kind") or (
            "speaker" if self.cfg["profile"] == "meeting" or self.cfg.get("speaker_embed") else "acoustic_group")
        self.doc["voice_identity_signal"] = "wavlm_sv" if self.cfg.get("speaker_embed") else "voice_features"
        (self.out / "topic_map.json").write_text(json.dumps(self.doc, ensure_ascii=False, indent=1))

    # 12-13
    def versions_and_clips(self, cut=True):
        from .versions import build_versions, check_versions
        v = build_versions(self.doc)
        gate = check_versions(v)
        (self.out / "versions.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
        clips_dir = self.out / "clips"
        clips_dir.mkdir(exist_ok=True)
        made = 0
        for prof, spec in v.items():
            for k, pl in enumerate(spec.get("playlists", [])):
                if not pl:
                    continue
                parts = []
                for j, c in enumerate(pl):
                    name = re.sub(r"[^\w]+", "_", f"{prof}_{k}_{j:03d}_{int(c['t0'])}s")[:80]
                    dst = clips_dir / f"{name}.mp4"
                    if cut and not dst.exists():
                        span = ["-ss", f"{c['t0']:.2f}", "-to", f"{c['t1']:.2f}"]
                        inputs = span + ["-i", str(self.video)]
                        maps = []
                        if self.audio_src:            # video sin audio: se muxea la pista externa
                            inputs += span + ["-i", str(self.audio_src)]
                            maps = ["-map", "0:v:0", "-map", "1:a:0"]
                        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, *maps, "-c:v", "libx264",
                                        "-preset", "veryfast", "-crf", "23", "-c:a", "aac", str(dst)],
                                       capture_output=True)
                    c["file"] = str(dst.relative_to(self.out))
                    if dst.exists():
                        parts.append(dst)
                        made += 1
                if cut and parts:
                    lst = clips_dir / f"{prof}_{k}.txt"
                    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                                    "-c", "copy", str(self.out / f"version_{prof}_{k}.mp4")], capture_output=True)
        (self.out / "versions.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
        self._index(v, gate)
        self.log(f"versiones: G-versión {gate['G_version']}, {made} clips")
        return gate

    def _index(self, v, gate):
        topics = sorted(self.doc["levels"]["default"]["topics"], key=lambda t: t["shots"][0])
        vk = "hablantes" if self.doc.get("voice_identity_kind", "speaker") == "speaker" else "grupos acústicos"
        lines = [f"# {self.video.stem} — mapa de tópicos CAVA ({self.cfg['profile']})", "",
                 f"Duración {self.state['duration'] / 60:.1f} min · {len(topics)} tópicos · "
                 f"{vk} {', '.join(self.doc.get('voice_identities', []))} · G-versión {gate['G_version']}", "",
                 f"| tópico | rangos (min) | duración | retornos | {vk} | etiqueta |", "|---|---|---|---|---|---|"]
        for t in topics:
            if t["duration_s"] < 20:
                continue
            rng = ", ".join(f"{a / 60:.1f}–{b / 60:.1f}" for a, b in t["spans"][:4]) + (" …" if len(t["spans"]) > 4 else "")
            spk = ", ".join(f"{s['id']} {s['share']:.0%}" for s in t.get("speakers", [])[:2])
            lab = (t.get("topic_label") or t.get("label") or "").replace("|", "/")
            lines.append(f"| {t['topic_id']} | {rng} | {t['duration_s'] / 60:.1f} min | {t['returns']} | {spk} | {lab[:110]} |")
        lines += ["", "## Versiones", ""] + [f"- **{k}**: {len([p for p in s.get('playlists', []) if p])} playlist(s)"
                                            + ("" if s.get("applicable", True) else " (no aplica)") for k, s in v.items()]
        (self.out / "index.md").write_text("\n".join(lines) + "\n")
        (self.out / "index.json").write_text(json.dumps(
            [{"topic_id": t["topic_id"], "spans": t["spans"], "label": t.get("topic_label") or t.get("label"),
              "speakers": t.get("speakers", []), "returns": t["returns"]} for t in topics], ensure_ascii=False, indent=1))

    def run(self, cut=True):
        self.prepare()
        self.asr()
        self.signals()
        self.vjudge()
        self.topic_map()
        self.labels()
        self.speakers()
        return self.versions_and_clips(cut=cut)
