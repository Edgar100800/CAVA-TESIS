"""EXP-043-DIA (exploratorio): nombra los hablantes pyannote de Spider-Man.

Por hablante, ponderando por duración de turno:
  labios  = rostro con mayor mouth_std (>= 0.03) en cada turno (asd_turn_*.jsonl, turnos >= 1 s)
  pantalla = lift de presencia del personaje durante sus turnos (scan.npz a 1 fps) frente a la película
Regla: labios si share >= 0.25 y >= 2x el segundo; si no, pantalla si lift >= 3 y p >= 0.30; si no, sin rostro.
"""
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

S = Path("/data/tesis-cava/exp036/dia/spider")
F = Path("/data/tesis-cava/exp036/fid")
names = json.loads((F / "names.json").read_text())
turns = json.loads((S / "turns_merged.json").read_text())
spk_dur = defaultdict(float)
for a, b, s in turns:
    spk_dur[s] += b - a

lips = defaultdict(lambda: defaultdict(float))
lips_tot = defaultdict(float)
best = {}
for f in glob.glob(str(S / "asd_turn_[0-9].jsonl")):
    for line in open(f):
        r = json.loads(line)
        if r.get("cid") is None or r["cid"] < 0 or r["mouth_std"] < 0.03:
            continue
        n = names[str(r["cid"])]
        k = r["unit"]
        if n not in best.get(k, {}) or r["mouth_std"] > best[k][n]:
            best.setdefault(k, {})[n] = r["mouth_std"]
for k, (a, b, s) in enumerate(turns):
    if b - a < 1.0:
        continue
    lips_tot[s] += b - a
    if k in best:
        lips[s][max(best[k], key=best[k].get)] += b - a

d = np.load(F / "smoke/scan.npz")
dur = float(d["times"].max()) + 1
present = defaultdict(set)
for t, c in zip(d["times"], d["cid"]):
    if c >= 0:
        present[int(t)].add(names[str(int(c))])
base = defaultdict(int)
for t, ns in present.items():
    for n in ns:
        base[n] += 1
on = defaultdict(lambda: defaultdict(int))
on_tot = defaultdict(int)
for a, b, s in turns:
    for t in range(int(np.ceil(a)), int(b) + 1):
        on_tot[s] += 1
        for n in present.get(t, ()):
            on[s][n] += 1

out = {}
for s in sorted(spk_dur, key=lambda x: -spk_dur[x]):
    lt = lips_tot[s] or 1
    lv = sorted(((n, v / lt) for n, v in lips[s].items()), key=lambda x: -x[1])
    ov = sorted(((n, k / on_tot[s], (k / on_tot[s]) / (base[n] / dur)) for n, k in on[s].items() if k >= 3),
                key=lambda x: -x[2])
    l1, l2 = (lv + [(None, 0), (None, 0)])[:2]
    if l1[0] and l1[1] >= 0.25 and l1[1] >= 2 * l2[1]:
        name, ev = l1[0], f"labios {l1[1]:.2f} (2.º {l2[1]:.2f})"
    elif ov and ov[0][2] >= 3 and ov[0][1] >= 0.30:
        name, ev = ov[0][0], f"pantalla p {ov[0][1]:.2f} lift {ov[0][2]:.1f}"
    else:
        name, ev = None, "sin evidencia"
    out[s] = {"dur_s": round(spk_dur[s]), "auto": name, "evidence": ev,
              "lips": [(n, round(v, 2)) for n, v in lv[:3]],
              "onscreen": [(n, round(p, 2), round(x, 1)) for n, p, x in ov[:3]]}
    print(f"{s} {spk_dur[s]:6.0f}s → {str(name):26s} [{ev}]  labios {out[s]['lips'][:2]}  pantalla {out[s]['onscreen'][:2]}")
(S / "speaker_names_auto.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
