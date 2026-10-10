"""EXP-035a: narrador sintético con estructura de documental (ver pre-registro en EXPERIMENT_LOG).

Fuentes = los archivos de VoxConverse elegidos en EXP-034 (data/gatebench/mix/<split>/*__clean.json). El habla
RTTM se corta en tramos por fronteras de segmento RTTM (corrección de dev, ver log); debajo de la voz, fondo MUSAN a SNR 15 dB; tras cada tramo, con
p = 0.6, hueco de solo fondo de 4–20 s a 0 dB respecto al RMS del habla. Condiciones: música, ruido. Semilla 0.
→ data/gatebench/docmix/{dev,conf}/<file>__<cond>.{wav,json}
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_speaker_embed import rttm, unit_gt  # noqa: E402
from exp034_items import G, grid  # noqa: E402
from exp034_mix import SR, bed, k_true, musan_split, write_wav  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402

V = Path("data/voxconverse")
SNR_UNDER, SNR_GAP, P_GAP, GAP = 15.0, 0.0, 0.6, (4.0, 20.0)


def chunks(segs, min_sil=0.0):
    """Tramos de habla (a, b, [(a, b, spk), ...]) separados por silencios RTTM >= min_sil (0: toda frontera de segmento RTTM)."""
    segs = sorted(segs)
    out = []
    for a, b, s in segs:
        if out and a - out[-1][1] < min_sil:
            out[-1][1] = max(out[-1][1], b)
            out[-1][2].append((a, b, s))
        else:
            out.append([a, b, [(a, b, s)]])
    return out


def main():
    for split, vsplit in (("dev", "dev"), ("conf", "test")):
        rng = np.random.default_rng(0)
        beds = {"music": musan_split("music", split), "noise": musan_split("noise", split)}
        out = G / "docmix" / split
        out.mkdir(parents=True, exist_ok=True)
        srcs = sorted(json.loads(f.read_text())["src"] for f in (G / "mix" / split).glob("*__clean.json"))
        fracs = []
        for src in srcs:
            segs = rttm(V / "voxconverse-master" / vsplit / f"{src}.rttm")
            audio = load_audio(str(next(V.glob(f"wav_{vsplit}/**/{src}.wav"))))
            sp = np.zeros(len(audio), bool)
            for a, b, _ in segs:
                sp[int(a * SR):int(b * SR)] = True
            rms_sp = float(np.sqrt(np.mean(audio[sp] ** 2))) if sp.any() else 0.05
            for cond in ("music", "noise"):
                f = out / f"{src}__{cond}"
                voice, gate_bed, new_segs, t = [], [], [], 0.0
                for a, b, ss in chunks(segs):
                    x = audio[int(a * SR):int(b * SR)]
                    voice.append(x)
                    gate_bed.append(np.full(len(x), 10 ** (-SNR_UNDER / 20), np.float32))
                    new_segs += [(t + (sa - a), t + (sb - a), s) for sa, sb, s in ss]
                    t += len(x) / SR
                    if rng.random() < P_GAP:
                        n = int(rng.uniform(*GAP) * SR)
                        voice.append(np.zeros(n, np.float32))
                        gate_bed.append(np.full(n, 10 ** (-SNR_GAP / 20), np.float32))
                        t += n / SR
                v = np.concatenate(voice)
                level = np.concatenate(gate_bed)
                b = bed(beds[cond], len(v), rng)
                rb = float(np.sqrt(np.mean(b ** 2))) or 1e-6
                x = v + b / rb * rms_sp * level
                x = x / max(1.0, float(np.abs(x).max()))
                write_wav(f.with_suffix(".wav"), x)
                units = grid(len(x) / SR)
                dom, gate = unit_gt(units, new_segs)
                fracs.append(float(gate.mean()))
                f.with_suffix(".json").write_text(json.dumps({
                    "src": src, "vsplit": vsplit, "cond": cond, "snr_under_db": SNR_UNDER, "snr_gap_db": SNR_GAP,
                    "k_true": k_true(dom), "units": units, "gt_speech": gate.tolist(), "dom": dom}))
            print(f"[docmix] {split} {src}", flush=True)
        print(f"[docmix] {split}: fracción de habla GT media {np.mean(fracs):.3f} (min {np.min(fracs):.3f}, max {np.max(fracs):.3f})", flush=True)


if __name__ == "__main__":
    main()
