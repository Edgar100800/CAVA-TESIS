"""EXP-043-DIA (exploratorio): pyannote en Spider-Man frente a V1–V8 (EXP-042-FID).

Etiqueta pyannote por unidad de 5 s = hablante con más tiempo en la unidad.
Tabla de contingencia V# × SPEAKER_xx, pureza en ambos sentidos, ARI, y cada
SPEAKER_xx con los personajes en pantalla y el movimiento de labios de sus unidades.
"""
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

W = Path("/data/tesis-cava/exp036/fid")
D = Path("/data/tesis-cava/exp036/dia/spider")
state = json.loads(Path("/data/tesis-cava/CAVA_minimo/outputs/Spider_Man/work/state.json").read_text())
units = state["units"]
vid = np.load(W / "smoke/voice_per_unit.npy")
split = json.loads((W / "smoke/v6_split.json").read_text())["V6_split"]
vlab = [f"V{int(v)}" if v >= 0 else None for v in vid]
for g, tag in (("1", "V6a"), ("2", "V6b")):
    for u in split[g]:
        vlab[u] = tag
VN = {"V1": "Mary Jane", "V2": "Yelena", "V3": "Peter", "V4": "Peter (máscara)", "V5": "Ned",
      "V6a": "Punisher", "V6b": "Bill Metzger", "V7": "sin asignar", "V8": "fuera de cuadro"}

segs = []
for line in open(D / "audio.rttm"):
    p = line.split()
    segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
plab, pcover = [], []
for a, b in units:
    acc = defaultdict(float)
    for s0, s1, spk in segs:
        o = min(b, s1) - max(a, s0)
        if o > 0:
            acc[spk] += o
    plab.append(max(acc, key=acc.get) if acc else None)
    pcover.append(sum(acc.values()) / (b - a))
spk_time = Counter()
for s0, s1, spk in segs:
    spk_time[spk] += s1 - s0

both = [i for i in range(len(units)) if vlab[i] and plab[i]]
print(f"unidades: {len(units)} | con V#: {sum(v is not None for v in vlab)} | con pyannote: "
      f"{sum(p is not None for p in plab)} | ambas: {len(both)}")
print(f"ARI V# vs pyannote (unidades con ambas): {adjusted_rand_score([vlab[i] for i in both], [plab[i] for i in both]):.3f}")

names = json.loads((W / "names.json").read_text())
d = np.load(W / "smoke/scan.npz")
starts = np.array([u[0] for u in units])
ui = np.clip(np.searchsorted(starts, d["times"], side="right") - 1, 0, len(units) - 1)
onscreen = defaultdict(set)
for u, c in zip(ui, d["cid"]):
    if c >= 0:
        onscreen[int(u)].add(names[str(int(c))])
base = Counter(n for u in range(len(units)) for n in onscreen.get(u, ()))
lips = defaultdict(dict)
for f in glob.glob(str(W / "smoke/asd_[0-9].jsonl")):
    for l in open(f):
        r = json.loads(l)
        if r.get("cid") is not None and r["cid"] >= 0 and r["mouth_std"] >= 0.03:
            n = names[str(r["cid"])]
            lips[r["unit"]][n] = max(lips[r["unit"]].get(n, 0), r["mouth_std"])

print("\npyannote → V# (pureza) · en pantalla (lift) · labios")
rows = {}
for spk, tsec in spk_time.most_common():
    us = [i for i in range(len(units)) if plab[i] == spk]
    if not us:
        continue
    vc = Counter(vlab[i] for i in us if vlab[i])
    nv = sum(vc.values())
    os_ = Counter(n for u in us for n in onscreen.get(u, ()))
    lift = sorted(((n, (k / len(us)) / (base[n] / len(units))) for n, k in os_.items() if k >= 5),
                  key=lambda t: -t[1])[:2]
    lp = Counter(max(lips[u], key=lips[u].get) for u in us if lips.get(u))
    rows[spk] = {"time_s": round(tsec), "units": len(us),
                 "voices": {f"{v} {VN[v]}": round(k / nv, 2) for v, k in vc.most_common(3)} if nv else {},
                 "onscreen_lift": [(n, round(x, 1)) for n, x in lift],
                 "lips": {n: round(k / len(us), 2) for n, k in lp.most_common(2)}}
    r = rows[spk]
    print(f"{spk} {r['time_s']:5d}s {len(us):4d}u | {r['voices']} | pantalla {r['onscreen_lift']} | labios {r['lips']}")

print("\nV# → pyannote (cómo se reparte cada voz)")
for v in VN:
    us = [i for i in range(len(units)) if vlab[i] == v and plab[i]]
    pc = Counter(plab[i] for i in us)
    print(f"{v:4s} {VN[v]:16s} {len(us):4d}u → " + ", ".join(f"{s} {k / len(us):.2f}" for s, k in pc.most_common(3)))
(D / "spider_compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
