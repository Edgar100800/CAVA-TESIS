"""EXP-019e: categorización de personajes por tópico — nombres + identidades por apariencia.

Por video, solo con salidas de CAVA (el GT no interviene):
  1. etiqueta propia (019b) intacta: se AÑADE, no se reescribe
  2. nombres por enlaces (regla 019d: visual ≥ p90 y vjudge ≥ p75, quorum 2)
  3. descripción → nombre: frase descriptiva de CHARACTERS vs entradas del
     registro (019c); se asigna la más similar (bge) si sim ≥ p95 del video
  4. identidades P#: frases aún sin nombre agrupadas entre tópicos por enlace
     promedio sobre el acuerdo de DOS señales (texto bge ≥ p90 Y visual de sus
     tópicos ≥ p75); grupos que abarcan ≥ 2 tópicos
Etiqueta final: "<etiqueta propia> || NAMES: … || IDS: P1 (desc); …"
Salida: <out>/<tt>.topic_labels.json y <out>/<tt>.identities.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_threads import STOP  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from propagate_names import centroid  # noqa: E402

NAME = re.compile(r"\b[A-Z][a-z]+\b")


def phrases(label):
    head = label.split("|")[0]
    head = head.split(":", 1)[1] if ":" in head else head
    parts = re.split(r",|;|\band\b", head)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def names_in(text):
    return {w for w in NAME.findall(text) if w not in STOP}


def parse_registry(text):
    out = []
    for line in text.splitlines():
        if " - " in line:
            name, desc = line.split(" - ", 1)
            name = name.strip("-* ").strip()
            if names_in(name):
                out.append((name, f"{name} - {desc.strip()}"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", required=True)
    ap.add_argument("--summary-dir", required=True)
    ap.add_argument("--labels", default="data/topic_labels")
    ap.add_argument("--registry", default="data/topic_labels_reg")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--out", default="data/topic_labels_cat")
    ap.add_argument("--min-dur", type=float, default=30.0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bge = BgeEmbedder()
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    for f in sorted(Path(args.maps).glob("*.topic_map.json")):
        doc = json.loads(f.read_text())
        tt = doc["video_id"]
        fl, fr = Path(args.labels) / f"{tt}.topic_labels.json", Path(args.registry) / f"{tt}.registry.txt"
        if not fl.exists():
            continue
        labels = json.loads(fl.read_text())
        registry = parse_registry(fr.read_text()) if fr.exists() else []
        topics = [t for t in doc["levels"]["default"]["topics"]
                  if t["duration_s"] >= args.min_dur and str(t["topic_id"]) in labels]
        if len(topics) < 3:
            continue
        vis = np.asarray(np.load(Path(args.corpus) / f"{tt}.npz")["visual"], np.float32)
        sums = json.loads((Path(args.summary_dir) / f"{tt}.summaries.json").read_text())
        e = bge([u["summary"] for u in sums])
        vj = np.zeros((len(vis), e.shape[1]), np.float32)
        for u, v in zip(sums, e):
            vj[u["lo"]:min(u["hi"], len(vis))] = v
        K = len(topics)
        cv = [centroid(vis, t["shots"]) for t in topics]
        cj = [centroid(vj, t["shots"]) for t in topics]
        Sv, Sj = np.full((K, K), np.nan), np.full((K, K), np.nan)
        for i in range(K):
            for j in range(K):
                if i != j and cv[i] is not None and cv[j] is not None:
                    Sv[i, j] = float(cv[i] @ cv[j])
                if i != j and cj[i] is not None and cj[j] is not None:
                    Sj[i, j] = float(cj[i] @ cj[j])
        tv90, tj75, tv75 = (np.nanpercentile(Sv, 90), np.nanpercentile(Sj, 75), np.nanpercentile(Sv, 75))
        own = [labels[str(t["topic_id"])] for t in topics]
        # nombres como FRASES ("Indiana Jones"), no palabras sueltas
        names = [{p for p in phrases(l) if names_in(p)} for l in own]
        own_tokens = [names_in(" ".join(n)) for n in names]
        added = [set() for _ in range(K)]

        # 2) nombres por enlaces (019d, modo añadir)
        for i in range(K):
            if names[i]:
                continue
            donors = [j for j in range(K) if j != i and names[j] and not np.isnan(Sv[i, j])
                      and not np.isnan(Sj[i, j]) and Sv[i, j] >= tv90 and Sj[i, j] >= tj75]
            if donors:
                added[i] |= names[max(donors, key=lambda k: Sv[i, k])]

        # 3) descripción -> nombre por el registro
        desc = [(i, p) for i in range(K) for p in phrases(own[i]) if not names_in(p)]
        if desc and registry:
            D = bge([p for _, p in desc])
            R = bge([r for _, r in registry])
            S = D @ R.T
            thr = np.percentile(S, 95)
            keep = []
            for k, (i, p) in enumerate(desc):
                b = int(np.argmax(S[k]))
                if S[k, b] >= thr:
                    added[i].add(registry[b][0])
                else:
                    keep.append((i, p))
            desc = keep

        # 4) identidades por apariencia (texto Y visual, enlace promedio)
        identities = {}
        if len(desc) >= 2:
            D = bge([p for _, p in desc])
            St = D @ D.T
            iu = np.triu_indices(len(desc), 1)
            tt90 = np.percentile(St[iu], 90)
            A = np.zeros((len(desc), len(desc)))
            for a in range(len(desc)):
                for b in range(len(desc)):
                    ia, ib = desc[a][0], desc[b][0]
                    vis_ok = ia == ib or (not np.isnan(Sv[ia, ib]) and Sv[ia, ib] >= tv75)
                    A[a, b] = float(a == b or (St[a, b] >= tt90 and vis_ok))
            Z = linkage(squareform(1.0 - A, checks=False), method="average")
            cl = fcluster(Z, t=0.5, criterion="distance")
            pid = 0
            for c in sorted(set(cl)):
                mem = [k for k in range(len(desc)) if cl[k] == c]
                tops = sorted({desc[k][0] for k in mem})
                if len(tops) < 2:
                    continue
                pid += 1
                central = max(mem, key=lambda k: St[k, mem].mean())
                identities[f"P{pid}"] = {"description": desc[central][1],
                                         "topics": [topics[i]["topic_id"] for i in tops]}
        ids_of = {}
        for p_, v in identities.items():
            for tid in v["topics"]:
                ids_of.setdefault(tid, []).append(f"{p_} ({v['description']})")

        new = dict(labels)
        n_added = 0
        for i, t in enumerate(topics):
            extra = []
            # solo nombres que aportan alguna palabra nueva a la etiqueta propia
            fresh = sorted({c for c in added[i] if names_in(c) - own_tokens[i]})
            if fresh:
                extra.append("NAMES: " + ", ".join(fresh))
                n_added += 1
            if t["topic_id"] in ids_of:
                extra.append("IDS: " + "; ".join(ids_of[t["topic_id"]]))
            if extra:
                new[str(t["topic_id"])] = own[i] + " || " + " || ".join(extra)
        (out / f"{tt}.topic_labels.json").write_text(json.dumps(new, ensure_ascii=False))
        (out / f"{tt}.identities.json").write_text(json.dumps(identities, indent=1, ensure_ascii=False))
        print(f"[categorize] {tt}: +nombres {n_added}, "
              f"identidades {len(identities)}", flush=True)


if __name__ == "__main__":
    main()
