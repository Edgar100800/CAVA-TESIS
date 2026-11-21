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
 11 speakers  v1.0: WavLM + ward/BIC; v1.1 film/meeting: pyannote; V# por tópico y clip
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

from . import variants as V
from .profiles import get_profile
from .profiles.v1_0 import PROFILES  # compatibilidad: siempre los perfiles congelados
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


def transcribe(wav, device, compute_type=None, deterministic=False):
    """faster-whisper large-v3 con VAD interno; ref = float16 (cuda) / int8 (cpu), fast = int8_float16.

    `deterministic` (EXP-046-STAB, modo D): mismos pesos y precisión, temperature=0 sin reintentos por temperatura,
    mismo beam_size (5, el valor por defecto de faster-whisper que usa ref) y mismo VAD. Por defecto no cambia nada.
    """
    from faster_whisper import WhisperModel
    wm = WhisperModel("large-v3", device=device,
                      compute_type=compute_type or ("float16" if device == "cuda" else "int8"))
    if deterministic:
        segs, _ = wm.transcribe(str(wav), vad_filter=True, beam_size=5, temperature=0.0)
    else:
        segs, _ = wm.transcribe(str(wav), vad_filter=True)
    return [(s.start, s.end, s.text.strip()) for s in segs]


def units_text(segs, units):
    return [" ".join(t for a, b, t in segs if a < u1 and b > u0) for u0, u1 in units]


