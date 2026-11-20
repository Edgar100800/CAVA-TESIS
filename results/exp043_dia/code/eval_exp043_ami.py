"""EXP-043-DIA, comprobación previa a la adopción: AMI fresh3 (40 reuniones), no inferioridad
ARI(P) − ARI(C) > −0.02 (media), mismo protocolo que exp028_secondary.py (unidades de 10 s,
filtro de habla = unidad con texto ASR, hablante dominante con dominant() de EXP-020).
C = xvec cacheado + detector EXP-029 + ward/BIC (producto). P = pyannote, hablante mayoritario por unidad.
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, "/data/tesis-cava/CAVA_minimo")
sys.path.insert(0, "/data/tesis-cava/exp036/dia")
from topicagg.speaker import single_speaker  # noqa: E402

A = Path("/data/tesis-cava/data_ami")
ref = json.load(open("/data/tesis-cava/exp036/dia/ref/exp028_secondary.json"))["ami"] \
    if Path("/data/tesis-cava/exp036/dia/ref/exp028_secondary.json").exists() else {}


def load_eval():
    import importlib.util
    spec = importlib.util.spec_from_file_location("e", "/data/tesis-cava/exp036/dia/eval_exp043.py")
    src = Path(spec.origin).read_text()
    ns = {}
    for name in ("voice_ids", "k_eff", "rttm", "unit_major"):
        start = src.index(f"def {name}(")
        end = src.index("\n\n\n", start)
        exec(src[start:end], {"np": np, "Path": Path}, ns)
    return ns


f = load_eval()


def dominant(units, speech):  # copia literal de scripts/eval_voice_identities.py
    dom = []
    for u0, u1 in units:
        ov = {}
        for s, a, b in speech:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0) + o
        tot = sum(ov.values())
        sp = max(ov, key=ov.get) if ov else None
        dom.append(sp if ov and ov[sp] >= 0.6 * tot and tot > 3 else None)
    return dom


def ari(dom, lab):
    idx = [i for i in range(len(dom)) if dom[i] and lab[i] >= 0]
    return float(adjusted_rand_score([dom[i] for i in idx], lab[idx])) if idx else 0.0


rows = {}
for m in (A / "meetings_fresh3.txt").read_text().split():
    pr = A / "out_ami" / f"{m}.Mix-Headset.rttm"
    if not pr.exists():
        continue
    meta = json.loads((A / "signals" / f"{m}.json").read_text())
    xz = np.load(A / "signals" / f"{m}.xvec.npz")
    x = xz["x"].astype(np.float32)
    n = min(len(x), len(meta["unit_times"]))
    units, x = meta["unit_times"][:n], x[:n]
    gate = np.array([bool((t or "").strip()) for t in meta["asr_text"][:n]])
    dom = dominant(units, json.loads((A / "gt" / f"{m}.json").read_text())["speech"])
    c28 = f["voice_ids"](x, gate)
    if single_speaker(x, gate):
        cvid = np.where(gate & (np.linalg.norm(x, axis=1) > 0), 1, -1)
    else:
        cvid = c28
    pm = f["unit_major"](units, f["rttm"](pr))
    names = {s: i + 1 for i, s in enumerate(sorted({s for s in pm if s}))}
    pvid = np.array([names[s] if (s and gate[i]) else -1 for i, s in enumerate(pm)])
    rows[m] = {"ari_c28": ari(dom, c28), "ari_C": ari(dom, cvid), "ari_P": ari(dom, pvid),
               "single_C": bool(single_speaker(x, gate))}

d = np.array([r["ari_P"] - r["ari_C"] for r in rows.values()])
se = d.std(ddof=1) / np.sqrt(len(d))
same = [m for m in rows if m in ref]
rep = {"n": len(rows),
       "sanity_exp028_ari_xvec": {"exp028": round(float(np.mean([ref[m]["ari_xvec"] for m in same])), 4) if same else None,
                                  "recomputed_cache": round(float(np.mean([rows[m]["ari_c28"] for m in same])), 4) if same else None},
       "ari_C": round(float(np.mean([r["ari_C"] for r in rows.values()])), 4),
       "ari_P": round(float(np.mean([r["ari_P"] for r in rows.values()])), 4),
       "P_minus_C": {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "z": round(float(d.mean() / se), 2)},
       "non_inferior": bool(d.mean() > -0.02),
       "single_C_meetings": sum(r["single_C"] for r in rows.values()),
       "per_meeting": rows}
Path("/data/tesis-cava/exp036/dia/exp043_ami_fresh3.json").write_text(json.dumps(rep, indent=1))
print(json.dumps({k: v for k, v in rep.items() if k != "per_meeting"}, indent=1))
