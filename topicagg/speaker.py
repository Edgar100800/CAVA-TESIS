"""Embedding de hablante (EXP-028): WavLM-base-plus-sv frozen, una x-vector de 512 por unidad con habla.

Pesos: `refs/pr/4` (sha 939f573b), conversión safetensors de SFconvertbot; verificado tensor a tensor
(266/266) igual al pytorch_model.bin oficial de microsoft/wavlm-base-plus-sv.
Validado para IDENTIDAD de hablante (VoxConverse test: AUC 0.96 frente a 0.74 de los rasgos de voz).
No es un votante de tópicos: los rasgos de voz (topicagg/voice.py) siguen siendo la señal `voice` del mapa.
"""
import numpy as np

WAVLM = ("microsoft/wavlm-base-plus-sv", "939f573b5e1a33c20332a5fe9ac34f95a66c4f07")


class XVec:
    def __init__(self, device=None):
        device = device or ("cuda" if __import__("torch").cuda.is_available() else "cpu")
        import torch
        from transformers import AutoFeatureExtractor, WavLMForXVector
        self.torch, self.device = torch, device
        self.fe = AutoFeatureExtractor.from_pretrained(WAVLM[0], revision=WAVLM[1])
        self.m = WavLMForXVector.from_pretrained(WAVLM[0], revision=WAVLM[1], use_safetensors=True).to(device).eval()

    def __call__(self, audio, units, gate, sr=16000, bs=32):
        out = np.zeros((len(units), 512), np.float32)
        idx = [i for i in range(len(units)) if gate[i]]
        for k in range(0, len(idx), bs):
            chunk = idx[k:k + bs]
            x = [audio[int(units[i][0] * sr):int(units[i][1] * sr)] for i in chunk]
            inp = self.fe(x, sampling_rate=sr, return_tensors="pt", padding=True).to(self.device)
            with self.torch.no_grad():
                out[chunk] = self.m(**inp).embeddings.float().cpu().numpy()
        return out
