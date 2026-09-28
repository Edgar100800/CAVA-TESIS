"""EXP-010 eval (CPU): lecturas del narrative interpreter -> fronteras -> F1 vs GT.

Lee la salida de `narrative_interpreter.py` y responde dos preguntas:

  A) Solo: ¿las lecturas narrativas del VJudge, embebidas, marcan fronteras
     de escena? Novedad de ventana (`signal_boundary`) + percentil, igual
     que cualquier otra señal del gestor. Por condición mm / frames / text.
  B) Votante: ¿añadir la lectura `mm` como señal propia a manage()
     (visual + transcript + narrative, sin fusión) mejora el consenso?

Embeddings: bge-base-en-v1.5 (CLS, L2) y TF-IDF (réplica del fallo de EXP-009).
Baselines: azar con el mismo nº de cortes (A: sobre bordes de segmento; B: sobre
shots), 200 sorteos. Techo: recall máximo alcanzable desde bordes de segmento.
Comparación entre condiciones sin umbral: AP de la novedad en cada borde de
segmento (positivo = borde más cercano a un corte GT; AP azar = tasa positiva).
Gate pre-registrado: F1@±15s > 0.30 Y por encima del azar.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.multimodal_manager import _signal_cuts, manage, signal_boundary  # noqa: E402

BGE = "BAAI/bge-base-en-v1.5"


def tfidf(texts):
    vocab, docs = {}, []
    for txt in texts:
        toks = [w for w in "".join(c if c.isalnum() else " " for c in txt.lower()).split()
                if len(w) > 2]
        docs.append(toks)
        for w in set(toks):
            vocab.setdefault(w, len(vocab))
    df = np.zeros(max(1, len(vocab)))
    for toks in docs:
        for w in set(toks):
            df[vocab[w]] += 1
    idf = np.log((1 + len(docs)) / (1 + df)) + 1.0
    rows = []
    for toks in docs:
        v = np.zeros(max(1, len(vocab)), dtype=np.float32)
        for w in toks:
            v[vocab[w]] += idf[vocab[w]]
        n = np.linalg.norm(v)
        rows.append(v / n if n > 0 else v)
    return np.asarray(rows, dtype=np.float32)


class BgeEmbedder:
    def __init__(self, device="cpu"):
        import torch
        from transformers import AutoModel, AutoTokenizer
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(BGE)
        self.model = AutoModel.from_pretrained(BGE).to(device).eval()
        self.device = device

    def __call__(self, texts, bs=32):
        out = []
        for i in range(0, len(texts), bs):
            batch = [t if t.strip() else "[empty]" for t in texts[i:i + bs]]
            enc = self.tok(batch, padding=True, truncation=True, max_length=256,
                           return_tensors="pt").to(self.device)
            with self.torch.inference_mode():
                h = self.model(**enc).last_hidden_state[:, 0]
            out.append(self.torch.nn.functional.normalize(h, dim=-1).cpu().numpy())
        embs = np.concatenate(out).astype(np.float32)
        embs[[not t.strip() for t in texts]] = 0.0  # sin lectura = sin señal
        return embs


def topic_line(desc):
    for line in desc.splitlines():
        line = line.replace("*", "").strip()
        if line.upper().startswith("TOPIC:"):
            return line.split(":", 1)[1].strip()
    return desc


def f1_at(pred_s, gt_s, tol):
    used, matched = set(), 0
    for p in pred_s:
        best = None
        for gi, g in enumerate(gt_s):
            if gi not in used and abs(p - g) <= tol and (best is None or
                                                         abs(p - g) < abs(p - gt_s[best])):
                best = gi
        if best is not None:
            used.add(best)
            matched += 1
    P = matched / len(pred_s) if pred_s else 0.0
    R = matched / len(gt_s) if gt_s else 0.0
    return P, R, (2 * P * R / (P + R)) if P + R else 0.0


def average_precision(scores, labels):
    order = np.argsort(-np.asarray(scores))
    y = np.asarray(labels, dtype=float)[order]
    if y.sum() == 0:
        return 0.0
    prec = np.cumsum(y) / np.arange(1, len(y) + 1)
    return float((prec * y).sum() / y.sum())


def edge_labels(edges, gt_cuts):
    """Cada corte GT marca como positivo su borde de segmento más cercano."""
    lab = np.zeros(len(edges), dtype=int)
    e = np.asarray(edges)
    for g in gt_cuts:
        lab[int(np.argmin(np.abs(e - g)))] = 1
    return lab


def cut_times(shot_cuts, shot_times):
    return [shot_times[k][0] for k in shot_cuts]


def random_f1(n_cuts, candidates, gt_s, shot_times, tol, rng, draws=200):
    if n_cuts == 0 or not candidates:
        return 0.0
    k = min(n_cuts, len(candidates))
    vals = [f1_at(cut_times(sorted(rng.choice(candidates, k, replace=False)), shot_times),
                  gt_s, tol)[2] for _ in range(draws)]
    return float(np.mean(vals))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inp", default="data/narrative_interpreter")
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--percentile", type=float, default=80)
    ap.add_argument("--tols", type=float, nargs="+", default=[5.0, 15.0, 30.0])
    ap.add_argument("--out", default="results/exp010_narrative.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    inp = Path(args.inp)
    bge = BgeEmbedder()
    report = {"protocol": "exp010_narrative_v1", "percentile": args.percentile,
              "tols_s": args.tols, "movies": {}}

    for meta_f in sorted(inp.glob("*.meta.json")):
        meta = json.loads(meta_f.read_text())
        tt, n, st = meta["video_id"], meta["n_shots"], meta["shot_times"]
        gt_s = cut_times(meta["gt_scene_cuts"], st)
        mres = {"n_shots": n, "n_gt_cuts": len(gt_s), "standalone": {}, "voter": {}}

        conds = {}
        for cond in ("mm", "frames", "text"):
            f = inp / f"{tt}.{cond}.json"
            if f.exists():
                segs = json.loads(f.read_text())
                if segs and segs[-1]["shot_end"] >= n:  # solo condiciones completas
                    conds[cond] = segs
        if not conds:
            continue
        any_segs = next(iter(conds.values()))
        edges = [s["shot_start"] for s in any_segs[1:]]  # cortes posibles
        labels = edge_labels(edges, meta["gt_scene_cuts"])
        mres["edge_pos_rate"] = round(float(labels.mean()), 4)  # AP del azar
        mres["recall_ceiling"] = {str(t): f1_at(cut_times(edges, st), gt_s, t)[1]
                                  for t in args.tols}

        # A) cada lectura como señal sola, a nivel de segmento
        seg_embs = {}
        for cond, segs in conds.items():
            descs = [s["description"] for s in segs]
            for emb_name, embs in (("bge_full", bge(descs)),
                                   ("bge_topic", bge([topic_line(d) if d else "" for d in descs])),
                                   ("tfidf_full", tfidf(descs))):
                seg_embs[(cond, emb_name)] = embs
                cuts_seg = _signal_cuts(signal_boundary(embs), args.percentile, 2)
                shot_cuts = [segs[c]["shot_start"] for c in cuts_seg if c < len(segs)]
                row = {"n_cuts": len(shot_cuts),
                       "ap_edges": round(average_precision(signal_boundary(embs), labels), 4),
                       "ap_rand": mres["edge_pos_rate"]}
                for t in args.tols:
                    P, R, F = f1_at(cut_times(shot_cuts, st), gt_s, t)
                    row[f"f1@{t:g}"] = round(F, 4)
                    row[f"p@{t:g}"], row[f"r@{t:g}"] = round(P, 4), round(R, 4)
                    row[f"rand@{t:g}"] = round(random_f1(len(shot_cuts), edges, gt_s, st,
                                                         t, rng), 4)
                mres["standalone"][f"{cond}/{emb_name}"] = row

        # B) lectura mm como votante extra en manage() (sin fusión)
        npz = Path(args.corpus) / f"{tt}.npz"
        if npz.exists() and "mm" in conds:
            d = np.load(npz)
            m = min(n, len(d["visual"]))
            shot2seg = np.zeros(m, dtype=int)
            for s in conds["mm"]:
                shot2seg[s["shot_start"]:min(s["shot_end"], m)] = s["seg_idx"]
            narr = seg_embs[("mm", "bge_full")][shot2seg]
            base = {"visual": np.asarray(d["visual"][:m], np.float32),
                    "transcript": np.asarray(d["tfidf"][:m], np.float32)}
            variants = {"visual+transcript": base,
                        "visual+transcript+narrative": base | {"narrative": narr},
                        "narrative_only_shot": {"narrative": narr}}
            gt_m = [g for g in meta["gt_scene_cuts"] if g < m]
            gt_ms = cut_times(gt_m, st)
            for vname, sigs in variants.items():
                for q in (1, 2):
                    if q > len(sigs):
                        continue
                    plan = manage(sigs, n_segments=m, percentile=args.percentile,
                                  link_quorum=q, tolerance_bins=1)
                    pred = [i for i in range(1, m) if plan.labels[i] != plan.labels[i - 1]]
                    row = {"n_cuts": len(pred), "n_groups": len(plan.groups)}
                    for t in args.tols:
                        P, R, F = f1_at(cut_times(pred, st), gt_ms, t)
                        row[f"f1@{t:g}"] = round(F, 4)
                        row[f"p@{t:g}"], row[f"r@{t:g}"] = round(P, 4), round(R, 4)
                        row[f"rand@{t:g}"] = round(random_f1(len(pred), list(range(1, m)),
                                                             gt_ms, st, t, rng), 4)
                    mres["voter"][f"{vname}/q{q}"] = row
        report["movies"][tt] = mres
        print(f"[eval] {tt}: conds={list(conds)}", flush=True)

    # agregado (media entre películas)
    agg = {}
    for part in ("standalone", "voter"):
        keys = sorted({k for m in report["movies"].values() for k in m[part]})
        for k in keys:
            rows = [m[part][k] for m in report["movies"].values() if k in m[part]]
            agg[f"{part}/{k}"] = {f: round(float(np.mean([r[f] for r in rows])), 4)
                                  for f in rows[0]} | {"n_movies": len(rows)}
    report["aggregate"] = agg
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))

    print("\n| lectura (sola) | AP bordes | AP azar |\n|---|---|---|")
    for k, a in agg.items():
        if "ap_edges" in a:
            print(f"| {k} | {a['ap_edges']:.3f} | {a['ap_rand']:.3f} |")
    t = 15.0 if 15.0 in args.tols else args.tols[0]
    print(f"\n| configuración | n_cortes | F1@±{t:g}s | P | R | azar F1 | Δ vs azar |")
    print("|---|---|---|---|---|---|---|")
    for k, a in agg.items():
        f, r = a[f"f1@{t:g}"], a[f"rand@{t:g}"]
        print(f"| {k} | {a['n_cuts']:.0f} | {f:.3f} | {a[f'p@{t:g}']:.3f} | "
              f"{a[f'r@{t:g}']:.3f} | {r:.3f} | {f - r:+.3f} |")
    print(f"[out] {out}")


if __name__ == "__main__":
    main()
