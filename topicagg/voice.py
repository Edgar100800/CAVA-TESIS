"""Señal de voz (EXP-020): espectrograma log-mel + tono, por unidad de tiempo.

Solo numpy + ffmpeg (sin modelos): describe CÓMO suena la voz de cada tramo
—timbre (bandas mel) y altos/bajos del tono (f0)— para que CAVA la use como
un votante más, sin fusionarla con otras señales.

Vector por unidad (normalizado por video, z-score por dimensión):
  64 medias log-mel + 64 desviaciones log-mel
  f0: mediana, p10, p90, rango intercuartil (en semitonos), fracción sonora
  energía: media y desviación (dB)
Unidades sin voz (fracción sonora ~0) devuelven vector nulo: la señal se
abstiene ahí (abstain en manage()).
"""
from __future__ import annotations

import subprocess

import numpy as np

SR = 16000


def load_audio(path: str, sr: int = SR) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def mel_filterbank(n_mels=64, n_fft=512, sr=SR, fmin=60.0, fmax=7600.0):
    def hz2mel(f):
        return 2595 * np.log10(1 + f / 700)

    def mel2hz(m):
        return 700 * (10 ** (m / 2595) - 1)
    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels + 2)
    bins = np.floor((n_fft + 1) * mel2hz(mels) / sr).astype(int)
    fb = np.zeros((n_mels, n_fft // 2 + 1), np.float32)
    for i in range(n_mels):
        a, b, c = bins[i], bins[i + 1], bins[i + 2]
        if b > a:
            fb[i, a:b] = (np.arange(a, b) - a) / (b - a)
        if c > b:
            fb[i, b:c] = (c - np.arange(b, c)) / (c - b)
    return fb


def frames(x, win, hop):
    n = 1 + max(0, (len(x) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return x[idx] if n > 0 and len(x) >= win else np.zeros((0, win), np.float32)


def pitch(fr, sr=SR, fmin=70.0, fmax=400.0):
    """f0 por autocorrelación normalizada; NaN si el cuadro no es sonoro."""
    fr = fr - fr.mean(axis=1, keepdims=True)
    n = fr.shape[1]
    spec = np.fft.rfft(fr, 2 * n, axis=1)
    ac = np.fft.irfft(spec * np.conj(spec), axis=1)[:, :n]
    ac /= np.maximum(ac[:, :1], 1e-9)
    lo, hi = int(sr / fmax), int(sr / fmin)
    lag = lo + np.argmax(ac[:, lo:hi], axis=1)
    peak = ac[np.arange(len(ac)), lag]
    f0 = sr / lag
    f0[peak < 0.45] = np.nan          # poca periodicidad = no sonoro
    return f0


def voice_features(audio: np.ndarray, unit_times: list[list[float]], sr: int = SR) -> np.ndarray:
    fb = mel_filterbank()
    win, hop = int(0.025 * sr), int(0.010 * sr)
    feats = []
    for t0, t1 in unit_times:
        seg = audio[int(t0 * sr):int(t1 * sr)]
        fr = frames(seg, win, hop)
        if len(fr) < 10:
            feats.append(None)
            continue
        energy_db = 10 * np.log10((fr ** 2).mean(1) + 1e-10)
        speechy = energy_db > (np.percentile(energy_db, 90) - 25)
        spec = np.abs(np.fft.rfft(fr * np.hanning(win), 512, axis=1)) ** 2
        logmel = np.log(spec @ fb.T + 1e-10)
        f0 = pitch(frames(seg, int(0.040 * sr), hop))
        voiced = np.isfinite(f0)
        if voiced.mean() < 0.05:
            feats.append(None)          # sin voz: la señal se abstiene
            continue
        semis = 12 * np.log2(f0[voiced] / 100.0)
        lm = logmel[speechy] if speechy.sum() > 5 else logmel
        feats.append(np.concatenate([
            lm.mean(0), lm.std(0),
            [np.median(semis), np.percentile(semis, 10), np.percentile(semis, 90),
             np.subtract(*np.percentile(semis, [75, 25])), voiced.mean()],
            [energy_db.mean(), energy_db.std()]]).astype(np.float32))
    dim = next((len(f) for f in feats if f is not None), 135)
    X = np.zeros((len(feats), dim), np.float32)
    ok = [i for i, f in enumerate(feats) if f is not None]
    if ok:
        M = np.stack([feats[i] for i in ok])
        M = (M - M.mean(0)) / (M.std(0) + 1e-6)     # z-score por video
        X[ok] = M
    return X
