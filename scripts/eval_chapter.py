"""EXP-013 eval (CPU): criterios pre-registrados de la capitulación del ledger.

Sobre los mismos 100 candidatos SegLoop por película:
  AP beat (±60 s) y AP escena (±1 shot) de segloop, chapter (fracción de
  ventanas que marcan el corte) y ledger_ctx3 (EXP-012). El score chapter tiene
  pocos valores distintos: los empates se rompen al azar y el AP se promedia
  sobre 20 permutaciones (no se desempata con SegLoop: eso sería fusión).
  veto_chapter: orden SegLoop restringido a cortes marcados en ≥ 1 ventana
  (voto del capitulador), K=24, contra SegLoop solo.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_hierarchy import MN, load_film, metrics  # noqa: E402
from eval_ledger import paired  # noqa: E402
from narrative_eval import average_precision  # noqa: E402


def ap_ties(scores, labels, rng, perms=20):
    s = np.asarray(scores, float)
    return float(np.mean([average_precision(s + 1e-9 * rng.random(len(s)), labels)
                          for _ in range(perms)]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--chapter", default="data/vjudge_chapter")
    ap.add_argument("--ledger", default="data/vjudge_ledger")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--K", type=int, default=24)
    ap.add_argument("--logit", default=None,
                    help="EXP-013b: dir con <tt>.chapterlogit.json; score = p_start y el veto "
                         "usa la mediana del juez en la película")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    rng = np.random.default_rng(0)

    rows, sel = {}, {}
    for tt in Path(args.films_file).read_text().split():
        f = (Path(args.logit) / f"{tt}.chapterlogit.json") if args.logit \
            else Path(args.chapter) / f"{tt}.chapter.json"
        if not f.exists() or not (MN / "annotation" / f"{tt}.json").exists():
            continue
        ch = json.loads(f.read_text())
        if args.logit:
            if any(r["p_start"] is None for r in ch):
                continue
            ch = [r | {"score": r["p_start"]} for r in ch]
        else:
            ch = ch["cuts"]
        led = {r["cut"]: r["p_new_ctx3"] for r in
               json.loads((Path(args.ledger) / f"{tt}.ledger.json").read_text())}
        g = load_film(tt, Path(args.corpus))
        if not g or len(g["beat"]) < 2:
            continue
        st, (lo, hi) = g["shot_times"], g["beat_span"]
        cuts = [r["cut"] for r in ch]
        sc = {"segloop": {r["cut"]: r["seg_score"] for r in ch},
              "chapter": {r["cut"]: r["score"] or 0.0 for r in ch},
              "ledger_ctx3": led}
        beat_t = np.asarray([st[b][0] for b in g["beat"]])
        scene = np.asarray(g["scene"])
        inside = [c for c in cuts if lo < c < hi]
        yb = np.asarray([np.min(np.abs(beat_t - st[c][0])) <= 60 for c in inside], int)
        ys = np.asarray([np.min(np.abs(scene - c)) <= 1 for c in cuts], int)
        r = {"beat_pos_rate": float(yb.mean()), "scene_pos_rate": float(ys.mean()),
             "mark_rate": float(np.mean([sc["chapter"][c] > 0 for c in cuts]))}
        for name, s in sc.items():
            r[f"ap_beat_{name}"] = ap_ties([s[c] for c in inside], yb, rng) if yb.sum() else None
            r[f"ap_scene_{name}"] = ap_ties([s[c] for c in cuts], ys, rng)
        rows[tt] = r
        order = sorted(cuts, key=lambda c: -sc["segloop"][c])
        thr = float(np.median([sc["chapter"][c] for c in cuts])) if args.logit else 0.0
        keep = (lambda c: sc["chapter"][c] >= thr) if args.logit else (lambda c: sc["chapter"][c] > 0)
        picks = {"segloop": order[:args.K],
                 "veto_chapter": [c for c in order if keep(c)][:args.K]}
        sel[tt] = {k: metrics(sorted(v), g) for k, v in picks.items()}

    keys = sorted({k for r in rows.values() for k in r if k.startswith("ap_")})
    ap_mean = {k: round(float(np.mean(v)), 4) for k in keys
               if (v := [r[k] for r in rows.values() if r.get(k) is not None])}
    for k in ("beat_pos_rate", "scene_pos_rate", "mark_rate"):
        ap_mean[k] = round(float(np.mean([r[k] for r in rows.values()])), 4)
    d = [sel[t]["veto_chapter"]["beat_f1"] - sel[t]["segloop"]["beat_f1"] for t in sel]
    ds = [sel[t]["veto_chapter"]["scene_f1"] - sel[t]["segloop"]["scene_f1"] for t in sel]
    crit = {"1_chapter_vs_segloop_beat": paired(rows, "ap_beat_chapter", "ap_beat_segloop"),
            "2_veto_chapter_vs_segloop_beatF1_K": {
                "mean": round(float(np.mean(d)), 4),
                "se": round(float(np.std(d, ddof=1) / np.sqrt(len(d))), 4), "n": len(d)},
            "chapter_vs_ledger_ctx3_beat": paired(rows, "ap_beat_chapter", "ap_beat_ledger_ctx3"),
            "scene_chapter_vs_segloop": paired(rows, "ap_scene_chapter", "ap_scene_segloop"),
            "veto_chapter_vs_segloop_sceneF1_K": {
                "mean": round(float(np.mean(ds)), 4),
                "se": round(float(np.std(ds, ddof=1) / np.sqrt(len(ds))), 4)}}
    rep = {"protocol": "exp013_chapter_v1", "films_file": args.films_file, "n_films": len(rows),
           "ap_mean": ap_mean, "criteria": crit, "per_film": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(f"{len(rows)} películas · {ap_mean}")
    for k, v in crit.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
