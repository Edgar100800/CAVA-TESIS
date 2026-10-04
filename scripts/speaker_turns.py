"""EXP-023: votante de fronteras por cambio de quién tiene la palabra.

score[k] (frontera entre unidad k y k+1) = divergencia Jensen-Shannon entre el
histograma de identidades de voz (ward + BIC, EXP-022d) de las `w` unidades
anteriores y el de las `w` siguientes. Unidades sin voz no cuentan. Es un
votante de fronteras (boundary_signals de manage()), no un embedding.
"""
import numpy as np


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
