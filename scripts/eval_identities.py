"""EXP-019e criterio 5 + cobertura: ¿las identidades por apariencia (P#) son
consistentes y cuántos tópicos quedan categorizados por personaje?

  consistencia  pares de tópicos que comparten una P#: fracción que comparte ≥ 1
                personaje del GT (cast + hablantes, ≥ 2 shots en cada tópico),
                frente a TODOS los pares de tópicos de la misma película.
                Fisher unilateral sobre los conteos agrupados.
  cobertura     fracción de tópicos (≥ 30 s, con GT) con ≥ 1 personaje
                categorizado: nombre que casa con un alias del cast, o una P#.
"""
import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categorize_characters import distinctive_words  # noqa: E402
from eval_categorization import alias_index, named  # noqa: E402


def gt_chars(t, shots):
    cnt = {}
    for s in t["shots"]:
        if s < len(shots):
            for c in set(shots[s]["on_screen"]) | set(shots[s]["speakers"]):
                cnt[c] = cnt.get(c, 0) + 1
    return {c for c, k in cnt.items() if k >= 2}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--maps", required=True)
    ap.add_argument("--cat", default="data/topic_labels_cat")
    ap.add_argument("--base-labels", default="data/topic_labels")
    ap.add_argument("--gt", default="data/movienet_content_gt")
    ap.add_argument("--min-dur", type=float, default=30.0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--filter-min-words", type=int, default=2,
                    help="EXP-019f: separa identidades cuya descripción tiene ≥ N palabras distintivas")
    args = ap.parse_args()
    id_same = id_n = base_same = base_n = 0
    pass_same = pass_n = fail_same = fail_n = 0
    cov, cov_base, per = [], [], {}
    for tt in Path(args.films_file).read_text().split():
        fm, fg = Path(args.maps) / f"{tt}.topic_map.json", Path(args.gt) / f"{tt}.json"
        fi, fl = Path(args.cat) / f"{tt}.identities.json", Path(args.cat) / f"{tt}.topic_labels.json"
        if not (fm.exists() and fg.exists() and fi.exists() and fl.exists()):
            continue
        gt = json.loads(fg.read_text())
        amap, shots = alias_index(gt["characters"]), gt["shots"]
        topics = {t["topic_id"]: t for t in json.loads(fm.read_text())["levels"]["default"]["topics"]
                  if t["duration_s"] >= args.min_dur}
        G = {tid: gt_chars(t, shots) for tid, t in topics.items()}
        G = {k: v for k, v in G.items() if v}
        if not G:
            continue
        idents = json.loads(fi.read_text())
        labels = json.loads(fl.read_text())
        base = json.loads((Path(args.base_labels) / f"{tt}.topic_labels.json").read_text())
        s_id = n_id = 0
        for v in idents.values():
            ok = len(distinctive_words(v["description"])) >= args.filter_min_words
            for a, b in combinations([x for x in v["topics"] if x in G], 2):
                n_id += 1
                sh = bool(G[a] & G[b])
                s_id += sh
                if ok:
                    pass_n, pass_same = pass_n + 1, pass_same + sh
                else:
                    fail_n, fail_same = fail_n + 1, fail_same + sh
        s_all = n_all = 0
        for a, b in combinations(sorted(G), 2):
            n_all += 1
            s_all += bool(G[a] & G[b])
        id_same, id_n, base_same, base_n = id_same + s_id, id_n + n_id, base_same + s_all, base_n + n_all
        with_id = {x for v in idents.values() for x in v["topics"]}
        c = [bool(named(labels.get(str(t), ""), amap)) or t in with_id for t in G]
        cb = [bool(named(base.get(str(t), ""), amap)) for t in G]
        cov.append(float(np.mean(c)))
        cov_base.append(float(np.mean(cb)))
        per[tt] = {"id_pairs": n_id, "id_share": s_id, "all_pairs": n_all, "all_share": s_all,
                   "coverage": cov[-1], "coverage_base_named": cov_base[-1], "n_identities": len(idents)}
    _, p = fisher_exact([[id_same, id_n - id_same], [base_same, base_n - base_same]], alternative="greater")
    _, p_pf = fisher_exact([[pass_same, pass_n - pass_same], [fail_same, fail_n - fail_same]],
                           alternative="greater")
    d = np.array(cov) - np.array(cov_base)
    rep = {"n_films": len(per),
           "identity_pairs": id_n, "identity_share_rate": round(id_same / max(id_n, 1), 4),
           "random_pair_share_rate": round(base_same / max(base_n, 1), 4), "fisher_p": round(float(p), 6),
           "coverage_019e": round(float(np.mean(cov)), 4), "named_019b": round(float(np.mean(cov_base)), 4),
           "coverage_gain": {"mean": round(float(d.mean()), 4),
                             "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4)},
           "filter_pass": {"pairs": pass_n, "share_rate": round(pass_same / max(pass_n, 1), 4)},
           "filter_fail": {"pairs": fail_n, "share_rate": round(fail_same / max(fail_n, 1), 4)},
           "fisher_p_pass_vs_fail": round(float(p_pf), 6),
           "identities_per_film": round(float(np.mean([v["n_identities"] for v in per.values()])), 2),
           "per_film": per}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_film"}, indent=1))


if __name__ == "__main__":
    main()
