"""EXP-025/026: criterios pre-registrados a partir de los JSON de eval_bbc.py (desarrollo y confirmación)."""
import json
import sys

import numpy as np


def paired(d):
    d = np.asarray(d, float)
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d),
            "z": round(float(d.mean() / se), 2) if se > 0 else None}


dev, conf = (json.load(open(f))["per_episode"] for f in sys.argv[1:3])
pstar = max((80, 90, 95), key=lambda q: np.mean([r[f"m_local_cava_p{q}"] for r in dev.values()]))
sfx = "" if pstar == 80 else f"_p{pstar}"
out = {"p_star": pstar, "dev_means": {q: round(float(np.mean([r[f"m_local_cava_p{q}"] for r in dev.values()])), 4)
                                      for q in (80, 90, 95)}}
R = list(conf.values())
cava = [r[f"m_local_cava_p{pstar}"] for r in R]
for b in ("contiguous", "fused"):
    best = [max(r[f"m_local_{b}"], r[f"m_local_{b}{sfx}"]) for r in R]
    out[f"c_vs_best_{b}"] = paired(np.array(cava) - best)
if pstar != 80:
    out["c_vs_cava_p80"] = paired(np.array(cava) - [r["m_local_cava_p80"] for r in R])
sigs = ("voice", "visual", "transcript", "vjudge")
out["coherence_pos"] = {k: int(sum(r[f"coh_cava_p{pstar}_{k}"] > 0 for r in R)) for k in sigs}
out["coherence_ok"] = all(v >= len(R) - 1 for v in out["coherence_pos"].values())
out["means_conf"] = {k: round(float(np.mean([r[k] for r in R])), 4) for k in R[0]
                     if k.startswith(("m_local_", "f1b_", "ceiling", "n_runs_cava", "n_runs_contig", "keff_"))}
ep26 = [r for e, r in (dev | conf).items() if e not in ("bbc_01", "bbc_02")]
out["exp026_err_base_minus_gate"] = paired([r["err_base"] - r["err_gate"] for r in ep26])
print(json.dumps(out, indent=1))
