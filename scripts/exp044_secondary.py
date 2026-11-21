"""EXP-044-TURN: métricas secundarias (sin criterio) a partir de la salida de eval_ami.py --turns-source pyannote.

Entradas: <results>.json y <results>.aux.npz de eval_ami.py, RTTM de pyannote, GT de AMI, señales (unit_times).
Por reunión evaluada:
  frac_labeled_C/P, mediana/media/fracción de ceros del score JSD de C y P
  ARI de las etiquetas de unidad (C y P) vs hablante dominante GT (dominant() de EXP-020) y |K_eff − K_true|
  DER (collar 0,25 s) de pyannote vs GT de AMI
  F1 de fronteras de tópico (±1 unidad) de cava_voice, contiguous, cava_turns (C) y cava_turns_P vs GT
  nº de tópicos predichos y retornos de cada sistema
Correr con dia-venv (pyannote.metrics): python -I scripts/exp044_secondary.py --results R.json --out S.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

D = Path("data/ami")


def rttm(path):
    segs = []
    for line in Path(path).read_text().splitlines():
        p = line.split()
        if p and p[0] == "SPEAKER":
            segs.append((float(p[3]), float(p[3]) + float(p[4]), p[7]))
    return segs


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
    return float(adjusted_rand_score([dom[i] for i in idx], lab[idx])) if len(idx) > 5 else None


def k_eff(vid, thr=0.05):
    v = vid[vid >= 0]
    if not len(v):
        return 0
    _, c = np.unique(v, return_counts=True)
    return int((c / len(v) >= thr).sum())


def boundaries(lab):
    lab = np.asarray(lab)
    return [k for k in range(len(lab) - 1) if lab[k] != lab[k + 1]]


def f1_tol(pred, ref, tol=1):
    if not pred and not ref:
        return 1.0
    used, tp = set(), 0
    for p in pred:
        c = [r for r in ref if abs(r - p) <= tol and r not in used]
        if c:
            used.add(min(c, key=lambda r: abs(r - p)))
            tp += 1
    pr, rc = tp / max(1, len(pred)), tp / max(1, len(ref))
    return 0.0 if pr + rc == 0 else 2 * pr * rc / (pr + rc)


def runs_returns(lab):
    lab = np.asarray(lab)
    runs = 1 + len(boundaries(lab))
    return len(set(lab.tolist())), runs - len(set(lab.tolist()))


def paired(a, b):
    d = np.array([x - y for x, y in zip(a, b)])
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": int(len(d))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pyannote-dir", default="data/ami/pyannote")
    ap.add_argument("--no-der", action="store_true")
    args = ap.parse_args()
    rep = json.loads(Path(args.results).read_text())
    aux = np.load(Path(args.results).with_suffix(".aux.npz"))
    if not args.no_der:
        from pyannote.core import Annotation, Segment
        from pyannote.metrics.diarization import DiarizationErrorRate

        def ann(segs):
            a = Annotation()
            for s0, s1, spk in segs:
                a[Segment(s0, s1)] = str(spk)
            return a
    rows = {}
    for m, rb in rep["per_meeting_b"].items():
        meta = json.loads((D / "signals" / f"{m}.json").read_text())
        gt = json.loads((D / "gt" / f"{m}.json").read_text())
        vid_c, vid_p = aux[f"{m}/vid_C"], aux[f"{m}/vid_P"]
        sc_c, sc_p = aux[f"{m}/score_C"], aux[f"{m}/score_P"]
        n = len(vid_c)
        units = meta["unit_times"][:n]
        dom = dominant(units, gt["speech"])
        lab = [s for s in dom if s]
        _, cnt = np.unique(lab, return_counts=True) if lab else ([], [])
        k_true = int((np.asarray(cnt) / max(1, len(lab)) >= 0.05).sum())
        r = {"frac_labeled_C": rb["frac_labeled_C"], "frac_labeled_P": rb["frac_labeled_P"],
             "score_median_C": float(np.median(sc_c)), "score_median_P": float(np.median(sc_p)),
             "score_mean_C": float(sc_c.mean()), "score_mean_P": float(sc_p.mean()),
             "score_frac_zero_C": float((sc_c == 0).mean()), "score_frac_zero_P": float((sc_p == 0).mean()),
             "ari_C": ari(dom, vid_c), "ari_P": ari(dom, vid_p), "k_true": k_true,
             "kerr_C": abs(k_eff(vid_c) - k_true), "kerr_P": abs(k_eff(vid_p) - k_true)}
        if not args.no_der:
            r["der_P"] = float(DiarizationErrorRate(collar=0.25)(
                ann([(a, b, s) for s, a, b in gt["speech"]]),
                ann(rttm(Path(args.pyannote_dir) / f"{m}.Mix-Headset.rttm"))))
        top = []
        for u0, u1 in units:
            mid = (u0 + u1) / 2
            top.append(next((i for i, t in enumerate(gt["topics"]) if t["t0"] <= mid <= t["t1"]), -1))
        ref_b = boundaries(top)
        for k in ("cava_voice", "contiguous", "cava_turns", "cava_turns_P"):
            lb = aux[f"{m}/labels_{k}"]
            r[f"f1_{k}"] = f1_tol(boundaries(lb), ref_b)
            r[f"n_topics_{k}"], r[f"returns_{k}"] = runs_returns(lb)
        r["n_topics_gt"] = len({t["label"] for t in gt["topics"]})
        r["returns_gt"] = len(gt["topics"]) - r["n_topics_gt"]
        rows[m] = r
    summ = {}
    for k in ("frac_labeled_C", "frac_labeled_P", "score_median_C", "score_median_P", "score_frac_zero_C",
              "score_frac_zero_P", "ari_C", "ari_P", "kerr_C", "kerr_P", "der_P", "f1_cava_voice",
              "f1_contiguous", "f1_cava_turns", "f1_cava_turns_P", "n_topics_cava_turns", "n_topics_cava_turns_P",
              "returns_cava_turns", "returns_cava_turns_P", "n_topics_gt", "returns_gt"):
        v = [r[k] for r in rows.values() if r.get(k) is not None]
        if v:
            summ[k] = round(float(np.mean(v)), 4)
    if all(r["ari_P"] is not None and r["ari_C"] is not None for r in rows.values()):
        summ["ari_P_minus_C"] = paired([r["ari_P"] for r in rows.values()], [r["ari_C"] for r in rows.values()])
    summ["f1_P_minus_C"] = paired([r["f1_cava_turns_P"] for r in rows.values()],
                                  [r["f1_cava_turns"] for r in rows.values()])
    Path(args.out).write_text(json.dumps({"summary": summ, "per_meeting": rows}, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
