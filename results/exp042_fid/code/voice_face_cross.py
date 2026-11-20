"""EXP-042-FID: cruce de grupos de voz V1..V8 (WavLM-sv) con identidades de rostro.

1. Reconstruye la voz por unidad de 5 s igual que topicagg.pipeline.speakers()
   (habla ASR >= 50 %, single_speaker, identities(ward, bic)) y la valida contra
   los `speakers` guardados en topic_map.json.
2. Presencia de rostro por unidad desde scan.npz (1 fps, cid de cluster).
3. Para cada voz V: P(rostro c en pantalla | V habla) y lift = P(c|V) / P(c|habla).
   Asignación 1:1 por Hungarian sobre el lift (con soporte mínimo).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

ap = argparse.ArgumentParser()
ap.add_argument("--run", default="/data/tesis-cava/CAVA_minimo/outputs/Spider_Man")
ap.add_argument("--cava", default="/data/tesis-cava/CAVA_minimo")
ap.add_argument("--work", default="/data/tesis-cava/exp036/fid/smoke")
ap.add_argument("--names", default="/data/tesis-cava/exp036/fid/names.json")
ap.add_argument("--min-units", type=int, default=8)
args = ap.parse_args()

sys.path.insert(0, args.cava)
sys.path.insert(0, f"{args.cava}/scripts")
from eval_voice_identities import identities  # noqa: E402
from topicagg.speaker import single_speaker  # noqa: E402

run = Path(args.run)
state = json.loads((run / "work/state.json").read_text())
units = state["units"]
n = len(units)
x = np.load(run / "work/speaker_xvec.npy")
speech = np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in state["asr_segments"])
                   >= 0.5 * (u1 - u0) for u0, u1 in units])
vid = np.full(n, -1)
if single_speaker(x, speech):
    vid[speech] = 1
else:
    vid[speech] = identities(x[speech], "ward", k_rule="bic")

np.save(Path(args.work) / "voice_per_unit.npy", vid)

# validación contra topic_map
doc = json.loads((run / "topic_map.json").read_text())
agree = tot = 0
for t in doc["levels"]["default"]["topics"]:
    saved = t.get("speakers") or []
    if not saved:
        continue
    vs = [f"V{int(v)}" for v in vid[t["shots"]] if v >= 0]
    if not vs:
        continue
    tot += 1
    agree += Counter(vs).most_common(1)[0][0] == saved[0]["id"]
print(f"voces reconstruidas: {sorted(set(int(v) for v in vid if v >= 0))}; "
      f"coincidencia con topic_map (voz dominante por tópico): {agree}/{tot}")

# rostros por unidad
d = np.load(Path(args.work) / "scan.npz")
times, cid = d["times"], d["cid"]
starts = np.array([u[0] for u in units])
uidx = np.clip(np.searchsorted(starts, times, side="right") - 1, 0, n - 1)
faces = sorted(set(int(c) for c in cid if c >= 0))
F = np.zeros((n, len(faces)), bool)
fpos = {c: i for i, c in enumerate(faces)}
for u, c in zip(uidx, cid):
    if c >= 0:
        F[u, fpos[int(c)]] = True

names = json.loads(Path(args.names).read_text()) if Path(args.names).exists() else {}
fname = lambda c: names.get(str(c), f"face_{c}")
labs = [fname(c) for c in faces]
uniq = sorted(set(labs))
F = np.stack([F[:, [i for i, l in enumerate(labs) if l == u]].any(1) for u in uniq], 1)
faces = uniq
fname = lambda c: c
voices = sorted(set(int(v) for v in vid if v >= 0))
base = F[speech].mean(0) + 1e-9
P = np.zeros((len(voices), len(faces)))
S = np.zeros_like(P)
res = {"validation": {"agree": agree, "topics": tot}, "voices": {}}
for i, v in enumerate(voices):
    m = vid == v
    P[i] = F[m].mean(0)
    S[i] = F[m].sum(0)
    lift = P[i] / base
    top = np.argsort(-P[i])[:5]
    res["voices"][f"V{v}"] = {
        "units": int(m.sum()), "speech_s": round(float(m.sum() * 5), 0),
        "faces_on_screen_rate": round(float(F[m].any(1).mean()), 3),
        "top": [{"face": fname(faces[j]), "p": round(float(P[i, j]), 3),
                 "lift": round(float(lift[j]), 2), "units": int(S[i, j])} for j in top]}

# Regla: candidato si p >= 0.15, lift >= 2 y soporte; ambiguo si hay >1 candidato.
L = P / base
assign = {}
for i, v in enumerate(voices):
    cand = [j for j in range(len(faces))
            if P[i, j] >= 0.15 and L[i, j] >= 2.0 and S[i, j] >= args.min_units]
    cand.sort(key=lambda j: -P[i, j] * np.log(L[i, j]))
    j = cand[0] if cand else int(np.argmax(P[i]))
    assign[f"V{v}"] = {"face": fname(faces[j]) if cand else None,
                       "ambiguous_with": [fname(faces[k]) for k in cand[1:]],
                       "lift": round(float(L[i, j]), 2), "p": round(float(P[i, j]), 3),
                       "units": int(S[i, j])}
res["assignment"] = assign
Path(args.work, "voice_face_cross.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))

print(f"\n{'voz':4} {'unid':>5} {'%rostro':>7}  top rostros (p, lift)")
for v, info in res["voices"].items():
    tops = ", ".join(f"{t['face']} ({t['p']:.2f}, x{t['lift']})" for t in info["top"][:3])
    print(f"{v:4} {info['units']:5d} {info['faces_on_screen_rate']:7.2f}  {tops}")
print("\nAsignación (p ≥ 0.15, lift ≥ 2, soporte ≥ %d unidades):" % args.min_units)
for v, a in assign.items():
    amb = f"  [ambigua con {', '.join(a['ambiguous_with'])}]" if a["ambiguous_with"] else ""
    print(f"  {v} -> {a['face'] or '(sin asignar)'}  lift {a['lift']}  p {a['p']}  n {a['units']}{amb}")
