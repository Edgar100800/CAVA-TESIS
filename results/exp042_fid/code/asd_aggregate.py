"""Agrega asd_*.jsonl: hablante activo por tramo = rostro con mayor mouth_std
(>= --min-std); para cada voz V, distribución de hablantes activos."""
import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--work", default="/data/tesis-cava/exp036/fid/smoke")
ap.add_argument("--names", default="/data/tesis-cava/exp036/fid/names.json")
ap.add_argument("--min-std", type=float, default=0.04)
args = ap.parse_args()

names = json.loads(Path(args.names).read_text()) if Path(args.names).exists() else {}
cname = lambda c: names.get(str(c), f"face_{c}")
fname = lambda c: c if c is not None else "(nadie)"
units = defaultdict(list)
voice_of = {}
for f in sorted(glob.glob(f"{args.work}/asd_[0-9].jsonl")):
    for line in open(f):
        r = json.loads(line)
        voice_of[r["unit"]] = r["voice"]
        if r.get("cid") is not None and r["cid"] >= 0:
            units[r["unit"]].append(r)

by_voice = defaultdict(Counter)
n_voice = Counter(voice_of.values())
for u, v in voice_of.items():
    per = {}
    for r in units.get(u, []):
        if r["mouth_std"] >= args.min_std:
            k = cname(r["cid"]); per[k] = max(per.get(k, 0), r["mouth_std"])
    best = max(per, key=per.get) if per else None
    by_voice[v][best] += 1

res = {}
print(f"{'voz':4} {'tramos':>6}  hablante activo (proporción de tramos)")
for v in sorted(by_voice, key=lambda s: int(s[1:])):
    tot = n_voice[v]
    top = by_voice[v].most_common(5)
    res[v] = {"units": tot, "active": [{"face": fname(c), "share": round(k / tot, 3), "units": k}
                                       for c, k in top]}
    known = [(c, k) for c, k in top if c is not None]
    first, second = (known + [(None, 0), (None, 0)])[:2]
    verdict = fname(first[0]) if first[1] >= 0.15 * tot and first[1] >= 2 * max(second[1], 1) else "ambiguo"
    res[v]["assign"] = verdict
    print(f"{v:4} {tot:6d}  " + ", ".join(f"{fname(c)} {k/tot:.2f}" for c, k in top) + f"  => {verdict}")
Path(args.work, "asd_assignment.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
