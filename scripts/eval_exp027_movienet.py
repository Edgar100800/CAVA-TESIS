"""EXP-027 confirmación: snap de fronteras CAVA a fronteras visuales (R = 30 s) en MovieNet train2."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import f1_b  # noqa: E402
from eval_topic_map import mcc  # noqa: E402
from explore_visual_boundaries import random_like, snap  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402
from topicagg.topic_map import snap_boundaries as snap_time  # noqa: E402

AB = dict(percentile=80, link_quorum=2, tolerance_bins=1, link_mode="average", abstain=True, return_percentile=90)




def main():
    T = Path("data/training/movienet")
    rows = {}
    for f in sorted(T.glob("*.json")):
        meta = json.loads(f.read_text())
        if meta["split"] != "train2":
            continue
        z = np.load(f.with_suffix(".npz"))
        sig = {k: z[k].astype(np.float32) for k in ("visual", "dialogue", "vjudge")}
        units, gt = z["units"].astype(float), z["scene"]
        n = len(gt)
        mid, ends = units.mean(1), units[:, 1]
        I, J = np.triu_indices(n, 1)
        keep = np.abs(mid[J] - mid[I]) <= 300
        I, J = I[keep], J[keep]
        y = gt[I] == gt[J]
        base = np.asarray(manage(sig, **AB).labels)
        vis = np.asarray(manage({"visual": sig["visual"]}, **(AB | {"link_quorum": 1})).labels)
        cand = {"cava": base, "snap30": snap_time(base, vis, ends, 30.0), "snap6u": snap(base, vis, 6)}
        rnd = [snap_time(base, random_like(vis, s), ends, 30.0) for s in range(5)]
        r = {k: {"m": mcc(v[I] == v[J], y), "f1": f1_b(v, [gt])} for k, v in cand.items()}
        r["rand30"] = {"m": float(np.mean([mcc(v[I] == v[J], y) for v in rnd])),
                       "f1": float(np.mean([f1_b(v, [gt]) for v in rnd]))}
        r["visual"] = {"m": mcc(vis[I] == vis[J], y), "f1": f1_b(vis, [gt])}
        rows[meta["id"]] = r
        print(meta["id"], " ".join(f"{k}={v['m']:.3f}/{v['f1']:.3f}" for k, v in r.items()), flush=True)

    def paired(a, b, k):
        d = np.array([x[a][k] - x[b][k] for x in rows.values()])
        se = d.std(ddof=1) / np.sqrt(len(d))
        return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d), "z": round(float(d.mean() / se), 2)}
    rep = {"means": {s: {k: round(float(np.mean([x[s][k] for x in rows.values()])), 4) for k in ("m", "f1")}
                     for s in next(iter(rows.values()))},
           "criteria": {f"snap30_vs_{b}_{k}": paired("snap30", b, k) for b in ("cava", "rand30") for k in ("m", "f1")},
           "secondary": {f"snap6u_vs_cava_{k}": paired("snap6u", "cava", k) for k in ("m", "f1")},
           "per_film": rows}
    Path("results/exp027_movienet_train2.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_film"}, indent=1))


if __name__ == "__main__":
    main()
