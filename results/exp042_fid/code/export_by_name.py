"""CSV de intervalos por personaje (fusiona todos los clústeres con el mismo nombre)."""
import json, shutil
from collections import defaultdict
from pathlib import Path
import numpy as np
W = Path("/data/tesis-cava/exp036/fid")
names = json.loads((W / "names.json").read_text())
d = np.load(W / "smoke/scan.npz")
by = defaultdict(list)
for t, c in zip(d["times"], d["cid"]):
    if c >= 0 and str(int(c)) in names:
        by[names[str(int(c))]].append(float(t))
out = W / "smoke/intervals"
shutil.rmtree(out, ignore_errors=True); out.mkdir()
hms = lambda s: f"{int(s//3600):02d}:{int(s%3600//60):02d}:{int(s%60):02d}"
rows = []
for n, ts in by.items():
    ts = sorted(set(ts)); ivs, cur = [], [ts[0], ts[0]]
    for t in ts[1:]:
        if t - cur[1] <= 5.0: cur[1] = t
        else: ivs.append(cur); cur = [t, t]
    ivs.append(cur)
    (out / f"{n.replace(' ', '_').replace('(', '').replace(')', '')}.csv").write_text(
        "inicio_hms,fin_hms,inicio_s,fin_s,duracion_s\n" + "".join(
            f"{hms(a)},{hms(b)},{a:.1f},{b:.1f},{b-a+1:.1f}\n" for a, b in ivs))
    rows.append((sum(b - a + 1 for a, b in ivs), n, len(ivs), len(ts)))
for s, n, k, f in sorted(rows, reverse=True):
    print(f"{n:28s} {f:4d} rostros {k:4d} intervalos {s:7.0f} s")
