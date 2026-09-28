"""EXP-009b: mismo protocolo que exp009_simple, reasoning con bge-base (semántico).

Cierra el pendiente de EXP-009 ("un embedder semántico podría capturar
estructura que TF-IDF no ve"). AUC local (≤3 shots) vs remoto (>10 shots).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp009_simple import (FUSION_DIR, REASON_ROOT, VIDEOS, _l2,  # noqa: E402
                           auc_separation_from_pairs, tfidf)
from narrative_eval import BgeEmbedder  # noqa: E402


def main():
    bge = BgeEmbedder()
    results = {}
    for vid in VIDEOS:
        rj = REASON_ROOT / vid / "vjudge_all_shots.json"
        if not rj.exists():
            continue
        shots = json.loads(rj.read_text())["shots"]
        n = len(shots)
        texts = [s["reasoning"] for s in shots]
        visual = _l2(np.asarray(np.load(FUSION_DIR / f"{vid}.npz")["tokens"][:n], np.float32))
        pos = [(i, j) for i in range(n) for j in range(i + 1, n) if j - i <= 3]
        neg = [(i, j) for i in range(n) for j in range(i + 1, n) if j - i > 10]
        embs = {"visual": visual, "reasoning_tfidf": tfidf(texts), "reasoning_bge": bge(texts)}
        results[vid] = {"n_shots": n} | {
            k: round(auc_separation_from_pairs(e @ e.T, pos, neg), 4) for k, e in embs.items()}
        print(vid, results[vid], flush=True)
    mean = {k: round(float(np.mean([r[k] for r in results.values()])), 4)
            for k in ("visual", "reasoning_tfidf", "reasoning_bge")}
    print("mean", mean)
    out = REASON_ROOT / "exp009_bge.json"
    out.write_text(json.dumps({"protocol": "exp009b_bge", "per_video": results,
                               "mean_auc": mean}, indent=1))
    print("[out]", out)


if __name__ == "__main__":
    main()
