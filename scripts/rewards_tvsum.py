"""EXP-031: recompensa de clips frente a la importancia humana de TVSum (fuera del pipeline; el GT no toca el producto).

Recompensa por segundo = z-score (por video) de la importancia media de los 20 anotadores. Escribe
<run>/rewards.jsonl (una fila por clip de clips.jsonl, con `reward_tvsum`) y results/exp031_tvsum.json.
"""
import json
import math
from pathlib import Path

import numpy as np

S = Path("/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/ydata-tvsum50-v1_1/data/ydata-tvsum50-anno.tsv")
RUNS = Path("data/cava_runs_v1")
N_RANDOM = 1000


def importance():
    acc = {}
    for line in S.read_text().splitlines():
        vid, _, sc = line.split("\t")
        acc.setdefault(vid, []).append(np.array([float(x) for x in sc.split(",")]))
    return {v: np.mean(np.stack(a), 0) for v, a in acc.items()}, {v: np.stack(a) for v, a in acc.items()}


def per_second(frames, duration):
    n = int(math.ceil(duration))
    fps = len(frames) / duration
    sec = np.array([frames[int(s * fps):max(int((s + 1) * fps), int(s * fps) + 1)].mean() for s in range(n)])
    return (sec - sec.mean()) / (sec.std() + 1e-9)


def reward(z, spans):
    secs = np.concatenate([np.arange(int(math.floor(a)), min(int(math.ceil(b)), len(z))) for a, b in spans]) \
        if spans else np.array([], int)
    return float(z[secs].mean()) if len(secs) else float("nan")


def random_spans(durs, D, rng):
    free = D - sum(durs)
    order = rng.permutation(len(durs))
    pts = np.sort(rng.uniform(0, free, len(durs)))
    out, acc = [], 0.0
    for p, k in zip(pts, order):
        out.append((p + acc, p + acc + durs[k]))
        acc += durs[k]
    return out


def uniform_spans(durs, D):
    gap = (D - sum(durs)) / (len(durs) + 1)
    out, t = [], gap
    for d in durs:
        out.append((t, t + d))
        t += d + gap
    return out


def f1_user(sel, user_scores, D, frac=0.15):
    n = int(math.ceil(D))
    fps = len(user_scores) / D
    sec = np.array([user_scores[int(s * fps):max(int((s + 1) * fps), int(s * fps) + 1)].mean() for s in range(n)])
    k = max(1, int(round(frac * n)))
    top = np.zeros(n, bool)
    top[np.argsort(-sec, kind="stable")[:k]] = True
    p = (sel & top).sum() / max(sel.sum(), 1)
    r = (sel & top).sum() / k
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def main():
    imp, users = importance()
    rng = np.random.default_rng(0)
    rows = {}
    for run in sorted(RUNS.iterdir()):
        vid = run.name
        if vid not in imp or not (run / "clips.jsonl").exists():
            continue
        man = json.loads((run / "run_manifest.json").read_text())
        D = float(man["video"]["duration_s"])
        z = per_second(imp[vid], D)
        clips = [json.loads(l) for l in (run / "clips.jsonl").read_text().splitlines()]
        with open(run / "rewards.jsonl", "w") as fh:
            for c in clips:
                fh.write(json.dumps({"clip_id": c["clip_id"], "version": c["version"], "playlist": c["playlist"],
                                     "order": c["order"], "reward_tvsum": reward(z, [(c["t0"], c["t1"])]),
                                     "reward_source": "tvsum_mean20_z"}) + "\n")
        r = {"duration_s": D}
        for ver in ("highlights10pct", "recap60"):
            spans = [(c["t0"], c["t1"]) for c in clips if c["version"] == ver]
            if not spans:
                continue
            durs = [b - a for a, b in spans]
            null = np.array([reward(z, random_spans(durs, D, rng)) for _ in range(N_RANDOM)])
            r[ver] = {"n_clips": len(spans), "seconds": round(sum(durs), 1), "cava": reward(z, spans),
                      "random": float(np.nanmean(null)), "uniform": reward(z, uniform_spans(durs, D)),
                      "percentile_vs_random": float((null < reward(z, spans)).mean())}
            if ver == "highlights10pct":
                sel = np.zeros(int(math.ceil(D)), bool)
                for a, b in spans:
                    sel[int(math.floor(a)):int(math.ceil(b))] = True
                r[ver]["f1_15pct_mean_users"] = float(np.mean([f1_user(sel, u, D) for u in users[vid]]))
        tops = [(c["topic_duration_s"], reward(z, [(c["t0"], c["t1"])])) for c in clips if c["version"] == "full_chapters"]
        if len(tops) > 2:
            from scipy.stats import spearmanr
            r["rho_topic_duration_vs_reward"] = float(spearmanr(*zip(*tops)).correlation)
        rows[vid] = r

    def paired(ver, b):
        d = np.array([r[ver]["cava"] - r[ver][b] for r in rows.values() if ver in r])
        se = d.std(ddof=1) / np.sqrt(len(d))
        return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d), "z": round(float(d.mean() / se), 2)}
    rep = {"n_videos": len(rows),
           "criteria": {"c1_highlights_vs_random": paired("highlights10pct", "random"),
                        "c2_highlights_vs_uniform": paired("highlights10pct", "uniform")},
           "secondary": {"recap60_vs_random": paired("recap60", "random"),
                         "means": {v: {k: round(float(np.mean([r[v][k] for r in rows.values() if v in r])), 4)
                                       for k in ("cava", "random", "uniform", "percentile_vs_random")}
                                   for v in ("highlights10pct", "recap60")},
                         "f1_15pct_mean": round(float(np.mean([r["highlights10pct"]["f1_15pct_mean_users"]
                                                               for r in rows.values() if "highlights10pct" in r])), 4),
                         "rho_topic_duration_vs_reward_mean": round(float(np.nanmean(
                             [r.get("rho_topic_duration_vs_reward", np.nan) for r in rows.values()])), 4)},
           "per_video": rows}
    Path("results/exp031_tvsum.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_video"}, indent=1))


if __name__ == "__main__":
    main()
