"""EXP-034: caché por ítem de los filtros de habla en GPU (ver pre-registro).

  whisper   segmentos de Whisper large-v3 exactamente como el pipeline (vad_filter); en AMI y BBC se reutilizan
            los del caché existente (gate de xvec.npz / state.json)
  parakeet  texto por unidad (referencia; en AMI y BBC del caché de EXP-030)
  silero    segmentos de Silero VAD v5 (ONNX de faster-whisper, opciones por defecto)
  ast       P(Speech) y P(Music) por unidad (AST AudioSet, revisión fijada)
  xvec      x-vector de TODAS las unidades (mix, ami, bbc), para aplicar cualquier filtro después
→ data/gatebench/cache/<dom>/<id>.json (+ .xall.npy)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exp034_items import G, all_items  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402

AST = ("MIT/ast-finetuned-audioset-10-10-0.4593", "f826b80d28226b62986cc218e5cec390b1096902")
SR = 16000


class AstSpeech:
    def __init__(self, device="cuda"):
        import torch
        from transformers import ASTFeatureExtractor, ASTForAudioClassification
        self.torch, self.device = torch, device
        self.fe = ASTFeatureExtractor.from_pretrained(AST[0], revision=AST[1])
        self.m = ASTForAudioClassification.from_pretrained(AST[0], revision=AST[1]).to(device).eval().half()
        lab = {v: int(k) for k, v in self.m.config.id2label.items()}
        self.i_speech, self.i_music = lab["Speech"], lab["Music"]

    def __call__(self, audio, units, bs=32):
        sp, mu = [], []
        for k in range(0, len(units), bs):
            x = [audio[int(a * SR):max(int(b * SR), int(a * SR) + SR // 10)] for a, b in units[k:k + bs]]
            inp = self.fe(x, sampling_rate=SR, return_tensors="pt")
            with self.torch.no_grad():
                p = self.torch.sigmoid(self.m(inp["input_values"].to(self.device).half()).logits.float()).cpu().numpy()
            sp += p[:, self.i_speech].tolist()
            mu += p[:, self.i_music].tolist()
        return sp, mu


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doms", nargs="+", default=["ava", "mix", "ami", "bbc"])
    args = ap.parse_args()
    from faster_whisper import WhisperModel
    from faster_whisper.vad import get_speech_timestamps
    from topicagg.asr_parakeet import Parakeet
    from topicagg.speaker import XVec
    wm = WhisperModel("large-v3", device="cuda", compute_type="float16")
    pk, xv, ast = Parakeet(), XVec(), AstSpeech()
    for it in all_items(args.doms):
        o = G / "cache" / it["dom"] / f"{it['id']}.json"
        if o.exists():
            continue
        o.parent.mkdir(parents=True, exist_ok=True)
        audio = load_audio(it["wav"])
        units = it["units"]
        # la última unidad puede pasar el final del audio (AVA corto, BBC): relleno con silencio
        need = int((max(b for _, b in units) + 1.0) * SR)
        if len(audio) < need:
            audio = np.concatenate([audio, np.zeros(need - len(audio), np.float32)])
        r = {"units": units}
        if it["dom"] in ("ava", "mix", "docmix"):
            segs, _ = wm.transcribe(it["wav"], vad_filter=True)
            r["whisper_segments"] = [(s.start, s.end, s.text.strip()) for s in segs]
            r["parakeet"] = pk.units(audio, units)
        elif it["dom"] == "bbc":
            w = Path(it["wav"]).parent
            r["whisper_segments"] = json.loads((w / "state.json").read_text())["asr_segments"]
            r["parakeet"] = json.loads((Path("data/asr_compare/bbc") / f"{it['id']}.json").read_text())["parakeet"]
        else:  # ami: el filtro Whisper es el gate del caché de identidades (EXP-028/029)
            z = np.load(Path("data/ami/signals") / f"{it['id']}.xvec.npz")
            r["whisper_gate"] = z["gate"].tolist()
            r["dom_gt"] = [str(d) for d in z["dom"]]
            r["parakeet"] = json.loads((Path("data/asr_compare/ami") / f"{it['id']}.json").read_text())["parakeet"]
        r["silero_segments"] = [(t["start"] / SR, t["end"] / SR) for t in get_speech_timestamps(audio)]
        r["ast_speech"], r["ast_music"] = ast(audio, units)
        if it["dom"] != "ava":
            np.save(o.with_suffix(".xall.npy"), xv(audio, units, np.ones(len(units), bool)).astype(np.float16))
        o.write_text(json.dumps(r, ensure_ascii=False))
        print(f"[cache] {it['dom']} {it['id']} ({len(units)} unidades)", flush=True)
    print("EXP034_CACHE_DONE", flush=True)


if __name__ == "__main__":
    main()
