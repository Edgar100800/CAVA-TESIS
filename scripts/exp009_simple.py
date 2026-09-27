"""EXP-009 simplificado: ¿el razonamiento VJudge separa tópicos?

Directo, sin manage(): para cada par de shots en el mismo grupo GT vs
distinto grupo GT, comparamos la similitud de embeddings:
  - visual (SigLIP)
  - reasoning (TF-IDF sobre el texto del VJudge)
  - transcript (ASR, TF-IDF)

Si la similitud de reasoning discrimina mejor que visual, el razonamiento
lleva señal de tópico.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/edgar.chambilla/Tesis/CAVA")
sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")

REASON_ROOT = Path("/home/edgar.chambilla/Tesis/SegLoop/data/cava_pilot")
FUSION_DIR = Path("/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/processing/segmenter/siglip_bassl_fusion")
VIDEOS = ["Hl-__g2gn_A", "AwmHb44_ouw", "98MoyGZKHXc"]


def _l2(x):
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / (n + 1e-8)


def tfidf(texts):
    vocab = {}
    docs = []
    for txt in texts:
        toks = [w for w in "".join(c if c.isalnum() else " " for c in txt.lower()).split()
                if len(w) > 2]
        docs.append(toks)
        for w in set(toks):
            vocab.setdefault(w, len(vocab))
    n_docs = len(docs)
    df = np.zeros(len(vocab))
    for toks in docs:
        for w in set(toks):
            df[vocab[w]] += 1
    idf = np.log((1 + n_docs) / (1 + df)) + 1.0
    rows = []
    for toks in docs:
        v = np.zeros(len(vocab), dtype=np.float32)
        for w in toks:
            v[vocab[w]] += 1.0
        for w in set(toks):
            v[vocab[w]] *= idf[vocab[w]]
        n = np.linalg.norm(v)
        rows.append(v / n if n > 0 else v)
    return np.asarray(rows, dtype=np.float32)


def auc_separation(sims, same_topic):
    """AUC: P(sim(i,j) > sim(i,k)) donde (i,j) mismo tópico, (i,k) distinto."""
    pos = [sims[i, j] for i in range(len(sims)) for j in range(len(sims))
           if i < j and same_topic[i] == same_topic[j]]
    neg = [sims[i, j] for i in range(len(sims)) for j in range(len(sims))
           if i < j and same_topic[i] != same_topic[j]]
    if not pos or not neg:
        return 0.5
    wins = sum(1 for p in pos for n in neg if p > n) + \
           0.5 * sum(1 for p in pos for n in neg if p == n)
    return wins / (len(pos) * len(neg))


def main():
    results = {}
    for vid in VIDEOS:
        # reasoning
        rj = REASON_ROOT / vid / "vjudge_all_shots.json"
        if not rj.exists():
            print(f"[skip] {vid}: sin vjudge")
            continue
        rd = json.loads(rj.read_text())
        shots_rd = rd["shots"]
        n = len(shots_rd)

        # reasoning embeddings
        reason_texts = [s["reasoning"] for s in shots_rd]
        reason_embs = tfidf(reason_texts)

        # visual embeddings
        npz = FUSION_DIR / f"{vid}.npz"
        vd = np.load(npz)
        visual = _l2(np.asarray(vd["tokens"][:n], np.float32))

        # GT: shot → invideo_scene_id (desde topics_multimodal.json si existe,
        # sino desde el orden de shots como proxy)
        # para TVSum no hay scene_id GT — usamos estructura temporal como proxy:
        # shots adyacentes (±3) = probablemente mismo tópico
        same_temporal = np.zeros((n, n), dtype=bool)
        for i in range(n):
            for j in range(max(0, i - 3), min(n, i + 4)):
                if i != j:
                    same_temporal[i, j] = True

        # sim matrices
        r_sim = reason_embs @ reason_embs.T
        v_sim = visual @ visual.T

        # AUC: ¿reasoning separa mejor que visual?
        # pos = pares cercanos temporalmente, neg = pares lejanos
        pos_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)
                     if abs(i - j) <= 3]
        neg_pairs = [(i, j) for i in range(n) for j in range(i + 1, n)
                     if abs(i - j) > 10]
        if not pos_pairs or not neg_pairs:
            continue

        reason_auc = auc_separation_from_pairs(r_sim, pos_pairs, neg_pairs)
        visual_auc = auc_separation_from_pairs(v_sim, pos_pairs, neg_pairs)

        results[vid] = {
            "n_shots": n, "n_pos_pairs": len(pos_pairs), "n_neg_pairs": len(neg_pairs),
            "reasoning_auc_local_vs_remote": round(reason_auc, 4),
            "visual_auc_local_vs_remote": round(visual_auc, 4),
        }
        print(f"{vid}: reasoning AUC={reason_auc:.4f} | visual AUC={visual_auc:.4f}",
              flush=True)

    # agregado
    r_aucs = [v["reasoning_auc_local_vs_remote"] for v in results.values()]
    v_aucs = [v["visual_auc_local_vs_remote"] for v in results.values()]
    print(f"\n=== AGREGADO ===")
    print(f"reasoning AUC: {np.mean(r_aucs):.4f} (4 dominios antes: N/A)")
    print(f"visual AUC:    {np.mean(v_aucs):.4f}")
    out = REASON_ROOT / "exp009_simple.json"
    out.write_text(json.dumps({"per_video": results,
                               "reasoning_auc_mean": round(float(np.mean(r_aucs)), 4),
                               "visual_auc_mean": round(float(np.mean(v_aucs)), 4)},
                              indent=1))
    print(f"[out] {out}")


def auc_separation_from_pairs(sim_matrix, pos_pairs, neg_pairs):
    """AUC: fracción de pares positivos con sim > pares negativos."""
    pos_sims = [sim_matrix[i, j] for i, j in pos_pairs]
    neg_sims = [sim_matrix[i, j] for i, j in neg_pairs]
    wins = sum(1 for p in pos_sims for n in neg_sims if p > n)
    ties = sum(1 for p in pos_sims for n in neg_sims if p == n)
    total = len(pos_sims) * len(neg_sims)
    return (wins + 0.5 * ties) / total if total else 0.5


if __name__ == "__main__":
    main()
