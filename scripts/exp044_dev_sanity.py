"""EXP-044-TURN: sanidad en desarrollo (dev_20), solo descriptiva y sin MCC ni ajuste de parámetros.

Por reunión: fracción de unidades etiquetadas por C (ward+BIC sobre voz) y por P (pyannote, unit_major),
distribución del score JSD del votante de turnos (w = 6) de C y de P. Regla de parada pre-registrada:
si la mediana del score de P en dev es 0 (votante inactivo) se detiene antes de tocar confirmación.
La mediana de la regla se calcula sobre todas las fronteras de dev agrupadas (n_units − 1 por reunión);
se reportan además las medianas por reunión.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_ami import rttm, unit_major  # noqa: E402
from eval_voice_identities import identities  # noqa: E402
from speaker_turns import speaker_turn_scores  # noqa: E402

D = Path("data/ami")


def dist(x):
    q = np.percentile(x, [10, 25, 50, 75, 90])
    return {"mean": round(float(x.mean()), 4), "p10": round(float(q[0]), 4), "p25": round(float(q[1]), 4),
            "median": round(float(q[2]), 4), "p75": round(float(q[3]), 4), "p90": round(float(q[4]), 4),
            "frac_zero": round(float((x == 0).mean()), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--w", type=int, default=6)
    args = ap.parse_args()
    rows, all_c, all_p = {}, [], []
    for m in Path(args.meetings).read_text().split():
        z = np.load(D / "signals" / f"{m}.npz")
        meta = json.loads((D / "signals" / f"{m}.json").read_text())
        n = min(len(meta["unit_times"]), len(z["voice"]))
        units = meta["unit_times"][:n]
        vid = identities(np.asarray(z["voice"][:n], np.float32), "ward", k_rule="bic")
        pm = unit_major(units, rttm(D / "pyannote" / f"{m}.Mix-Headset.rttm"))
        names = {s: i + 1 for i, s in enumerate(sorted({s for s in pm if s}))}
        pvid = np.array([names[s] if s else -1 for s in pm])
        sc, sp = speaker_turn_scores(vid, args.w), speaker_turn_scores(pvid, args.w)
        all_c.append(sc), all_p.append(sp)
        rows[m] = {"n_units": n, "frac_labeled_C": round(float((vid >= 0).mean()), 4),
                   "frac_labeled_P": round(float((pvid >= 0).mean()), 4), "K_C": int(vid.max()),
                   "K_P": len(names), "score_C": dist(sc), "score_P": dist(sp)}
        print(m, rows[m]["frac_labeled_C"], rows[m]["frac_labeled_P"], rows[m]["score_C"]["median"],
              rows[m]["score_P"]["median"], flush=True)
    c, p = np.concatenate(all_c), np.concatenate(all_p)
    rep = {"w": args.w, "n_meetings": len(rows), "pooled_score_C": dist(c), "pooled_score_P": dist(p),
           "frac_labeled_C_mean": round(float(np.mean([r["frac_labeled_C"] for r in rows.values()])), 4),
           "frac_labeled_P_mean": round(float(np.mean([r["frac_labeled_P"] for r in rows.values()])), 4),
           "n_meetings_median_P_zero": int(sum(r["score_P"]["median"] == 0 for r in rows.values())),
           "stop_rule_pooled_median_P_is_zero": bool(np.median(p) == 0), "per_meeting": rows}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_meeting"}, indent=1))


if __name__ == "__main__":
    main()
