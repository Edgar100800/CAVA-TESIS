"""EXP-019: ¿la etiqueta de cada tópico dice quién está y de qué trata?

Contra el GT de contenido (`build_content_gt.py`: cast por shot + guion alineado):
  1. precisión de personajes nombrados en la etiqueta vs GT del tópico, frente a
     la misma medida con etiquetas de OTROS tópicos de la película
  2. recuperación de contenido: bge(etiqueta) vs bge(líneas del guion del
     tópico); MRR del propio tópico vs MRR del azar (H_N / N)
Tópicos del nivel default con duración ≥ --min-dur s.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrative_eval import BgeEmbedder  # noqa: E402


def alias_index(chars):
    owners = {}
    for cid, c in chars.items():
        for a in c["aliases"]:
            owners.setdefault(a, set()).add(cid)
    return {a: next(iter(o)) for a, o in owners.items() if len(o) == 1}   # alias ambiguo: fuera


def named(label, amap):
    return {amap[w.lower()] for w in re.findall(r"\b[A-Z][a-zA-Z]+\b", label or "")
            if w.lower() in amap}


def paired(rows, a, b):
    d = np.array([r[a] - r[b] for r in rows.values() if r.get(a) is not None and r.get(b) is not None])
    if len(d) < 2:
        return None
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": int(len(d)),
            "z": round(float(d.mean() / se), 2) if se > 0 else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--maps", required=True)
    ap.add_argument("--gt", default="data/movienet_content_gt")
    ap.add_argument("--min-dur", type=float, default=30.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels-dir", default=None,
                    help="EXP-019b: usa <tt>.topic_labels.json en lugar de la etiqueta de unidad")
    args = ap.parse_args()
    bge = BgeEmbedder()
    rows = {}
    for tt in Path(args.films_file).read_text().split():
        fm, fg = Path(args.maps) / f"{tt}.topic_map.json", Path(args.gt) / f"{tt}.json"
        if not fm.exists() or not fg.exists():
            continue
        doc, gt = json.loads(fm.read_text()), json.loads(fg.read_text())
        amap = alias_index(gt["characters"])
        shots = gt["shots"]
        topics = [t for t in doc["levels"]["default"]["topics"] if t["duration_s"] >= args.min_dur]
        if args.labels_dir:
            fl = Path(args.labels_dir) / f"{tt}.topic_labels.json"
            if not fl.exists():
                continue
            tl = json.loads(fl.read_text())
            topics = [t | {"label": tl.get(str(t["topic_id"]), t["label"])} for t in topics]
        info = []
        for t in topics:
            cnt = {}
            for s in t["shots"]:
                if s < len(shots):
                    for c in set(shots[s]["on_screen"]) | set(shots[s]["speakers"]):
                        cnt[c] = cnt.get(c, 0) + 1
            gtc = {c for c, k in cnt.items() if k >= 2}
            lines = list(dict.fromkeys(l for s in t["shots"] if s < len(shots) for l in shots[s]["lines"]))
            info.append({"gt": gtc, "named": named(t["label"], amap), "label": t["label"] or "",
                         "text": " ".join(lines)[:2000]})
        valid = [x for x in info if x["gt"]]
        if len(valid) < 3:
            continue
        own = [len(x["named"] & x["gt"]) / len(x["named"]) for x in valid if x["named"]]
        shuf = []
        for i, x in enumerate(valid):
            others = [len(y["named"] & x["gt"]) / len(y["named"])
                      for j, y in enumerate(valid) if j != i and y["named"]]
            if others and x["named"]:
                shuf.append(float(np.mean(others)))
        r = {"n_topics": len(valid), "naming_rate": float(np.mean([bool(x["named"]) for x in valid])),
             "prec_own": float(np.mean(own)) if own else None,
             "prec_shuffled": float(np.mean(shuf)) if shuf else None}
        withtext = [x for x in valid if x["text"].strip()]
        if len(withtext) >= 3:
            L = bge([x["label"] for x in withtext])
            T = bge([x["text"] for x in withtext])
            Ssim = L @ T.T
            ranks = [int((Ssim[i] > Ssim[i, i]).sum()) + 1 for i in range(len(withtext))]
            N = len(withtext)
            r.update({"mrr": float(np.mean([1 / k for k in ranks])),
                      "mrr_chance": float(sum(1 / k for k in range(1, N + 1)) / N),
                      "top1": float(np.mean([k == 1 for k in ranks])), "n_text_topics": N})
        rows[tt] = r
        print(f"[categ] {tt}: tópicos {r['n_topics']} nombra {r['naming_rate']:.2f} "
              f"prec {r['prec_own']} vs {r['prec_shuffled']} | MRR {r.get('mrr')} vs {r.get('mrr_chance')}",
              flush=True)

    crit = {"1_prec_own_vs_shuffled": paired(rows, "prec_own", "prec_shuffled"),
            "2_mrr_vs_chance": paired(rows, "mrr", "mrr_chance")}
    summ = {k: round(float(np.mean([r[k] for r in rows.values() if r.get(k) is not None])), 4)
            for k in ("naming_rate", "prec_own", "prec_shuffled", "mrr", "mrr_chance", "top1", "n_topics")}
    Path(args.out).write_text(json.dumps({"protocol": "exp019_categorization_v1", "n_films": len(rows),
                                          "summary": summ, "criteria": crit, "per_film": rows}, indent=1))
    print(f"\n{len(rows)} películas · {summ}")
    for k, v in crit.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
