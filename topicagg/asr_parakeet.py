"""ASR por unidad con Parakeet TDT 0.6B v3 (NVIDIA, CC-BY-4.0, 25 idiomas), frozen (EXP-030).

Una transcripción greedy por unidad (5 s / 10 s). Texto vacío = la unidad no tiene habla: es el filtro de
habla del pipeline (sin segmentos que crucen la música, como pasa con Whisper en documentales).
"""
import numpy as np

PARAKEET = ("nvidia/parakeet-tdt-0.6b-v3", "541d1f99c6b0c3cd0b11a95167540bb8edefd82b")


class Parakeet:
    def __init__(self, device=None):
        import torch
        from transformers import AutoProcessor, ParakeetForTDT
        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.proc = AutoProcessor.from_pretrained(PARAKEET[0], revision=PARAKEET[1])
        self.m = ParakeetForTDT.from_pretrained(PARAKEET[0], revision=PARAKEET[1]).to(self.device).eval()

    def units(self, audio: np.ndarray, units, sr: int = 16000, bs: int = 16) -> list[str]:
        out = []
        for k in range(0, len(units), bs):
            x = [audio[int(a * sr):max(int(b * sr), int(a * sr) + sr // 10)] for a, b in units[k:k + bs]]
            inp = self.proc(x, sampling_rate=sr, return_tensors="pt", padding=True).to(self.device)
            with self.torch.no_grad():
                seq = self.m.generate(**inp)
            out += [t.strip() for t in self.proc.batch_decode(getattr(seq, "sequences", seq), skip_special_tokens=True)]
        return out
