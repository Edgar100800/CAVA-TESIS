"""EXP-012 eval (CPU): criterios pre-registrados del story ledger.

Por conjunto de películas (--films-file: desarrollo o replicación), sobre los
mismos 100 candidatos SegLoop por película:
  AP beat (±60 s, dentro del tramo anotado) y AP escena (±1 shot) de:
    segloop · ledger_ctx1 · ledger_ctx3 · relational_mm (paso 2, si existe)
  Diferencias pareadas por película con SE (criterios 1–3).
  Criterio 4: veto relativo ctx3 (orden SegLoop saltando la mitad inferior del
  ledger) − SegLoop solo, beat F1 a K=24, pareado.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_hierarchy import MN, load_film, metrics  # noqa: E402
from narrative_eval import average_precision  # noqa: E402


def paired(rows, a, b):
    d = [r[a] - r[b] for r in rows.values() if r.get(a) is not None and r.get(b) is not None]
    if len(d) < 2:
        return None
    m, se = float(np.mean(d)), float(np.std(d, ddof=1) / np.sqrt(len(d)))
    return {"mean": round(m, 4), "se": round(se, 4), "n": len(d),
            "z": round(m / se, 2) if se > 0 else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--ledger", default="data/vjudge_ledger")
    ap.add_argument("--relational", default="data/vjudge_relational")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--K", type=int, default=24)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows, sel = {}, {}
    for tt in Path(args.films_file).read_text().split():
        f = Path(args.ledger) / f"{tt}.ledger.json"
        if not f.exists() or not (MN / "annotation" / f"{tt}.json").exists():
            continue
        led = json.loads(f.read_text())
        if not led or any(r.get("p_new_ctx3") is None for r in led):
            continue
        g = load_film(tt, Path(args.corpus))
        if not g or len(g["beat"]) < 2:
            continue
        st, (lo, hi) = g["shot_times"], g["beat_span"]
        cuts = [r["cut"] for r in led]
        sc = {"segloop": {r["cut"]: r["seg_score"] for r in led},
              "ledger_ctx1": {r["cut"]: r["p_new_ctx1"] for r in led},
              "ledger_ctx3": {r["cut"]: r["p_new_ctx3"] for r in led}}
        rf = Path(args.relational) / f"{tt}.mm.json"
        if rf.exists():
            rel = {r["cut"]: r["p_new"] for r in json.loads(rf.read_text())}
            if set(rel) == set(cuts):
                sc["relational_mm"] = rel
        beat_t = np.asarray([st[b][0] for b in g["beat"]])
        scene = np.asarray(g["scene"])
        inside = [c for c in cuts if lo < c < hi]
        yb = np.asarray([np.min(np.abs(beat_t - st[c][0])) <= 60 for c in inside], int)
        ys = np.asarray([np.min(np.abs(scene - c)) <= 1 for c in cuts], int)
        r = {"beat_pos_rate": float(yb.mean()), "scene_pos_rate": float(ys.mean())}
        for name, s in sc.items():
            r[f"ap_beat_{name}"] = average_precision([s[c] for c in inside], yb) if yb.sum() else None
            r[f"ap_scene_{name}"] = average_precision([s[c] for c in cuts], ys)
        rows[tt] = r

        order = sorted(cuts, key=lambda c: -sc["segloop"][c])
        med = np.median([sc["ledger_ctx3"][c] for c in cuts])
        picks = {"segloop": order[:args.K],
                 "veto_rel_ctx3": [c for c in order if sc["ledger_ctx3"][c] >= med][:args.K],
                 "ledger_ctx3_topk": sorted(cuts, key=lambda c: -sc["ledger_ctx3"][c])[:args.K]}
        sel[tt] = {k: metrics(sorted(v), g) for k, v in picks.items()}

    keys = sorted({k for r in rows.values() for k in r if k.startswith("ap_")})
    ap_mean = {k: round(float(np.mean(v)), 4) for k in keys
               if (v := [r[k] for r in rows.values() if r.get(k) is not None])}
    ap_mean["rand_beat"] = round(float(np.mean([r["beat_pos_rate"] for r in rows.values()])), 4)
    ap_mean["rand_scene"] = round(float(np.mean([r["scene_pos_rate"] for r in rows.values()])), 4)
    crit = {
        "1_ctx3_vs_segloop_beat": paired(rows, "ap_beat_ledger_ctx3", "ap_beat_segloop"),
        "2_ctx3_vs_ctx1_beat": paired(rows, "ap_beat_ledger_ctx3", "ap_beat_ledger_ctx1"),
        "3_ctx3_vs_relational_beat": paired(rows, "ap_beat_ledger_ctx3", "ap_beat_relational_mm"),
        "scene_ctx3_vs_segloop": paired(rows, "ap_scene_ledger_ctx3", "ap_scene_segloop"),
    }
    d4 = [sel[t]["veto_rel_ctx3"]["beat_f1"] - sel[t]["segloop"]["beat_f1"] for t in sel]
    crit["4_veto_rel_ctx3_vs_segloop_beatF1_K"] = {
        "mean": round(float(np.mean(d4)), 4),
        "se": round(float(np.std(d4, ddof=1) / np.sqrt(len(d4))), 4), "n": len(d4)}
    sel_mean = {k: {m: round(float(np.mean([sel[t][k][m] for t in sel
                                             if sel[t][k][m] is not None])), 4)
                    for m in ("scene_f1", "beat_f1", "beat_pk", "scene_prec")}
                for k in next(iter(sel.values()))}
    rep = {"protocol": "exp012_ledger_v1", "films_file": args.films_file, "n_films": len(rows),
           "K": args.K, "ap_mean": ap_mean, "criteria": crit, "selection_mean": sel_mean,
           "per_film": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(f"{len(rows)} películas · AP media: {ap_mean}")
    for k, v in crit.items():
        print(f"  {k}: {v}")
    print(f"  selección K={args.K}: {sel_mean}")
    print(f"[out] {args.out}")


if __name__ == "__main__":
    main()
