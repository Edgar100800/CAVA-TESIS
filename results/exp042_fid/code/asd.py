"""EXP-042-FID: hablante activo por movimiento de labios.

Para cada tramo de habla (unidad de 5 s con voz V#), lee frames a --fps, detecta
rostros, los asigna al centroide de clúster más cercano (coseno >= --thr) y mide la
apertura de boca (landmarks 2d106, puntos 52-71: alto/ancho). La desviación estándar
de la apertura dentro del tramo es la actividad de labios de ese rostro.

Salida: JSONL con {unit, voice, cid, n, mouth_std, mouth_mean}.
"""
import argparse
import json
import os
import time

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--video", required=True)
ap.add_argument("--jobs", required=True, help="JSON: [[unit, t0, t1, voice], ...]")
ap.add_argument("--centroids", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--fps", type=float, default=5.0)
ap.add_argument("--thr", type=float, default=0.40)
args = ap.parse_args()

from insightface.app import FaceAnalysis  # noqa: E402

app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition", "landmark_2d_106"],
                   providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
app.prepare(ctx_id=0, det_size=(640, 640))
print("providers:", app.models["detection"].session.get_providers(), flush=True)

c = np.load(args.centroids)
cids, C = c["cids"], c["C"]
jobs = json.load(open(args.jobs))
cap = cv2.VideoCapture(args.video)
done = set()
if os.path.exists(args.out):
    for line in open(args.out):
        done.add(json.loads(line)["unit"])
fh = open(args.out, "a")
t_start = time.time()
for k, (u, t0, t1, v) in enumerate(jobs):
    if u in done:
        continue
    per = {}
    t = t0
    while t < t1:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, fr = cap.read()
        t += 1.0 / args.fps
        if not ok:
            continue
        for f in app.get(fr):
            if f.det_score < 0.5 or getattr(f, "landmark_2d_106", None) is None:
                continue
            s = C @ f.normed_embedding
            j = int(np.argmax(s))
            cid = int(cids[j]) if s[j] >= args.thr else -1
            m = f.landmark_2d_106[52:72]
            w = m[:, 0].max() - m[:, 0].min()
            if w <= 1:
                continue
            per.setdefault(cid, []).append(float((m[:, 1].max() - m[:, 1].min()) / w))
    for cid, a in per.items():
        if len(a) >= 3:
            fh.write(json.dumps({"unit": u, "voice": v, "cid": cid, "n": len(a),
                                 "mouth_std": float(np.std(a)), "mouth_mean": float(np.mean(a))}) + "\n")
    if not per:
        fh.write(json.dumps({"unit": u, "voice": v, "cid": None, "n": 0}) + "\n")
    fh.flush()
    if k % 50 == 0:
        print(f"{k}/{len(jobs)} {time.time()-t_start:.0f}s", flush=True)
print("FIN", flush=True)
