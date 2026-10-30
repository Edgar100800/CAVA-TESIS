"""Identidades de voz V# y votante de turnos de hablante.

identities: clustering de embeddings de voz por unidad (EXP-022, K por BIC en EXP-022d).
speaker_turn_scores: votante de fronteras por cambio de quién tiene la palabra (EXP-023).
speakers_of: identidades de un conjunto de unidades con su fracción.
Antes vivían en scripts/eval_voice_identities.py, speaker_turns.py y build_ami_topic_maps.py.
"""
import numpy as np
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.metrics import silhouette_score


def bic_k(xn, kmax=8):
    """EXP-022d: nº de identidades por BIC de una mezcla gaussiana (PCA 16, diag)."""
    from sklearn.decomposition import PCA
    from sklearn.mixture import GaussianMixture
    xp = PCA(n_components=min(16, len(xn) - 1), random_state=0).fit_transform(xn)
    bic = {k: GaussianMixture(k, covariance_type="diag", random_state=0).fit(xp).bic(xp)
           for k in range(2, kmax + 1)}
    return min(bic, key=bic.get)


def identities(x, method="average", fixed_k=None, k_rule="silhouette"):
    ok = np.where(np.linalg.norm(x, axis=1) > 0)[0]
    xn = x[ok] / np.linalg.norm(x[ok], axis=1, keepdims=True)
    if k_rule == "bic" and not fixed_k:
        fixed_k = bic_k(xn)
    Z = linkage(xn, method="ward") if method == "ward" else linkage(pdist(xn, "cosine"), method="average")
    best, lab_best = -2, None
    for k in ([fixed_k] if fixed_k else range(2, 9)):
        lab = fcluster(Z, t=k, criterion="maxclust")
        if len(set(lab)) < 2:
            continue
        s = silhouette_score(xn, lab, metric="cosine")
        if s > best or fixed_k:
            best, lab_best = s, lab
    out = np.full(len(x), -1)
    out[ok] = lab_best
    return out


def speaker_turn_scores(vid, w=6):
    n = len(vid)
    K = int(vid.max()) + 1 if (vid >= 0).any() else 1
    score = np.zeros(max(0, n - 1), np.float32)
    for k in range(n - 1):
        L = vid[max(0, k - w + 1):k + 1]
        R = vid[k + 1:k + 1 + w]
        L, R = L[L >= 0], R[R >= 0]
        if len(L) < 2 or len(R) < 2:
            continue
        p = np.bincount(L, minlength=K) / len(L)
        q = np.bincount(R, minlength=K) / len(R)
        m = (p + q) / 2

        def kl(a, b):
            nz = a > 0
            return float((a[nz] * np.log2(a[nz] / b[nz])).sum())
        score[k] = 0.5 * kl(p, m) + 0.5 * kl(q, m)
    return score


def speakers_of(units, vid):
    ids = [vid[u] for u in units if vid[u] >= 0]
    if not ids:
        return []
    vals, cnt = np.unique(ids, return_counts=True)
    order = np.argsort(-cnt)
    return [{"id": f"V{int(vals[k])}", "share": round(float(cnt[k] / len(ids)), 3)} for k in order]
