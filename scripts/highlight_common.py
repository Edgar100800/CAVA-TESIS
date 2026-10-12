"""Común a EXP-037 (reglas fijas de highlights) y EXP-038 (política aprendida): carga de corridas v1, recompensas de
importancia (TVSum, SumMe), presupuesto en unidades y bases uniforme / al azar sobre la rejilla del mapa."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rewards_tvsum import importance, per_second, random_spans, reward, uniform_spans  # noqa: E402,F401

SUMME = Path("/home/edgar.chambilla/Tesis/SegLoop/data/summe/GT")
TVSUM_INFO = Path("/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/ydata-tvsum50-v1_1/data/ydata-tvsum50-info.tsv")
UNIT = 5.0
FRAC = 0.10


def tvsum_z():
    imp, _ = importance()
    return lambda vid, D: per_second(imp[vid], D) if vid in imp else None


def summe_z():
    from scipy.io import loadmat

    def z(vid, D):
        f = SUMME / f"{vid}.mat"
        if not f.exists():
            return None
        m = loadmat(f)
        return per_second(np.asarray(m["gt_score"], float).ravel(), float(m["video_duration"].ravel()[0]))
    return z


def tvsum_categories():
    rows = [l.split("\t") for l in TVSUM_INFO.read_text().splitlines()[1:]]
    return {r[1]: r[0] for r in rows}


def load_run(run: Path):
    doc = json.loads((run / "topic_map.json").read_text())
    units = [tuple(u) for u in doc["unit_times"]]
    sig = np.load(run / "work" / "signals.npz")
    topics = [t for t in doc["levels"]["default"]["topics"] if not t["flags"]["no_topic"]]
    clips = [json.loads(l) for l in (run / "clips.jsonl").read_text().splitlines()]
    st = json.loads((run / "work" / "state.json").read_text())
    return {"vid": run.name, "D": float(doc["duration_s"]), "units": units, "topics": topics, "doc": doc,
            "visual": np.asarray(sig["visual"][:len(units)], np.float32), "asr": st.get("asr", [""] * len(units)),
            "h0": [(c["t0"], c["t1"]) for c in clips if c["version"] == "highlights10pct"]}


def budget_units(D: float) -> int:
    return max(1, int(math.floor(FRAC * D / UNIT)))


def unit_spans(units, idx):
    """Unidades elegidas → tramos (contiguas se funden)."""
    out = []
    for i in sorted(set(int(i) for i in idx)):
        a, b = units[i]
        if out and abs(out[-1][1] - a) < 1e-6:
            out[-1][1] = b
        else:
            out.append([a, b])
    return [tuple(s) for s in out]


def uniform_units(n: int, m: int):
    return sorted({min(n - 1, int((k + 0.5) * n / m)) for k in range(m)})


def random_units_reward(z, units, m, rng, draws=1000):
    n = len(units)
    return float(np.nanmean([reward(z, unit_spans(units, rng.choice(n, min(m, n), replace=False))) for _ in range(draws)]))


def paired(d):
    d = np.asarray(d, float)
    se = float(d.std(ddof=1) / np.sqrt(len(d)))
    return {"mean": round(float(d.mean()), 4), "se": round(se, 4), "n": len(d), "z": round(float(d.mean() / se), 2) if se else None}
