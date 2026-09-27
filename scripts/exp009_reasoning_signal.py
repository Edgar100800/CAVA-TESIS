"""EXP-009: VJudge reasoning como señal de tópicos — gate pre-registrado.

Hipótesis: el razonamiento del VJudge (frozen Qwen) captura estructura
narrativa que las señales visuales/transcript no capturan.

Gate de invalidación:
  Si la coherencia intra-grupo con razonamiento ≤ sin razonamiento,
  el razonamiento no aporta señal temática.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/home/edgar.chambilla/Tesis/CAVA")
sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")
from topicagg.multimodal_manager import manage  # noqa: E402


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


def intra_coherence(embs, groups):
    """Coseno medio intra-grupo ponderado por tamaño."""
    total, weight = 0.0, 0
    for g in groups:
        idx = g.segment_indices
        if len(idx) < 2:
            continue
        x = _l2(embs[idx])
        sims = x @ x.T
        n = len(idx)
        intra = (sims.sum() - np.trace(sims)) / (n * (n - 1))
        total += intra * n
        weight += n
    return total / weight if weight else 0.0


def main():
    pilot = Path("/home/edgar.chambilla/Tesis/SegLoop/data/cava_pilot")
    fusion = Path("/home/edgar.chambilla/Tesis/SegLoop/data/tvsum/processing/segmenter/siglip_bassl_fusion")
    reason_root = Path("/home/edgar.chambilla/Tesis/SegLoop/data/cava_pilot")
    videos = ["Hl-__g2gn_A", "AwmHb44_ouw", "98MoyGZKHXc"]

    results = {"videos": {}}
    for vid in videos:
        npz = fusion / f"{vid}.npz"
        reason_f = reason_root / vid / "vjudge_all_shots.json"
        if not npz.exists() or not reason_f.exists():
            continue
        d = np.load(npz)
        visual = np.asarray(d["tokens"], np.float32)
        reason_d = json.loads(reason_f.read_text())
        n = min(len(visual), len(reason_d["shots"]))
        visual = visual[:n]

        # reasoning embeddings (TF-IDF sobre el corpus de reasoning)
        reason_texts = [s["reasoning"] for s in reason_d["shots"]][:n]
        reason_tfidf = tfidf(reason_texts)

        # visual embedding también L2
        visual = _l2(visual)

        # grupos SIN reasoning (solo visual)
        plan_v = manage({"visual": visual}, n_segments=n,
                        percentile=80, link_quorum=2, tolerance_bins=1)
        coh_v = intra_coherence(visual, plan_v.groups)

        # grupos CON reasoning (visual + reasoning como señal conjunta)
        combined = np.hstack([visual, _l2(reason_tfidf)])
        plan_r = manage({"visual": combined}, n_segments=n,
                        percentile=80, link_quorum=2, tolerance_bins=1)
        coh_r = intra_coherence(combined, plan_r.groups)

        # grupos CON reasoning solo
        plan_reason_only = manage({"reasoning": _l2(reason_tfidf)},
                                  n_segments=n, percentile=80,
                                  link_quorum=2, tolerance_bins=1)
        coh_reason_only = intra_coherence(_l2(reason_tfidf), plan_reason_only.groups)

        results["videos"][vid] = {
            "coherence_visual_only": round(coh_v, 4),
            "coherence_visual_plus_reasoning": round(coh_r, 4),
            "coherence_reasoning_only": round(coh_reason_only, 4),
            "n_shots": n,
        }
        print(f"{vid}: visual={coh_v:.4f} → visual+reasoning={coh_r:.4f} "
              f"(Δ={coh_r - coh_v:+.4f})", flush=True)

    # agregado
    v_vals = [r["coherence_visual_only"] for r in results["videos"].values()]
    r_vals = [r["coherence_visual_plus_reasoning"] for r in results["videos"].values()]
    ro_vals = [r["coherence_reasoning_only"] for r in results["videos"].values()]
    results["aggregate"] = {
        "coherence_visual_mean": round(float(np.mean(v_vals)), 4),
        "coherence_visual_plus_reasoning_mean": round(float(np.mean(r_vals)), 4),
        "coherence_reasoning_only_mean": round(float(np.mean(ro_vals)), 4),
        "delta": round(float(np.mean(r_vals)) - float(np.mean(v_vals)), 4),
    }
    print(f"\n=== AGREGADO ===")
    print(f"visual solo:      {np.mean(v_vals):.4f}")
    print(f"visual+reasoning: {np.mean(r_vals):.4f}")
    print(f"reasoning solo:   {np.mean(ro_vals):.4f}")

    out = pilot / "exp009_results.json"
    out.write_text(json.dumps(results, indent=1))
    print(f"[out] {out}")


if __name__ == "__main__":
    main()
