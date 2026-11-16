"""EXP-036 F5: utilidades comunes (intervalos, BGE local, texto de briefs, evidencia -> tiempo).

Solo lectura sobre F1/F2 y CAVA_minimo. Sin descargas: HF_HUB_OFFLINE=1.
"""
import json
import os
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]          # /data/tesis-cava
EXP = ROOT / "exp036"
CAVA = ROOT / "CAVA_minimo"
F5 = EXP / "f5"
MOVIES = ["Avengers_Endgame", "Spider_Man"]
BGE = "BAAI/bge-base-en-v1.5"
# Instrucción oficial de bge-*-en-v1.5 para consultas cortas -> pasajes. EXP-035b no la usaba.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
KEYS = ["characters", "actions", "states", "setting"]


def hms(s):
    m, sec = divmod(int(round(s)), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def parse_hms(x):
    parts = [float(p) for p in str(x).strip().split(":")]
    v = 0.0
    for p in parts:
        v = v * 60 + p
    return v


# ---------------------------------------------------------------- intervalos
def merge(iv):
    iv = sorted([float(a), float(b)] for a, b in iv if b > a)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def length(iv):
    return sum(b - a for a, b in merge(iv))


def inter_len(x, y):
    x, y = merge(x), merge(y)
    tot, i, j = 0.0, 0, 0
    while i < len(x) and j < len(y):
        lo, hi = max(x[i][0], y[j][0]), min(x[i][1], y[j][1])
        if hi > lo:
            tot += hi - lo
        if x[i][1] < y[j][1]:
            i += 1
        else:
            j += 1
    return tot


def iou(x, y):
    i = inter_len(x, y)
    u = length(x) + length(y) - i
    return i / u if u > 0 else 0.0


def hit(x, y, min_overlap=1.0):
    return inter_len(x, y) >= min_overlap


def clip(iv, bounds):
    out = []
    for a, b in merge(iv):
        for c, d in merge(bounds):
            lo, hi = max(a, c), min(b, d)
            if hi > lo:
                out.append([lo, hi])
    return merge(out)


# ---------------------------------------------------------------- BGE local
def setup_offline_env():
    os.environ.setdefault("HF_HOME", str(CAVA / "models"))
    os.environ.setdefault("HF_HUB_CACHE", str(CAVA / "models/hub"))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


class Bge:
    """Mismo pooling que CAVA_minimo/scripts/narrative_eval.py:BgeEmbedder (CLS + L2).

    No se importa narrative_eval directamente porque importa `topicagg` a nivel de módulo.
    Diferencia documentada: max_length configurable (512 para documentos; BgeEmbedder usa 256).
    """

    def __init__(self, device="cpu", max_length=512, threads=None):
        setup_offline_env()
        import torch
        from transformers import AutoModel, AutoTokenizer
        if threads:
            torch.set_num_threads(threads)
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(BGE)
        self.model = AutoModel.from_pretrained(BGE).to(device).eval()
        self.device = device
        self.max_length = max_length

    def __call__(self, texts, bs=32, max_length=None, pad_fixed=False):
        """pad_fixed: rellena a max_length fijo. Se usa para consultas: con longitudes variables, cada
        forma nueva de tensor paga la inicialización de kernels de CPU (~0.5-0.8 s), lo que hacía la
        latencia depender del orden de llamada. La máscara de atención hace el CLS equivalente."""
        out = []
        for i in range(0, len(texts), bs):
            batch = [t if t.strip() else "[empty]" for t in texts[i:i + bs]]
            enc = self.tok(batch, padding="max_length" if pad_fixed else True, truncation=True,
                           max_length=max_length or self.max_length, return_tensors="pt").to(self.device)
            with self.torch.inference_mode():
                h = self.model(**enc).last_hidden_state[:, 0]
            out.append(self.torch.nn.functional.normalize(h, dim=-1).cpu().numpy())
        return np.concatenate(out).astype(np.float32) if out else np.zeros((0, 768), np.float32)

    def n_tokens(self, text):
        return len(self.tok(text).input_ids)


# ---------------------------------------------------------------- evidencia F1 -> tiempo
def evidence_rows(spans, units, summaries, asr, mixed=frozenset()):
    """Réplica de exp036/scripts/f1_briefs.py:evidence_lines que además conserva [a, b] y tipo.

    Devuelve lista ordenada de dicts {id, kind, t0, t1, text}; ids E1.. idénticos a F1
    (se verifica contra f1_briefs.evidence_lines en f5_index.py).
    """
    rows = []
    for j, s in enumerate(summaries):
        a, b = units[s["lo"]][0], units[s["hi"] - 1][1]
        if any(b > x0 and a < x1 for x0, x1 in spans):
            tag = " [block crosses a scene boundary: may mix two scenes]" if j in mixed else ""
            rows.append((a, 0, f"VISION {hms(a)}-{hms(b)}{tag}: {s['summary']}", b, "vision", s["summary"]))
    for a, b, txt in asr:
        if any(b > x0 and a < x1 for x0, x1 in spans) and txt.strip():
            rows.append((a, 1, f"DIALOGUE {hms(a)}: \"{txt.strip()}\"", b, "dialogue", txt.strip()))
    rows.sort()
    return [{"id": f"E{i + 1}", "line": f"E{i + 1} {r[2]}", "kind": r[4], "t0": float(r[0]),
             "t1": float(r[3]), "text": r[5]} for i, r in enumerate(rows)]


# ---------------------------------------------------------------- texto del brief
def clean_name(n):
    if not isinstance(n, str):
        return None
    n = n.strip()
    return None if not n or n.lower() in {"null", "none", "unknown", "n/a"} else n


def char_table(brief):
    tab = {}
    for c in brief.get("characters") or []:
        if isinstance(c, dict):
            tab[str(c.get("id"))] = (clean_name(c.get("name")), (c.get("description") or "").strip())
    return tab


def who_text(who, tab):
    ids = who if isinstance(who, list) else [who]
    out = []
    for w in ids:
        name, desc = tab.get(str(w), (None, ""))
        out.append(name or desc or str(w))
    return ", ".join(o for o in out if o)


def brief_items(brief):
    """Ítems atómicos del brief: (sección, texto, evidencia). Base del rerank por fragmentos."""
    tab = char_table(brief)
    items = []
    for c in brief.get("characters") or []:
        if isinstance(c, dict):
            name, desc = clean_name(c.get("name")), (c.get("description") or "").strip()
            txt = f"{name}: {desc}" if name and desc else (name or desc)
            if txt:
                items.append(("characters", txt, list(c.get("evidence") or [])))
    for a in brief.get("actions") or []:
        if isinstance(a, dict) and a.get("what"):
            w = who_text(a.get("who") or [], tab)
            items.append(("actions", f"{w} {a['what']}".strip(), list(a.get("evidence") or [])))
    for s in brief.get("states") or []:
        if isinstance(s, dict) and s.get("state"):
            w = who_text(s.get("who") or [], tab)
            items.append(("states", f"{w}: {s['state']}".strip(": "), list(s.get("evidence") or [])))
    for s in brief.get("setting") or []:
        if isinstance(s, dict) and s.get("what"):
            items.append(("setting", s["what"], list(s.get("evidence") or [])))
    dev = (brief.get("development") or "").strip()
    if dev:
        items.append(("development", dev, []))
    return items


def brief_text(brief):
    """Texto plano estructurado para BM25 y BGE (sin 'uncertain': son dudas, no hechos)."""
    items = brief_items(brief)
    parts = []
    for sec, label in (("characters", "Characters"), ("actions", "Actions"), ("states", "States"),
                       ("setting", "Setting"), ("development", "Development")):
        xs = [t for s, t, _ in items if s == sec]
        if xs:
            parts.append(f"{label}: " + "; ".join(xs) + ".")
    return "\n".join(parts)


def names_of(brief):
    return sorted({n for n, _ in char_table(brief).values() if n})


def load_json(p):
    return json.loads(Path(p).read_text())


_STOP = set("""a an the and or of to in on at for with by from is are was were be been being this that these those
it its as into about over after before while who whom what which where when why how he she they them his her their
him we you i me my our your do does did not no yes so than then there here up down out off just also can could would
should will shall may might must some any all each both other another such very too only own same s t""".split())


def fts_query(q):
    toks = [t for t in re.findall(r"[a-z0-9]+", q.lower()) if t not in _STOP and len(t) > 1]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(toks))