class Pipeline:
    def __init__(self, video, out, profile="film", summary_s=40.0, device="cuda", labels=True, audio=None,
                 stack="v1.0", variant="ref", asr_mode="ref"):
        self.video, self.out = Path(video), Path(out)
        self.var = V.parse_variant(variant)  # EXP-045-Q: variante por pista; ref (por defecto) = comportamiento congelado
        if asr_mode not in ("ref", "det"):
            raise ValueError(f"asr_mode inválido {asr_mode}; ref|det")
        self.asr_mode = asr_mode  # EXP-046-STAB: det = ASR determinista (temperature=0 sin reintentos); ref por defecto
        self.sub_timings = {}
        self.audio_src = Path(audio) if audio else None   # p. ej. AMI: video sin pista de audio
        self.stack = stack
        self.cfg = get_profile(stack, profile) | {"profile": profile}
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
        if self.asr_mode == "det":
            ct = "int8_float16" if self.var["asr"] != "ref" else None
            f = self.work / f"asr.det{V.suffix(self.var['asr'])}.json"
            if f.exists():
                self.asr_segments = json.loads(f.read_text())["segments"]
            else:
                self.asr_segments = transcribe(self.work / "audio.wav", self.device, ct, deterministic=True)
                f.write_text(json.dumps({"compute_type": ct or "float16", "deterministic": True,
                                         "segments": self.asr_segments}, ensure_ascii=False))
            self.asr_text = units_text(self.asr_segments, self.state["units"])
            self.log(f"ASR[det] {len(self.asr_segments)} segmentos")
            return
        if self.var["asr"] != "ref":
            f = self.work / f"asr{V.suffix(self.var['asr'])}.json"
            if f.exists():
                self.asr_segments = json.loads(f.read_text())["segments"]
            else:
                self.asr_segments = transcribe(self.work / "audio.wav", self.device, "int8_float16")
                f.write_text(json.dumps({"compute_type": "int8_float16", "segments": self.asr_segments},
                                        ensure_ascii=False))
            self.asr_text = units_text(self.asr_segments, self.state["units"])
            self.log(f"ASR[{self.var['asr']}] {len(self.asr_segments)} segmentos")
            return
        if "asr" in self.state:
            self.asr_segments, self.asr_text = self.state["asr_segments"], self.state["asr"]
            return
        segs = transcribe(self.work / "audio.wav", self.device)
        self.state["asr_segments"] = segs
        self.state["asr"] = units_text(segs, self.state["units"])
        self.asr_segments, self.asr_text = segs, self.state["asr"]
        self._save()
        self.log(f"ASR {len(segs)} segmentos")

    # 5-6
    def signals(self):
        f = self.work / "signals.npz"
        arr = dict(np.load(f)) if f.exists() else {}
        if "voice" not in arr:
            from .voice import load_audio, voice_features
            arr["voice"] = voice_features(load_audio(str(self.work / "audio.wav")), self.state["units"])
        if self.var["visual"] != "ref":
            self.arrays = dict(arr) | {"visual": self._visual_fast()}
            if not f.exists():
                np.savez_compressed(f, **arr)
            return
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

    def _visual_fast(self):
        """SigLIP fast: decode-once 1 fps + lotes de 64 + FP16; caché propio por variante."""
        fv = self.work / f"signals.visual{V.suffix(self.var['visual'])}.npy"
        if fv.exists():
            return np.load(fv)
        import torch
        from PIL import Image
        from transformers import AutoModel, AutoProcessor
        proc = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
        sm = AutoModel.from_pretrained("google/siglip-base-patch16-224").to(self.device).eval().half()
        units = self.state["units"]
        if self.var["visual"] == "fast_exact":  # diagnóstico: FP16 + lotes sobre los fotogramas exactos de la corrida ref
            paths = [self.work / "frames" / f"u{k:05d}.jpg" for k in range(len(units))]
            paths = [p if p.exists() and p.stat().st_size > 0 else None for p in paths]
        else:
            idx = V.FrameIndex(V.decode_once(self.video, self.work / "frames1fps"))
            paths = [idx.path((u0 + u1) / 2) for u0, u1 in units]
        out = np.zeros((len(units), 768), np.float32)
        ok = [k for k, p in enumerate(paths) if p is not None]
        for i in range(0, len(ok), 64):
            ks = ok[i:i + 64]
            ims = [Image.open(paths[k]).convert("RGB") for k in ks]
            with torch.inference_mode():
                px = proc(images=ims, return_tensors="pt").to(self.device)
                px = {a: (b.half() if b.is_floating_point() else b) for a, b in px.items()}
                o = sm.get_image_features(**px)
                o = (o.pooler_output if hasattr(o, "pooler_output") else o[0]).float().cpu().numpy()
            out[ks] = o
        del sm
        np.save(fv, out)
        return out

    def _frame_for(self, kind, b, q, t):
        """Fotograma de vjudge: exacto (ref), 1 fps más cercano (fast) o exacto reutilizado (fast_exact)."""
        fr = self.work / "frames"
        if kind == "fast":
            if not hasattr(self, "_fidx"):
                self._fidx = V.FrameIndex(self.work / "frames1fps")
            return self._fidx.path(t)
        p = fr / f"b{b:05d}_{int(q * 100)}.jpg"
        if kind == "fast_exact" and p.exists() and p.stat().st_size > 0:
            return p
        fr.mkdir(exist_ok=True)
        return _frame(self.video, t, p)

    def _vjudge_fast(self, blocks, units):
        kind = self.var["vjudge"]
        f = self.work / f"summaries{V.suffix(kind)}.json"
        sums = json.loads(f.read_text()) if f.exists() else []
        if len(sums) >= len(blocks):
            return sums
        from PIL import Image
        if kind == "fast":
            V.decode_once(self.video, self.work / "frames1fps")
        convs = []
        for b, (lo, hi) in enumerate(blocks):
            t0, t1 = units[lo][0], units[hi - 1][1]
            ps = [self._frame_for(kind, b, q, t0 + (t1 - t0) * q) for q in (0.15, 0.5, 0.85)]
            imgs = [Image.open(p).convert("RGB").resize((448, 252)) for p in ps if p]
            speech = " ".join(self.asr_text[lo:hi])[:500] or "(no speech)"
            content = [{"type": "image_url", "image_url": {"url": V.png_data_url(im)}} for im in imgs]
            content.append({"type": "text", "text": SUMMARY_PROMPT.format(n=len(imgs), speech=speech)})
            convs.append([{"role": "user", "content": content}])
        texts = V.chat_many(V.VL_URL, V.VL_MODEL, convs, 60)
        sums = [{"unit": b, "lo": lo, "hi": hi, "summary": t.strip()} for b, ((lo, hi), t) in enumerate(zip(blocks, texts))]
        f.write_text(json.dumps(sums, ensure_ascii=False))
        return sums

    # 7
    def vjudge(self):
        f = self.work / "summaries.json"
        units = self.state["units"]
        per = max(1, int(round(self.summary_s / self.cfg["unit_s"])))
        blocks = [(lo, min(lo + per, len(units))) for lo in range(0, len(units), per)]
        if self.var["vjudge"] != "ref":
            self.summaries = self._vjudge_fast(blocks, units)
            self.log(f"VJudge[{self.var['vjudge']}] {len(self.summaries)} resúmenes")
            return
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
            speech = " ".join(self.asr_text[lo:hi])[:500] or "(no speech)"
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
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        self.summaries = sums
        self.log(f"VJudge {len(sums)} resúmenes")

    # 8-9
    def topic_map(self):
        from .embed import BgeEmbedder
        from .topic_map import build_topic_map
        import time
        t_e = time.time()
        bge = BgeEmbedder(self.device, half=True) if self.var["embed"] != "ref" else BgeEmbedder()
        n = len(self.state["units"])
        e = bge([s["summary"] for s in self.summaries])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for s, v in zip(self.summaries, e):
            vj[s["lo"]:s["hi"]] = v
        sig = {"voice": self.arrays["voice"][:n], "visual": self.arrays["visual"][:n],
               "transcript": bge(self.asr_text), "vjudge": vj}
        self.sig = sig
        self.sub_timings["embed_bge_s"] = round(time.time() - t_e, 1)
        bnd = None
        if self.cfg.get("speaker_turns_w"):
            from .identities import identities, speaker_turn_scores
            vid = identities(np.asarray(sig["voice"], np.float32), "ward", k_rule="bic")
            bnd = {"turns": speaker_turn_scores(vid, self.cfg["speaker_turns_w"])}
        self.doc = build_topic_map(self.video.stem, sig, self.state["units"], unit_summaries=self.summaries,
                                   boundary_signals=bnd, snap_visual_s=self.cfg.get("snap_visual_s"),
                                   percentile=self.cfg["percentile"],
                                   return_percentile=self.cfg["return_percentile"], abstain=True,
                                   unit_texts=self.asr_text)
        self.doc["params"]["profile"] = self.cfg["profile"]
        d = self.doc["levels"]["default"]
        self.log(f"mapa: {d['n_topics']} tópicos ({d['n_returning']} con retornos)")

    # 10
    def labels(self, min_dur=30.0):
        from .labels import PROMPT, clean_label, stretches_text
        topics = [t for t in self.doc["levels"]["default"]["topics"] if t["duration_s"] >= min_dur]
        f = self.work / f"topic_labels{V.suffix(self.var['labels'])}.json"
        done = json.loads(f.read_text()) if f.exists() else {}
        # clave = id + tramos: un mapa nuevo (otro perfil u otros votantes) no hereda etiquetas de otro tópico
        key = lambda t: f'{t["topic_id"]}@' + ",".join(f"{a:.1f}-{b:.1f}" for a, b in t["spans"])  # noqa: E731
        todo = [t for t in topics if key(t) not in done]
        if todo and self.do_labels and self.var["labels"] != "ref":
            convs = [[{"role": "user", "content": PROMPT.format(stretches=stretches_text(t, 8))}] for t in todo]
            for t, text in zip(todo, V.chat_many(V.TXT_URL, V.TXT_MODEL, convs, 70)):
                done[key(t)] = text.strip().splitlines()[0]
            f.write_text(json.dumps(done, ensure_ascii=False))
        elif todo and self.do_labels:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            tok = AutoTokenizer.from_pretrained(TXT[0], revision=TXT[1])
            kw = {"device_map": self.device}
            if self.device == "cuda" and torch.cuda.get_device_properties(0).total_memory < 40 * 2 ** 30:
                # GPU de 24 GB: el 14B BF16 no cabe; offload de las últimas capas a CPU (misma numérica)
                kw = {"device_map": "auto", "max_memory": {0: "21GiB", "cpu": "55GiB"}}
            m = AutoModelForCausalLM.from_pretrained(TXT[0], revision=TXT[1], torch_dtype=torch.bfloat16,
                                                     **kw).eval()
            for t in todo:
                chat = tok.apply_chat_template([{"role": "user", "content": PROMPT.format(
                    stretches=stretches_text(t, 8))}], tokenize=False, add_generation_prompt=True)
                inp = tok([chat], return_tensors="pt").to(m.device)
                with torch.inference_mode():
                    g = m.generate(**inp, max_new_tokens=70, do_sample=False)
                done[key(t)] = tok.decode(g[0, inp.input_ids.shape[1]:], skip_special_tokens=True).strip().splitlines()[0]
                f.write_text(json.dumps(done, ensure_ascii=False))
            del m
            import gc
            gc.collect()
            torch.cuda.empty_cache()
        for t in self.doc["levels"]["default"]["topics"]:
            t["topic_label"] = clean_label(done.get(key(t), t["label"]))

    # 11
    def speakers(self):
        from .identities import identities, speakers_of
        units = self.state["units"]
        # EXP-026: solo unidades con habla ASR (≥ 50 % cubierta); no inferior en AMI, menos grupos espurios en BBC
        speech = np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in self.asr_segments)
                           >= 0.5 * (u1 - u0) for u0, u1 in units])
        backend = self.cfg.get("speaker_backend") or ("wavlm_sv" if self.cfg.get("speaker_embed") else "voice_features")
        if backend == "pyannote_c1":
            from .diarization import public_turns, rttm, run_diarization, unit_labels
            f = self.work / "diar.pyannote_c1.3533c8cf.json"
            run_diarization(self.work / "audio.wav", f)
            turns = rttm(f.with_suffix(".rttm"))
            vid = unit_labels(units, turns, speech)
            self.doc["speaker_turns"] = public_turns(turns)
        else:
            x = np.asarray(self.arrays["voice"][:len(units)], np.float32)
            if self.cfg.get("speaker_embed"):
                # EXP-028: identidad por embedding de hablante (WavLM-sv), no por rasgos de voz
                f = self.work / f"speaker_xvec{V.suffix(self.var['speaker'])}.npy"
                if f.exists():
                    x = np.load(f)
                else:
                    from .speaker import XVec
                    from .voice import load_audio
                    x = XVec(self.device, half=self.var["speaker"] != "ref")(load_audio(str(self.work / "audio.wav")), units, speech)
                    np.save(f, x)
            vid = np.full(len(units), -1)
            single = False
            if self.cfg.get("speaker_embed"):
                from .speaker import single_speaker
                single = single_speaker(x, speech)  # EXP-029
            if single:
                vid[speech] = 1
            elif speech.sum() >= 10:
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
        self.doc["voice_identity_signal"] = backend
        (self.out / "topic_map.json").write_text(json.dumps(self.doc, ensure_ascii=False, indent=1))

    # 12-13
    def versions_and_clips(self, cut=True):
        from .versions import build_versions, check_versions
        v = build_versions(self.doc)
        gate = check_versions(v)
        (self.out / "versions.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
        csuf = V.suffix(self.var["clips"])
        clips_dir = self.out / f"clips{csuf}"
        clips_dir.mkdir(exist_ok=True)
        venc = (["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-pix_fmt", "yuv420p"] if self.var["clips"] != "ref"
                else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"])
        made = 0
        for prof, spec in v.items():
            for k, pl in enumerate(spec.get("playlists", [])):
                if not pl:
                    continue
                parts = []
                for j, c in enumerate(pl):
                    # nombre por tramo exacto: un mapa distinto nunca reutiliza un clip viejo con el mismo nombre
                    name = re.sub(r"[^\w.-]+", "_", f"{prof}_{k}_{j:03d}_{c['t0']:.2f}-{c['t1']:.2f}")[:90]
                    dst = clips_dir / f"{name}.mp4"
                    if cut and not dst.exists():
                        span = ["-ss", f"{c['t0']:.2f}", "-to", f"{c['t1']:.2f}"]
                        inputs = span + ["-i", str(self.video)]
                        maps = []
                        if self.audio_src:            # video sin audio: se muxea la pista externa
                            inputs += span + ["-i", str(self.audio_src)]
                            maps = ["-map", "0:v:0", "-map", "1:a:0"]
                        subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, *maps, *venc, "-c:a", "aac", str(dst)],
                                       capture_output=True)
                    c["file"] = str(dst.relative_to(self.out))
                    if dst.exists():
                        parts.append(dst)
                        made += 1
                if cut and parts:
                    lst = clips_dir / f"{prof}_{k}.txt"
                    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                                    "-c", "copy", str(self.out / f"version_{prof}_{k}{csuf}.mp4")], capture_output=True)
        (self.out / "versions.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
        self._clips_jsonl(v)
        self._index(v, gate)
        self.log(f"versiones: G-versión {gate['G_version']}, {made} clips")
        return gate

    # registros para entrenamiento (RL): una fila por clip, sin GT; las recompensas se calculan aparte
    def _clips_jsonl(self, v):
        topics = {t["topic_id"]: t for t in self.doc["levels"]["default"]["topics"]}
        rows = []
        for prof, spec in v.items():
            for k, pl in enumerate(spec.get("playlists", []) or []):
                for j, c in enumerate(pl or []):
                    t = topics.get(c["topic_id"], {})
                    span = next((sp for sp in t.get("spans", []) if sp[0] <= c["t0"] + 1e-6 and c["t1"] <= sp[1] + 1e-6), None)
                    ctx = t["context"][t["spans"].index(span)] if span and "context" in t else {}
                    rows.append({
                        "clip_id": f"{self.video.stem}:{c['t0']:.2f}-{c['t1']:.2f}",
                        "video": self.video.stem, "profile": self.cfg["profile"],
                        "version": prof, "playlist": k, "order": j, "file": c.get("file"),
                        "t0": round(float(c["t0"]), 2), "t1": round(float(c["t1"]), 2),
                        "duration_s": round(float(c["t1"] - c["t0"]), 2),
                        "budget_s": spec.get("budget_s"),
                        "topic_id": c["topic_id"], "topic_label": c.get("label"),
                        "topic_duration_s": t.get("duration_s"), "topic_returns": t.get("returns"),
                        "topic_span": span, "trimmed": bool(span and (c["t1"] - c["t0"]) < (span[1] - span[0]) - 1e-6),
                        "provenance": t.get("provenance"), "flags": t.get("flags"),
                        "speakers": (ctx or {}).get("speakers", t.get("speakers")),
                        "seen": (ctx or {}).get("seen"), "said": (ctx or {}).get("said"),
                    })
        with open(self.out / "clips.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def _manifest(self, gate, timings):
        """Procedencia completa de la corrida: código, modelos (revisión exacta en caché), perfil, entrada."""
        import datetime
        import hashlib
        import platform

        def git(*a):
            try:
                return subprocess.run(["git", *a], cwd=Path(__file__).resolve().parents[1], capture_output=True,
                                      text=True, check=True).stdout.strip()
            except Exception:
                return None

        def snap(repo, pinned=None):
            if pinned:
                return pinned
            ref = Path(HF) / "hub" / f"models--{repo.replace('/', '--')}" / "refs" / "main"
            if ref.exists():
                return ref.read_text().strip()
            snaps = sorted((Path(HF) / "hub" / f"models--{repo.replace('/', '--')}" / "snapshots").glob("*"))
            return snaps[0].name if len(snaps) == 1 else None

        def sha256(path):
            h = hashlib.sha256()
            with open(path, "rb") as fh:
                for b in iter(lambda: fh.read(1 << 20), b""):
                    h.update(b)
            return h.hexdigest()
        from .speaker import WAVLM
        models = {"asr": ("Systran/faster-whisper-large-v3", snap("Systran/faster-whisper-large-v3")),
                  "visual": ("google/siglip-base-patch16-224", snap("google/siglip-base-patch16-224")),
                  "text_embed": ("BAAI/bge-base-en-v1.5", snap("BAAI/bge-base-en-v1.5")),
                  "vjudge": VL, "labels": TXT if self.do_labels else None}
        backend = self.cfg.get("speaker_backend") or ("wavlm_sv" if self.cfg.get("speaker_embed") else "voice_features")
        if self.cfg.get("speaker_embed") and backend != "pyannote_c1":
            models["speaker"] = WAVLM
        if backend == "pyannote_c1":
            from .diarization import DIARIZATION, PYANNOTE_AUDIO
            models["diarization"] = DIARIZATION
        d = self.doc["levels"]["default"]
        man = {"schema": "cava-run-v1",
               "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
               "video": {"path": str(self.video), "sha256": sha256(self.video), "duration_s": self.state.get("duration")},
               "audio": {"path": str(self.audio_src), "sha256": sha256(self.audio_src)} if self.audio_src else None,
               "code": {"git_commit": git("rev-parse", "HEAD"), "git_dirty": bool(git("status", "--porcelain", "--untracked-files=no", "--", "topicagg", "scripts")),
                        "python": platform.python_version()},
               "profile": self.cfg, "summary_s": self.summary_s, "labels": self.do_labels,
               "models": {k: (list(v) if v else None) for k, v in models.items()},
               "outputs": {"n_units": len(self.state["units"]), "n_topics": d["n_topics"],
                           "n_returning": d["n_returning"], "voice_identities": self.doc.get("voice_identities"),
                           "voice_identity_kind": self.doc.get("voice_identity_kind"),
                           "G_version": gate["G_version"], "files": ["topic_map.json", "versions.json",
                                                                     "clips.jsonl", "index.json", "index.md"]},
               "gt_used": False, "timings_s": timings}
        if self.asr_mode != "ref":
            man["asr_mode"] = self.asr_mode  # solo si no es ref: el manifiesto ref no cambia
        if any(v != "ref" for v in self.var.values()):
            man["variant"] = self.var  # solo si no es ref: el manifiesto ref no cambia
            man["timings_detail_s"] = self.sub_timings
        if self.stack != "v1.0":
            man["stack"] = self.stack
            if backend == "pyannote_c1":
                man["pyannote_audio"] = PYANNOTE_AUDIO
        (self.out / "run_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1))

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
        import time
        timings = {}
        for name in ("prepare", "asr", "signals", "vjudge", "topic_map", "labels", "speakers"):
            t0 = time.time()
            getattr(self, name)()
            timings[name] = round(time.time() - t0, 1)
        t0 = time.time()
        gate = self.versions_and_clips(cut=cut)
        timings["versions_and_clips"] = round(time.time() - t0, 1)
        self._manifest(gate, timings)
        return gate
