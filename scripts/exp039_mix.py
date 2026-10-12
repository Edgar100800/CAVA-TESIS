"""EXP-039: domix, voces dominantes con estructura de documental (ver pre-registro en EXPERIMENT_LOG).

Fuentes: archivos de VoxConverse con K_true >= 2 y voz principal >= 70 % de las unidades con hablante, no usados en
docmix (40 por split). Mismo generador que EXP-035a (exp035_mix): fondo a 15 dB bajo la voz, huecos de solo fondo de
4–20 s a 0 dB con p = 0.6, música y ruido, MUSAN dividido como en EXP-034, semilla 0.
→ data/gatebench/domix/{dev,conf}/<file>__<cond>.{wav,json}
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
from exp035_mix import GAP, P_GAP, SNR_GAP, SNR_UNDER, V, chunks  # noqa: E402
from topicagg.voice import load_audio  # noqa: E402

TOP = 0.70


def sources(vsplit, split):
    used = {json.loads(f.read_text())["src"] for f in (G / "docmix" / split).glob("*.json")}
    out = []
    for rt in sorted((V / "voxconverse-master" / vsplit).glob("*.rttm")):
        segs = rttm(rt)
        dom, _ = unit_gt(grid(max(b for _, b, _ in segs) + 1.0), segs)
        lab = [d for d in dom if d]
        if rt.stem in used or k_true(dom) < 2:
            continue
        _, c = np.unique(lab, return_counts=True)
        if c.max() / len(lab) >= TOP:
            out.append((rt.stem, float(c.max() / len(lab))))
    return out


def main():
    for split, vsplit in (("dev", "dev"), ("conf", "test")):
        rng = np.random.default_rng(0)
        beds = {"music": musan_split("music", split), "noise": musan_split("noise", split)}
        out = G / "domix" / split
        out.mkdir(parents=True, exist_ok=True)
        srcs = sources(vsplit, split)
        print(f"[domix] {split}: {len(srcs)} fuentes", flush=True)
        for src, top in srcs:
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
                f.with_suffix(".json").write_text(json.dumps({
                    "src": src, "vsplit": vsplit, "cond": cond, "snr_under_db": SNR_UNDER, "snr_gap_db": SNR_GAP,
                    "k_true": k_true(dom), "top_share_src": top, "units": units, "gt_speech": gate.tolist(), "dom": dom}))
            print(f"[domix] {split} {src} (principal {top:.2f})", flush=True)


if __name__ == "__main__":
    main()
