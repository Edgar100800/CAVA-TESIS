"""EXP-026 criterio 2: no inferioridad del filtro de habla en AMI (ARI de identidades de voz frente al hablante dominante GT)."""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_bbc import voice_ids  # noqa: E402
from eval_voice_identities import dominant  # noqa: E402

D = Path("data/ami")
rows = {}
for m in Path(sys.argv[1]).read_text().split():
    fz, fj = D / "signals" / f"{m}.npz", D / "signals" / f"{m}.json"
    if not (fz.exists() and fj.exists()):
        continue
    x = np.load(fz)["voice"].astype(np.float32)
    meta = json.loads(fj.read_text())
    n = min(len(x), len(meta["unit_times"]))
    x = x[:n]
    gate = np.array([bool((t or "").strip()) for t in meta["asr_text"][:n]])
    dom = dominant(meta["unit_times"][:n], json.loads((D / "gt" / f"{m}.json").read_text())["speech"])
    r = {"gate_frac": float(gate.mean())}
    for name, kw in (("base", {}), ("gate", {"gate": gate})):
        lab = voice_ids(x, **kw)
        idx = [i for i in range(n) if dom[i] and lab[i] >= 0]
        r[f"ari_{name}"] = float(adjusted_rand_score([dom[i] for i in idx], [lab[i] for i in idx])) if idx else 0.0
    rows[m] = r
    print(m, {k: round(v, 3) for k, v in r.items()}, flush=True)
d = np.array([r["ari_gate"] - r["ari_base"] for r in rows.values()])
rep = {"n": len(d), "ari_base": float(np.mean([r["ari_base"] for r in rows.values()])),
       "ari_gate": float(np.mean([r["ari_gate"] for r in rows.values()])),
       "gate_minus_base": {"mean": float(d.mean()), "se": float(d.std(ddof=1) / np.sqrt(len(d)))},
       "non_inferior": bool(d.mean() > -0.02), "per_meeting": rows}
Path(sys.argv[2]).write_text(json.dumps(rep, indent=1))
print(json.dumps({k: v for k, v in rep.items() if k != "per_meeting"}, indent=1))
