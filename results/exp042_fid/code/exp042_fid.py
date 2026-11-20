"""EXP-042-FID (exploratorio) — anclaje de identidades por rostro para la película.

Fase 1 (scan):  1 fps → detección + embedding ArcFace (buffalo_l) de TODOS los rostros.
Fase 2 (cluster): clustering jerárquico de embeddings (coseno) → identidades de rostro.
Fase 3 (voice):  cruce de cada clúster con los grupos de voz (turnos de ASR) → nombre.
Fase 4 (export): CSV de intervalos por personaje + resumen para la demo.

Uso:
  python exp042_fid.py scan  --video X.mp4 --work exp042/          # ~8-15 min CPU
  python exp042_fid.py cluster --work exp042/ [--thr 0.45]
  python exp042_fid.py voice   --work exp042/ --run data/films_runs/Spider_Man
  python exp042_fid.py export  --work exp042/ --out exp042/intervals
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

app = None


def get_app():
    global app
    if app is None:
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
    return app


def scan(args):
    out = Path(args.work)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(fps / args.fps))
    if args.t0 > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, args.t0 * 1000.0)
    fa = get_app()
    times, boxes, embs, scores = [], [], [], []
    i = 0
    t0 = time.time()
    while True:
        ok = cap.grab()
        if not ok:
            break
        t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if args.t1 and t >= args.t1:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            h, w = frame.shape[:2]
            if max(h, w) > 1280:
                s = 1280 / max(h, w)
                frame = cv2.resize(frame, (int(w * s), int(h * s)))
            faces = fa.get(frame)
            for f in faces:
                x1, y1, x2, y2 = [float(v) for v in f.bbox]
                if f.det_score < 0.5:
                    continue
                e = f.normed_embedding.astype(np.float32)
                times.append(round(t, 2))
                boxes.append([x1, y1, x2, y2])
                embs.append(e)
                scores.append(float(f.det_score))
        i += 1
    cap.release()
    np.savez_compressed(out / f"scan_shard_{args.shard}.npz" if args.shard else out / "scan.npz",
                        times=np.array(times, dtype=np.float32),
                        boxes=np.array(boxes, dtype=np.float32),
                        embs=np.stack(embs) if embs else np.zeros((0, 512), np.float32),
                        scores=np.array(scores, dtype=np.float32))
    print(f"[fid] {len(times)} rostros en {time.time()-t0:.0f}s → {out/'scan.npz'}", flush=True)


def cluster(args):
    out = Path(args.work)
    d = np.load(out / "scan.npz")
    embs, times = d["embs"], d["times"]
    if not len(embs):
        print("[fid] sin rostros")
        return
    sims = embs @ embs.T
    dist = np.clip(1.0 - sims, 0.0, 2.0)
    np.fill_diagonal(dist, 0.0)
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    Z = linkage(squareform(dist, checks=False), method="average")
    labels = fcluster(Z, t=args.thr, criterion="distance")
    counts = Counter(labels.tolist())
    keep = {l for l, c in counts.items() if c >= args.min_frames}
    ids = np.array([l if l in keep else -1 for l in labels.tolist()])
    np.savez_compressed(out / "scan.npz", **{k: d[k] for k in d.files}, cid=ids.astype(np.int32))
    summary = []
    for l in sorted(keep):
        m = ids == l
        dur = float(times[m].max() - times[m].min())
        summary.append({"cid": int(l), "frames": int(m.sum()),
                        "t0": float(times[m].min()), "t1": float(times[m].max()),
                        "coverage_s": round(dur, 1)})
    summary.sort(key=lambda x: -x["frames"])
    (out / "clusters.json").write_text(json.dumps(summary, indent=1))
    print(f"[fid] {len(keep)} clústeres ≥{args.min_frames} rostros (de {len(embs)}) → clusters.json", flush=True)
    for s in summary[:12]:
        print("   ", s, flush=True)


def _speaking_intervals(run: Path):
    """Grupos de voz desde el run: lista [(v, [(a,b), ...])] en segundos."""
    state = json.loads((run / "work/state.json").read_text())
    segs = state.get("asr_segments") or []
    # formato esperado: (a, b, texto, voz) o dict; detectar por longitud/tipo
    by_voice = defaultdict(list)
    for s in segs:
        if isinstance(s, dict):
            a, b, v = s.get("a"), s.get("b"), s.get("voice") or s.get("speaker")
        else:
            a, b = s[0], s[1]
            v = s[3] if len(s) > 3 else None
        if v is None or a is None:
            continue
        by_voice[str(v)].append((float(a), float(b)))
    return {k: sorted(v) for k, v in by_voice.items()}


def _overlap(interval_list, t0, t1):
    tot = 0.0
    for a, b in interval_list:
        tot += max(0.0, min(b, t1) - max(a, t0))
    return tot


def voice(args):
    out = Path(args.work)
    d = np.load(out / "scan.npz")
    times, cid = d["times"], d["cid"]
    voices = _speaking_intervals(Path(args.run))
    res = {"voices": {}, "clusters": {}}
    for v, ivs in voices.items():
        res["voices"][v] = {"speech_s": round(sum(b - a for a, b in ivs), 1)}
    for c in sorted(set(int(x) for x in cid if x >= 0)):
        m = cid == c
        ts = times[m]
        # intervalos del clúster (fusión de huecos <= gap)
        ivs = []
        cur = [ts[0], ts[0]]
        for t in ts[1:]:
            if t - cur[1] <= args.gap:
                cur[1] = t
            else:
                ivs.append(tuple(cur))
                cur = [t, t]
        ivs.append(tuple(cur))
        ov = {v: round(_overlap(voices[v], a, b), 1) for v in voices for a, b in ivs}
        res["clusters"][c] = {"intervals": [[round(a, 1), round(b, 1)] for a, b in ivs],
                              "speech_overlap_s": ov}
    (out / "voice_cross.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"[fid] cruce con {len(voices)} grupos de voz → voice_cross.json", flush=True)
    for c, info in sorted(res["clusters"].items(), key=lambda kv: -sum(kv[1]["speech_overlap_s"].values()))[:10]:
        top = sorted(info["speech_overlap_s"].items(), key=lambda kv: -kv[1])[:3]
        print(f"   cid {c}: {top}", flush=True)


def export(args):
    out = Path(args.work)
    d = np.load(out / "scan.npz")
    times, boxes, cid = d["times"], d["boxes"], d["cid"]
    vcp = out / "voice_cross.json"
    vc = json.loads(vcp.read_text()) if vcp.exists() else {}
    names = json.loads(Path(args.names).read_text()) if args.names else {}
    odir = Path(args.out)
    odir.mkdir(parents=True, exist_ok=True)
    for c in sorted(set(int(x) for x in cid if x >= 0)):
        m = cid == c
        ts = times[m]
        ivs, cur = [], [ts[0], ts[0]]
        for t in ts[1:]:
            if t - cur[1] <= args.gap:
                cur[1] = t
            else:
                ivs.append(tuple(cur)); cur = [t, t]
        ivs.append(tuple(cur))
        name = names.get(str(c), f"face_{c}")
        hms = lambda s: f"{int(s//3600):02d}:{int(s%3600//60):02d}:{int(s%60):02d}"
        csvp = odir / f"{name}.csv"
        csvp.write_text("inicio_hms,fin_hms,inicio_s,fin_s,duracion_s\n" + "".join(
            f"{hms(a)},{hms(b)},{a:.1f},{b:.1f},{b-a:.1f}\n" for a, b in ivs))
        print(f"[fid] {csvp} ({len(ivs)} intervalos)", flush=True)


def names_cmd(args):
    """Nombra clústeres con menciones del registro en el diálogo que ocurre
    mientras el rostro está en pantalla (regla F3: nombre solo si está en ASR)."""
    out = Path(args.work)
    d = np.load(out / "scan.npz")
    times, cid = d["times"], d["cid"]
    state = json.loads(Path(args.state).read_text())
    segs = state.get("asr_segments") or []
    reg = {}
    for line in Path(args.registry).read_text().splitlines():
        line = line.strip()
        if " - " in line:
            reg[line.split(" - ")[0].strip().lower()] = line.split(" - ")[0].strip()
    res = {}
    for c in sorted(set(int(x) for x in cid if x >= 0)):
        m = cid == c
        ts = np.sort(times[m])
        ivs, cur = [], [ts[0], ts[0]]
        for t in ts[1:]:
            if t - cur[1] <= args.gap:
                cur[1] = t
            else:
                ivs.append(tuple(cur)); cur = [t, t]
        ivs.append(tuple(cur))
        counts = Counter()
        for a, b, *rest in segs:
            if not rest:
                continue
            onscreen = sum(max(0.0, min(float(b), e) - max(float(a), s0)) for s0, e in ivs)
            if onscreen <= 0:
                continue
            text = (rest[0] or "").lower() if isinstance(rest[0], str) else ""
            for k in reg:
                if k in text:
                    counts[reg[k]] += float(min(onscreen, float(b) - float(a)))
        res[str(c)] = {"intervals": [[float(round(float(s0), 1)), float(round(float(e), 1))] for s0, e in ivs],
                       "mentions_s": dict(sorted(counts.items(), key=lambda kv: -kv[1])[:5])}
    (out / "names.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for c, info in sorted(res.items(), key=lambda kv: -sum(kv[1]["mentions_s"].values())):
        print(f"   cid {c} [{info['t0']}-{info['t1']}s]: {info['mentions_s']}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan"); p.add_argument("--video", required=True); p.add_argument("--work", default="exp042"); p.add_argument("--fps", type=float, default=1.0); p.add_argument("--t0", type=float, default=0.0); p.add_argument("--t1", type=float, default=0.0); p.add_argument("--shard", type=int, default=0)
    p = sub.add_parser("cluster"); p.add_argument("--work", default="exp042"); p.add_argument("--thr", type=float, default=0.45); p.add_argument("--min-frames", type=int, default=20)
    p = sub.add_parser("voice"); p.add_argument("--work", default="exp042"); p.add_argument("--run", required=True); p.add_argument("--gap", type=float, default=5.0)
    p = sub.add_parser("export"); p.add_argument("--work", default="exp042"); p.add_argument("--out", required=True); p.add_argument("--names", default=""); p.add_argument("--gap", type=float, default=5.0)
    p = sub.add_parser("names"); p.add_argument("--work", default="exp042"); p.add_argument("--state", required=True); p.add_argument("--registry", required=True); p.add_argument("--gap", type=float, default=5.0)
    args = ap.parse_args()
    {"scan": scan, "cluster": cluster, "voice": voice, "export": export, "names": names_cmd}[args.cmd](args)


if __name__ == "__main__":
    main()
