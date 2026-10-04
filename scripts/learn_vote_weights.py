"""EXP-024: pesos de voto POR SEÑAL aprendidos (ADR-0001: pesos explícitos, sin fusión).

Entrenamiento (reuniones de `--train-splits` del export data/training/ami):
  por reunión, manage() con el perfil meeting da las etiquetas propias de
  cada señal (con retornos y abstención). Para pares de unidades lejanas
  (≥ 18), cada señal aporta un rasgo: 1 si agrupa el par en su propio tópico,
  0 si no o si se abstiene. Regresión logística sobre "mismo tópico GT".
  Pesos = coeficientes (piso 0.05), normalizados a suma = nº de señales;
  quorum = −intercepto en la misma escala.
Evaluación (`--test-split`): MCC de manage(weights, link_quorum aprendido)
frente a pesos iguales (quorum 2), mismas señales y perfil, más turnos (w = 6).
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_topic_map import mcc  # noqa: E402
from eval_voice_identities import identities  # noqa: E402
from speaker_turns import speaker_turn_scores  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402

T = Path("data/training/ami")
SIGS = ("voice", "visual", "transcript", "vjudge")
PROF = dict(percentile=95, return_percentile=90, tolerance_bins=1, link_mode="average", abstain=True)


def load(split):
    for f in sorted(T.glob("*.json")):
        meta = json.loads(f.read_text())
        if meta["split"] == split:
            z = np.load(f.with_suffix(".npz"))
            yield meta["id"], {k: z[k].astype(np.float32) for k in SIGS}, z["topic"]


def pairs_of(topic, gap=18):
    I, J = np.triu_indices(len(topic), gap)
    keep = (topic[I] >= 0) & (topic[J] >= 0)
    return I[keep], J[keep], (topic[I[keep]] == topic[J[keep]])


def turns(sig):
    vid = identities(sig["voice"], "ward", k_rule="bic")
    return {"turns": speaker_turn_scores(vid, 6)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train-splits", nargs="+", default=["dev", "conf"])
    ap.add_argument("--test-split", default="fresh3")
    ap.add_argument("--out", default="results/exp024_vote_weights.json")
    args = ap.parse_args()
    X, Y = [], []
    names = list(SIGS) + ["turns"]
    for split in args.train_splits:
        for m, sig, topic in load(split):
            plan = manage(sig, boundary_signals=turns(sig), link_quorum=2, **PROF)
            I, J, y = pairs_of(topic)
            if len(y) < 20:
                continue
            feats = []
            for k in names:
                lab = plan.per_signal_labels[k]
                feats.append(((lab[I] == lab[J]) & (lab[I] >= 0) & (lab[J] >= 0)).astype(np.float32))
            X.append(np.stack(feats, 1))
            Y.append(y)
            print(f"[learn] {split} {m}: {len(y)} pares", flush=True)
    X, Y = np.concatenate(X), np.concatenate(Y)
    clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(X, Y)
    coef = np.maximum(clf.coef_[0], 0.05)
    scale = len(names) / coef.sum()
    weights = {k: round(float(c * scale), 4) for k, c in zip(names, coef)}
    quorum = round(float(max(-clf.intercept_[0] * scale, 0.5)), 4)
    print(f"[learn] pesos {weights} quorum {quorum}", flush=True)
    rows = {}
    for m, sig, topic in load(args.test_split):
        I, J, y = pairs_of(topic)
        if len(y) < 20 or y.all() or (~y).all():
            continue
        bnd = turns(sig)
        eq = manage(sig, boundary_signals=bnd, link_quorum=2, **PROF)
        lw = manage(sig, boundary_signals=bnd, link_quorum=quorum, weights=weights, **PROF)
        rows[m] = {"mcc_equal": mcc(eq.labels[I] == eq.labels[J], y),
                   "mcc_learned": mcc(lw.labels[I] == lw.labels[J], y),
                   "topics_equal": len(set(eq.labels.tolist())), "topics_learned": len(set(lw.labels.tolist()))}
    d = np.array([r["mcc_learned"] - r["mcc_equal"] for r in rows.values()])
    rep = {"weights": weights, "quorum": quorum, "n_train_pairs": int(len(Y)), "n_test": len(rows),
           "mcc_equal": round(float(np.mean([r["mcc_equal"] for r in rows.values()])), 4),
           "mcc_learned": round(float(np.mean([r["mcc_learned"] for r in rows.values()])), 4),
           "learned_minus_equal": {"mean": round(float(d.mean()), 4),
                                   "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4)} if len(d) > 1 else None,
           "per_meeting": rows}
    Path(args.out).write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "per_meeting"}, indent=1))


if __name__ == "__main__":
    main()
