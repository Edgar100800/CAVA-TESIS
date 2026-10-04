"""EXP-028, comprobaciones previas a la adopción:
  (a) AMI fresh3: no inferioridad del xvec frente a los rasgos de voz en ARI (margen −0.02), mismas unidades
      de 10 s, filtro de habla = unidad con texto ASR (como EXP-026), ward + BIC.
  (b) BBC 01–11 (sin criterio): K_eff de narrador con xvec frente a rasgos de voz, filtro de habla ASR.
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import k_eff, speech_gate, voice_ids  # noqa: E402
from eval_speaker_embed import XVec  # noqa: E402
from eval_voice_identities import dominant  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402

D = Path("data/ami")
xv = XVec()
rep = {"ami": {}, "bbc": {}}
for m in Path("data/ami/meetings_fresh3.txt").read_text().split():
    fz, fj, wav = D / "signals" / f"{m}.npz", D / "signals" / f"{m}.json", D / "media" / m / f"{m}.Mix-Headset.wav"
    if not (fz.exists() and fj.exists() and wav.exists()):
        continue
    hand = np.load(fz)["voice"].astype(np.float32)
    meta = json.loads(fj.read_text())
    n = min(len(hand), len(meta["unit_times"]))
    units = meta["unit_times"][:n]
    gate = np.array([bool((t or "").strip()) for t in meta["asr_text"][:n]])
    x = xv(load_audio(str(wav)), units, gate)
    dom = dominant(units, json.loads((D / "gt" / f"{m}.json").read_text())["speech"])
    r = {}
    for name, sig in (("hand", hand[:n]), ("xvec", x)):
        lab = voice_ids(sig, gate=gate)
        idx = [i for i in range(n) if dom[i] and lab[i] >= 0]
        r[f"ari_{name}"] = float(adjusted_rand_score([dom[i] for i in idx], lab[idx])) if idx else 0.0
    rep["ami"][m] = r
    print("ami", m, {k: round(v, 3) for k, v in r.items()}, flush=True)
for ep in range(1, 12):
    w = Path("data/cava_runs_doc") / f"bbc_{ep:02d}" / "work"
    st = json.loads((w / "state.json").read_text())
    hand = np.load(w / "signals.npz")["voice"].astype(np.float32)
    n = min(len(hand), len(st["units"]))
    units = st["units"][:n]
    sp = speech_gate(units, st["asr_segments"])
    x = xv(load_audio(str(w / "audio.wav")), units, sp)
    rep["bbc"][f"bbc_{ep:02d}"] = {f"keff_{k}": k_eff(voice_ids(s, gate=sp), sp) for k, s in (("hand", hand[:n]), ("xvec", x))}
    print("bbc", ep, rep["bbc"][f"bbc_{ep:02d}"], flush=True)
d = np.array([r["ari_xvec"] - r["ari_hand"] for r in rep["ami"].values()])
rep["ami_summary"] = {"n": len(d), "ari_hand": float(np.mean([r["ari_hand"] for r in rep["ami"].values()])),
                      "ari_xvec": float(np.mean([r["ari_xvec"] for r in rep["ami"].values()])),
                      "xvec_minus_hand": {"mean": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d)))},
                      "non_inferior": bool(d.mean() > -0.02)}
rep["bbc_summary"] = {k: float(np.mean([r[k] for r in rep["bbc"].values()])) for k in ("keff_hand", "keff_xvec")}
Path("results/exp028_secondary.json").write_text(json.dumps(rep, indent=1))
print(json.dumps({k: v for k, v in rep.items() if k.endswith("summary")}, indent=1))
