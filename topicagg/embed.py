"""Embeddings de texto bge-base-en-v1.5 (CLS, L2) para las señales transcript y vjudge.

Antes vivía en scripts/narrative_eval.py (EXP-010); el pipeline lo importa desde aquí.
"""
import numpy as np

BGE = "BAAI/bge-base-en-v1.5"


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
