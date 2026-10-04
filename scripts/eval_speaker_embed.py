"""EXP-028: identidad del hablante fuera de reuniones (VoxConverse: noticias, debates, programas con música y ruido).

Por archivo: unidades de 5 s (perfil film/documentary); hablante dominante GT por unidad (RTTM: ≥ 60 %
del habla de la unidad y ≥ 1.5 s de habla); filtro de habla = unidades con ≥ 50 % de habla GT (VAD oráculo,
el mismo para ambas señales: aísla la pregunta de identidad).
Señales:
  hand   rasgos de voz actuales (log-mel + tono, z-score por video; topicagg/voice.py)
  xvec   embedding de hablante WavLM-base-plus-sv (frozen, safetensors verificados = pesos oficiales)
Métricas: AUC "mismo hablante" sobre pares a ≥ 2 unidades; ARI de identidades ward + K por BIC (EXP-022d)
frente al hablante dominante; |K_eff − K_true| (identidades / hablantes con ≥ 5 % de las unidades).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_ami import auc  # noqa: E402
from eval_bbc import k_eff, voice_ids  # noqa: E402
from topicagg.voice import load_audio, voice_features  # noqa: E402

V = Path("data/voxconverse")
WAVLM = ("microsoft/wavlm-base-plus-sv", "939f573b5e1a33c20332a5fe9ac34f95a66c4f07")
UNIT = 5.0


class XVec:
    def __init__(self, device=None):
        device = device or ("cuda" if __import__("torch").cuda.is_available() else "cpu")
        import torch
        from transformers import AutoFeatureExtractor, WavLMForXVector
        self.torch, self.device = torch, device
        self.fe = AutoFeatureExtractor.from_pretrained(WAVLM[0], revision=WAVLM[1])
        self.m = WavLMForXVector.from_pretrained(WAVLM[0], revision=WAVLM[1], use_safetensors=True).to(device).eval()

    def __call__(self, audio, units, gate, sr=16000, bs=32):
        out = np.zeros((len(units), 512), np.float32)
        idx = [i for i in range(len(units)) if gate[i]]
        for k in range(0, len(idx), bs):
            chunk = idx[k:k + bs]
            x = [audio[int(units[i][0] * sr):int(units[i][1] * sr)] for i in chunk]
            inp = self.fe(x, sampling_rate=sr, return_tensors="pt", padding=True).to(self.device)
            with self.torch.no_grad():
                out[chunk] = self.m(**inp).embeddings.float().cpu().numpy()
        return out


def rttm(path):
    segs = []
    for line in Path(path).read_text().splitlines():
        p = line.split()
        if p and p[0] == "SPEAKER":
            segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
    return segs


def unit_gt(units, segs):
    dom, gate = [], []
    for u0, u1 in units:
        ov = {}
        for a, b, s in segs:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0.0) + o
        tot = sum(ov.values())
        sp = max(ov, key=ov.get) if ov else None
        dom.append(sp if sp and ov[sp] >= 0.6 * tot and ov[sp] >= 1.5 else None)
        gate.append(min(tot, u1 - u0) >= 0.5 * (u1 - u0))
    return dom, np.array(gate)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    gt_dir = next(V.glob(f"voxconverse-master/{args.split}"))
    wavs = sorted(V.glob(f"wav_{args.split}/**/*.wav"))
    if args.limit:
        wavs = wavs[:args.limit]
    xv = XVec()
    rows = {}
    for w in wavs:
        rt = gt_dir / f"{w.stem}.rttm"
        if not rt.exists():
            continue
        audio = load_audio(str(w))
        dur = len(audio) / 16000
        units = [[t, min(t + UNIT, dur)] for t in np.arange(0, dur - 1.0, UNIT)]
        dom, gate = unit_gt(units, rttm(rt))
        lab = [d for d in dom if d]
        spk, cnt = np.unique(lab, return_counts=True) if lab else ([], [])
        k_true = int((np.asarray(cnt) / max(1, len(lab)) >= 0.05).sum())
        sig = {"hand": voice_features(audio, units), "xvec": xv(audio, units, gate)}
        r = {"n_units": len(units), "speech_frac": float(gate.mean()), "k_true": k_true}
        I, J = np.triu_indices(len(units), 2)
        keep = [(i, j) for i, j in zip(I, J) if dom[i] and dom[j] and gate[i] and gate[j]]
        for name, x in sig.items():
            ok = np.linalg.norm(x, axis=1) > 0
            xn = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-9)
            kk = [(i, j) for i, j in keep if ok[i] and ok[j]]
            yy = [dom[i] == dom[j] for i, j in kk]
            r[f"auc_{name}"] = auc([float(xn[i] @ xn[j]) for i, j in kk], yy) if kk and 0 < sum(yy) < len(yy) else None
            vid = voice_ids(x, gate=gate)
            idx = [i for i in range(len(units)) if dom[i] and vid[i] >= 0]
            r[f"ari_{name}"] = float(adjusted_rand_score([dom[i] for i in idx], vid[idx])) if len(idx) > 5 else None
            r[f"kerr_{name}"] = abs(k_eff(vid, gate) - k_true)
        rows[w.stem] = r
        print(w.stem, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)

    def paired(a, b):
        d = np.array([x[a] - x[b] for x in rows.values() if x[a] is not None and x[b] is not None])
        se = d.std(ddof=1) / np.sqrt(len(d))
        return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d),
                "z": round(float(d.mean() / se), 2) if se > 0 else None}
    mean = lambda k: round(float(np.mean([x[k] for x in rows.values() if x[k] is not None])), 4)  # noqa: E731
    rep = {"split": args.split, "n": len(rows),
           "means": {k: mean(k) for k in ("auc_hand", "auc_xvec", "ari_hand", "ari_xvec", "kerr_hand", "kerr_xvec",
                                          "k_true", "speech_frac")},
           "criteria": {"auc_xvec_minus_hand": paired("auc_xvec", "auc_hand"),
                        "ari_xvec_minus_hand": paired("ari_xvec", "ari_hand"),
                        "kerr_hand_minus_xvec": paired("kerr_hand", "kerr_xvec")},
           "per_file": rows}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_file"}, indent=1))


if __name__ == "__main__":
    main()
