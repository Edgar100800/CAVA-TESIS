"""EXP-045-Q: refset_v1 (rutas) y comparaciones de mapas/versiones compartidas por los scripts de la validación."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

EXP = Path("/data/tesis-cava/exp045")
INP = EXP / "inputs"
VIDEOS = {
    "Spider_Man": dict(path="/data/tesis-cava/CAVA_minimo/videos/Spider_Man.mp4", profile="film", audio=None, machine="56"),
    "ES2002c.Room": dict(path=str(INP / "ami/ES2002c.Room.avi"), profile="meeting",
                         audio=str(INP / "ami/ES2002c.Mix-Headset.wav"), machine="56"),
    "bbc_01": dict(path=str(INP / "bbc/bbc_01.mp4"), profile="documentary", audio=None, machine="54"),
    "com_en_01": dict(path=str(INP / "abset/com_en_01.mp4"), profile="documentary", audio=None, machine="54"),
    "com_es_01": dict(path=str(INP / "abset/com_es_01.mp4"), profile="documentary", audio=None, machine="54"),
}
STACK = "v1.1"


def topic_of_units(doc, n_units):
    """Etiqueta de tópico por unidad (-1 si la unidad queda fuera de todo tópico). Nivel 'default'."""
    lab = np.full(n_units, -1, dtype=np.int64)
    for t in doc["levels"]["default"]["topics"]:
        for u in t["shots"]:
            if u < n_units:
                lab[u] = int(t["topic_id"]) if str(t["topic_id"]).lstrip("-").isdigit() else hash(t["topic_id"]) % (10 ** 9)
    return lab


def boundaries(lab):
    return {i for i in range(1, len(lab)) if lab[i] != lab[i - 1]}


def f1_tol(ref, cand, tol=1):
    """F1 de fronteras con tolerancia ±tol unidades; emparejamiento uno a uno voraz por cercanía."""
    r, c = sorted(ref), sorted(cand)
    if not r and not c:
        return 1.0
    used, tp = set(), 0
    for b in r:
        best = None
        for x in c:
            if x in used or abs(x - b) > tol:
                continue
            if best is None or abs(x - b) < abs(best - b):
                best = x
        if best is not None:
            used.add(best)
            tp += 1
    p = tp / len(c) if c else 0.0
    q = tp / len(r) if r else 0.0
    return 2 * p * q / (p + q) if p + q else 0.0


def seconds_set(version, key):
    """Segundos (enteros, [t0, t1)) cubiertos por las playlists de una versión."""
    s = set()
    for pl in version.get(key, {}).get("playlists", []):
        for c in pl:
            s.update(range(int(math.floor(c["t0"])), int(math.ceil(c["t1"]))))
    return s


def iou(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def chapter_topics(version, doc):
    """Cada capítulo de full_chapters -> conjunto de unidades de su tópico (identidad del tópico)."""
    topics = {t["topic_id"]: set(t["shots"]) for t in doc["levels"]["default"]["topics"]}
    return [frozenset(topics.get(c["topic_id"], ())) for pl in version["full_chapters"]["playlists"] for c in pl]


def same_topics_frac(ref_ch, cand_ch, thr=0.9):
    """Fracción de capítulos ref cuyo tópico tiene un par en cand con Jaccard de unidades >= thr."""
    if not ref_ch:
        return 1.0
    ok = 0
    for a in ref_ch:
        best = max((len(a & b) / len(a | b) for b in cand_ch if a | b), default=0.0)
        ok += best >= thr
    return ok / len(ref_ch)


def e2e_metrics(ref_doc, ref_versions, cand_doc, cand_versions, check_versions):
    n = len(ref_doc["unit_times"])
    la, lb = topic_of_units(ref_doc, n), topic_of_units(cand_doc, min(n, len(cand_doc["unit_times"])))
    m = min(len(la), len(lb))
    la, lb = la[:m], lb[:m]
    da, db = ref_doc["levels"]["default"], cand_doc["levels"]["default"]
    rel = lambda a, b: abs(b - a) / a if a else (0.0 if b == a else float("inf"))  # noqa: E731
    out = {
        "n_units": int(m),
        "ari_unit_topic": float(adjusted_rand_score(la, lb)),
        "f1_boundaries_pm1": float(f1_tol(boundaries(la), boundaries(lb), 1)),
        "n_topics_ref": da["n_topics"], "n_topics_cand": db["n_topics"],
        "delta_n_topics_rel": float(rel(da["n_topics"], db["n_topics"])),
        "n_returning_ref": da["n_returning"], "n_returning_cand": db["n_returning"],
        "delta_returns_rel": float(rel(da["n_returning"], db["n_returning"])),
        "G_version_ref": bool(check_versions(ref_versions)["G_version"]),
        "G_version_cand": bool(check_versions(cand_versions)["G_version"]),
    }
    out["G_version_equal"] = out["G_version_ref"] == out["G_version_cand"]
    out["iou_highlights10pct"] = iou(seconds_set(ref_versions, "highlights10pct"), seconds_set(cand_versions, "highlights10pct"))
    out["iou_recap60"] = iou(seconds_set(ref_versions, "recap60"), seconds_set(cand_versions, "recap60"))
    out["chapters_same_topics_j09"] = same_topics_frac(chapter_topics(ref_versions, ref_doc), chapter_topics(cand_versions, cand_doc), 0.9)
    out["chapters_same_topics_j05"] = same_topics_frac(chapter_topics(ref_versions, ref_doc), chapter_topics(cand_versions, cand_doc), 0.5)
    thr = {"ari_unit_topic": 0.95, "f1_boundaries_pm1": 0.95, "iou_highlights10pct": 0.90, "iou_recap60": 0.90,
           "chapters_same_topics_j09": 0.95}
    ok = {k: out[k] >= v for k, v in thr.items()}
    ok["delta_n_topics_rel"] = out["delta_n_topics_rel"] <= 0.02
    ok["delta_returns_rel"] = out["delta_returns_rel"] <= 0.02
    ok["G_version_equal"] = out["G_version_equal"]
    out["pass"] = ok
    out["pass_all"] = all(ok.values())
    return out


def load_run(d):
    d = Path(d)
    return json.loads((d / "topic_map.json").read_text()), json.loads((d / "versions.json").read_text())
