"""EXP-034: narrador sintético con GT exacto (VoxConverse + MUSAN), ver pre-registro.

Archivos con K_true = 1 (regla de EXP-028) y el mismo número con K_true >= 2 (semilla 0), por split
(VoxConverse dev = desarrollo, test = confirmación). Condiciones: limpio, música MUSAN a SNR 5 dB, ruido MUSAN a
SNR 5 dB. El fondo cubre todo el archivo; su nivel se fija respecto al RMS del habla RTTM. Los archivos de MUSAN se
dividen por sha1 del nombre (par = desarrollo, impar = confirmación).
→ data/gatebench/mix/{dev,conf}/<file>__<cond>.{wav,json}
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_speaker_embed import rttm, unit_gt  # noqa: E402
from exp034_items import G, grid  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402

V = Path("data/voxconverse")
SR = 16000
SNR_DB = 5.0


def k_true(dom):
    lab = [d for d in dom if d]
    if not lab:
        return 0
    _, c = np.unique(lab, return_counts=True)
    return int((c / len(lab) >= 0.05).sum())


def musan_split(kind, split):
    fs = sorted((G / "musan" / kind).glob("**/*.wav"))
    par = 0 if split == "dev" else 1
    return [f for f in fs if int(hashlib.sha1(f.name.encode()).hexdigest(), 16) % 2 == par]


def bed(files, n, rng):
    out, k = [], 0
    order = rng.permutation(len(files))
    while k < n:
        a = load_audio(str(files[order[len(out) % len(order)]]))
        a = a[: n - k] if len(a) else np.zeros(SR, np.float32)
        out.append(a)
        k += len(a)
    return np.concatenate(out)[:n]


def write_wav(path, x):
    import wave
    y = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((y * 32767).astype("<i2").tobytes())


def main():
    for vsplit, split in (("dev", "dev"), ("test", "conf")):
        rng = np.random.default_rng(0)
        gt_dir = V / "voxconverse-master" / vsplit
        rows = []
        for w in sorted(V.glob(f"wav_{vsplit}/**/*.wav")):
            rt = gt_dir / f"{w.stem}.rttm"
            if not rt.exists() or "__MACOSX" in str(w):
                continue
            segs = rttm(rt)
            dur = max(b for _, b, _ in segs) if segs else 0
            units = grid(dur + 1.0)
            dom, _ = unit_gt(units, segs)
            rows.append((w, k_true(dom)))
        single = [w for w, k in rows if k == 1]
        multi = [w for w, k in rows if k >= 2]
        pick = single + [multi[i] for i in sorted(rng.choice(len(multi), len(single), replace=False))]
        beds = {"music": musan_split("music", split), "noise": musan_split("noise", split)}
        out = G / "mix" / split
        out.mkdir(parents=True, exist_ok=True)
        for w in pick:
            segs = rttm(V / "voxconverse-master" / vsplit / f"{w.stem}.rttm")
            audio = load_audio(str(w))
            dur = len(audio) / SR
            units = grid(dur)
            dom, gate = unit_gt(units, segs)
            sp = np.zeros(len(audio), bool)
            for a, b, _ in segs:
                sp[int(a * SR):int(b * SR)] = True
            rms_sp = float(np.sqrt(np.mean(audio[sp] ** 2))) if sp.any() else 0.05
            for cond in ("clean", "music", "noise"):
                f = out / f"{w.stem}__{cond}"
                if f.with_suffix(".json").exists():
                    continue
                x = audio
                if cond != "clean":
                    b = bed(beds[cond], len(audio), rng)
                    rb = float(np.sqrt(np.mean(b ** 2))) or 1e-6
                    x = audio + b * (rms_sp / rb) * 10 ** (-SNR_DB / 20)
                    x = x / max(1.0, float(np.abs(x).max()))
                write_wav(f.with_suffix(".wav"), x)
                f.with_suffix(".json").write_text(json.dumps({
                    "src": w.stem, "vsplit": vsplit, "cond": cond, "snr_db": None if cond == "clean" else SNR_DB,
                    "k_true": k_true(dom), "units": units, "gt_speech": gate.tolist(), "dom": dom}))
            print(f"[mix] {split} {w.stem} K={k_true(dom)}", flush=True)
        print(f"[mix] {split}: {len(single)} con K=1, {len(single)} con K>=2", flush=True)


if __name__ == "__main__":
    main()
