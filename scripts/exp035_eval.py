"""EXP-035: evaluación (ver pre-registro en EXPERIMENT_LOG).

--part a   narrador sintético con estructura de documental (docmix conf; dev solo como verificación del generador)
--part b   GT humano en BBC: etiquetas exportadas de la página de anotación (ArtifactData, out_dir) en
           data/gatebench/exp035b/labels/labels/*.json. Con más de un anotador: mayoría por clip; empates y
           "no sé" se excluyen y se reportan.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp034_eval import narrator_rows, narrator_summary, paired  # noqa: E402
from exp034_items import G  # noqa: E402

KEYS = ["W", "A0.3&W", "S&W", "I&W"]
CANDS = ["S&W", "I&W"]
SPEECH = {"narrador", "voz_musica", "otra_voz"}


def part_a():
    nar = narrator_rows("conf", KEYS, sub="docmix")
    rep = {"summary": narrator_summary(nar, KEYS)}
    many = [r for r in nar.values() if r["k_true"] >= 2]
    fs_w = float(np.mean([r["W"]["single"] for r in many]))
    for g in CANDS:
        d = [int(r[g]["single"]) - int(r["W"]["single"]) for r in nar.values() if r["k_true"] == 1]
        c1 = paired(d)
        fs = float(np.mean([r[g]["single"] for r in many]))
        rep[g] = {"c1_single_minus_W": c1, "c1_pass": bool(c1["z"] is not None and c1["z"] > 2),
                  "c2_false_single": fs, "c2_false_single_W": fs_w, "c2_pass": bool(fs <= fs_w + 0.05)}
    rep["gate_quality"] = {k: {"fsr": float(np.mean([r[k]["fsr"] for r in nar.values() if r[k]["fsr"] is not None])),
                               "recall": float(np.mean([r[k]["recall"] for r in nar.values()]))} for k in KEYS}
    Path("results/exp035a.json").write_text(json.dumps(rep, indent=1))
    Path("results/exp035a_rows.json").write_text(json.dumps(nar, indent=1))
    print(json.dumps({k: v for k, v in rep.items()}, indent=1))


def labels():
    by_clip = {}
    for f in sorted((G / "exp035b" / "labels").glob("**/*.json")):
        d = json.loads(f.read_text())
        d = d.get("data", d)
        if d.get("clip") and d.get("label"):
            by_clip.setdefault(d["clip"], []).append(d["label"])
    out, excluded = {}, Counter()
    for c, ls in by_clip.items():
        top = Counter(ls).most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            excluded["empate"] += 1
        elif top[0][0] == "nose":
            excluded["nose"] += 1
        else:
            out[c] = top[0][0]
    return out, excluded, max((len(v) for v in by_clip.values()), default=0)


def estimates(rows, eps):
    """Métricas ponderadas por estrato, restringidas a los episodios `eps` (con repetición, para bootstrap)."""
    out = {}
    sel = [r for e in eps for r in rows if r["ep"] == e]
    w = np.array([r["weight"] for r in sel])
    y = np.array([r["y"] for r in sel], bool)
    other = np.array([r["label"] == "otra_voz" for r in sel])
    for k in KEYS:
        g = np.array([r["gates"][k] for r in sel], bool)
        out[k] = {"fsr": float((w * g * ~y).sum() / max((w * ~y).sum(), 1e-9)),
                  "recall": float((w * g * y).sum() / max((w * y).sum(), 1e-9))}
    out["other_voice_frac"] = float((w * other).sum() / max((w * y).sum(), 1e-9))
    out["speech_frac"] = float((w * y).sum() / w.sum())
    return out


def part_b():
    lab, excluded, max_annot = labels()
    sample = json.loads((G / "exp035b" / "sample.json").read_text())
    rows = [dict(r, label=lab[r["clip"]], y=lab[r["clip"]] in SPEECH) for r in sample if r["clip"] in lab]
    eps = sorted({r["ep"] for r in sample})
    est = estimates(rows, eps)
    rng = np.random.default_rng(0)
    boot = [estimates(rows, list(rng.choice(eps, len(eps), replace=True))) for _ in range(2000)]
    rep = {"n_labeled": len(rows), "n_sample": len(sample), "excluded": dict(excluded), "max_annotators_per_clip": max_annot,
           "label_counts": dict(Counter(r["label"] for r in rows)), "estimates": est}
    se_other = float(np.std([b["other_voice_frac"] for b in boot], ddof=1))
    for g in CANDS:
        d = np.array([b["W"]["fsr"] - b[g]["fsr"] for b in boot])
        diff = est["W"]["fsr"] - est[g]["fsr"]
        se = float(d.std(ddof=1))
        rep[g] = {"c1_fsr_W_minus_G": {"mean": diff, "se": se, "z": diff / se if se else None},
                  "c1_pass": bool(se and diff / se > 2), "c2_recall": est[g]["recall"], "c2_pass": bool(est[g]["recall"] >= 0.80),
                  "c3_other_voice_frac": est["other_voice_frac"], "c3_se": se_other, "c3_pass": bool(est["other_voice_frac"] < 0.05)}
        rep[g]["pass_b"] = bool(rep[g]["c1_pass"] and rep[g]["c2_pass"] and rep[g]["c3_pass"])
    Path("results/exp035b.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--part", choices=["a", "b"], required=True)
    part_a() if ap.parse_args().part == "a" else part_b()
