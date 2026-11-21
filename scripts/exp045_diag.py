"""EXP-045-Q: diagnósticos de embeddings sobre los artefactos de la corrida ref (GPU).

Uso: python scripts/exp045_diag.py --names Spider_Man,bbc_01
Por video escribe en <exp045>/runs/diag/<video>/:
  visual_fp16_exact.npy  SigLIP FP16 en lotes sobre los MISMOS fotogramas exactos de la corrida ref (aísla la precisión)
  bge_asr_cpu.npy / bge_asr_gpu.npy   bge FP32-CPU vs FP16-GPU sobre el texto ASR por unidad (ref)
  bge_vj_cpu.npy  / bge_vj_gpu.npy    ídem sobre los resúmenes vjudge ref (un vector por bloque)
  voice_s.json           tiempo de los rasgos de voz (CPU) para separar voz de SigLIP en 'signals'
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp045_common import EXP, VIDEOS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default=",".join(VIDEOS))
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args()
    import torch
    from PIL import Image
    from transformers import AutoModel, AutoProcessor

    from topicagg.embed import BgeEmbedder
    from topicagg.voice import load_audio, voice_features
    proc = AutoProcessor.from_pretrained("google/siglip-base-patch16-224")
    sm = AutoModel.from_pretrained("google/siglip-base-patch16-224").to(a.device).eval().half()
    cpu, gpu = BgeEmbedder(), BgeEmbedder(a.device, half=True)
    for name in a.names.split(","):
        run = EXP / "runs" / "ref" / name
        out = EXP / "runs" / "diag" / name
        out.mkdir(parents=True, exist_ok=True)
        st = json.loads((run / "work/state.json").read_text())
        units = st["units"]
        fr = run / "work/frames"
        ok, paths = [], []
        for k in range(len(units)):
            p = fr / f"u{k:05d}.jpg"
            paths.append(p)
            if p.exists() and p.stat().st_size > 0:
                ok.append(k)
        vis = np.zeros((len(units), 768), np.float32)
        for i in range(0, len(ok), 64):
            ks = ok[i:i + 64]
            ims = [Image.open(paths[k]).convert("RGB") for k in ks]
            with torch.inference_mode():
                px = proc(images=ims, return_tensors="pt").to(a.device)
                px = {x: (y.half() if y.is_floating_point() else y) for x, y in px.items()}
                o = sm.get_image_features(**px)
                o = (o.pooler_output if hasattr(o, "pooler_output") else o[0]).float().cpu().numpy()
            vis[ks] = o
        np.save(out / "visual_fp16_exact.npy", vis)
        asr = st["asr"]
        sums = json.loads((run / "work/summaries.json").read_text())
        for tag, texts in (("asr", asr), ("vj", [s["summary"] for s in sums])):
            np.save(out / f"bge_{tag}_cpu.npy", cpu(texts))
            np.save(out / f"bge_{tag}_gpu.npy", gpu(texts))
        t0 = time.time()
        voice_features(load_audio(str(run / "work/audio.wav")), units)
        (out / "voice_s.json").write_text(json.dumps({"voice_s": round(time.time() - t0, 1), "duration_s": st["duration"]}))
        print("diag", name, flush=True)


if __name__ == "__main__":
    main()
