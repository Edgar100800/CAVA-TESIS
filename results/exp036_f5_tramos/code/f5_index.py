"""EXP-036 F5: construye el índice híbrido (BM25 FTS5 + BGE) por película.

Niveles (campo `level`):
  scene : escenas F2 (outputs/<mov>/escenas.json) + brief F1 de escena (briefs_f1_escenas.json, status ok)
  topic : tópicos default (topic_map.json levels.default) con brief F1 si existe (>=30 s) + etiqueta
  fine  : tópicos fine (levels.fine): solo etiqueta y spans (F1 no generó briefs fine)

Fragmentos (para rerank y localización): cada ítem del brief (personaje/acción/estado/ambiente/
desarrollo) con sus ids de evidencia; cada id se traduce a [t0, t1] reconstruyendo la evidencia F1
exactamente (se verifica contra f1_briefs.evidence_lines). Las líneas de evidencia citadas se
embeben también, para recortar el intervalo al fragmento citado más afín a la consulta.

Escribe (solo bajo exp036/f5/index/):
  <mov>.npz        doc_vecs, chunk_vecs, chunk_doc, ev_vecs, ev_doc
  <mov>.meta.json  docs / chunks / evlines + procedencia
  bm25.sqlite      tabla FTS5 `docs` (porter unicode61) con ambas películas

Uso:
  P=CAVA_minimo/.venv/bin/python
  $P -I exp036/f5/f5_index.py [--movies Avengers_Endgame Spider_Man] [--device cpu|cuda]
  $P -I exp036/f5/f5_index.py --out exp036/f5/index_f3 --briefs-escenas 'exp036/outputs/{mov}/briefs_f3_escenas.json'
  (F3 debe conservar el esquema y la numeración de evidencia de f1_briefs.evidence_lines; si no, falla el assert.)
"""
import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f5_common import (CAVA, EXP, F5, MOVIES, Bge, brief_items, brief_text, evidence_rows, hms,  # noqa: E402
                       load_json, merge, names_of)

sys.path.insert(0, str(EXP / "scripts"))
from f1_briefs import evidence_lines  # noqa: E402  (solo lectura: verificación de ids)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def build_movie(mov, bge, out_dir, escenas_tpl=None, briefs_escenas_tpl=None):
    md = CAVA / "outputs" / mov
    od = EXP / "outputs" / mov
    src = {"escenas": Path(escenas_tpl.format(mov=mov)) if escenas_tpl else od / "escenas.json",
           "briefs_escenas": Path(briefs_escenas_tpl.format(mov=mov)) if briefs_escenas_tpl
           else od / "briefs_f1_escenas.json",
           "briefs_topicos": od / "briefs_f1_topicos.json", "topic_map": md / "topic_map.json",
           "state": md / "work/state.json", "summaries": md / "work/summaries.json"}
    st = load_json(src["state"])
    units = [tuple(u) for u in st["units"]]
    asr = st.get("asr_segments", [])
    summ = load_json(src["summaries"])
    esc = load_json(src["escenas"])["scenes"]
    be = load_json(src["briefs_escenas"])
    bt = load_json(src["briefs_topicos"])
    tm = load_json(src["topic_map"])

    docs, chunks, evl = [], [], []
    skipped = []

    def add_brief_doc(base, spans, rec, mixed=frozenset(), extra_text=""):
        d = len(docs)
        brief = rec["brief"]
        rows = evidence_rows(spans, units, summ, asr, mixed)
        ref = evidence_lines(spans, units, summ, asr, mixed)
        assert [r["line"] for r in rows] == ref and len(rows) == rec["n_evidence"], (mov, base["unit"])
        byid = {r["id"]: r for r in rows}
        items = brief_items(brief)
        cited = sorted({e for _, _, ev in items for e in ev if e in byid}, key=lambda e: int(e[1:]))
        txt = brief_text(brief) + (f"\n{extra_text}" if extra_text else "")
        docs.append({**base, "doc": d, "spans": merge(spans), "has_brief": True,
                     "names": names_of(brief), "warnings": rec["problems"]["warn"],
                     "n_evidence": rec["n_evidence"], "evidence_ids": cited,
                     "uncertain": brief.get("uncertain") or [], "text": txt})
        ev_local = {}
        for e in cited:
            r = byid[e]
            ev_local[e] = len(evl)
            evl.append({"doc": d, "id": e, "kind": r["kind"], "t0": r["t0"], "t1": r["t1"], "text": r["text"]})
        for sec, t, ev in items:
            ev = [e for e in ev if e in byid]
            chunks.append({"doc": d, "section": sec, "text": t, "evidence": ev,
                           "ev_rows": [ev_local[e] for e in ev]})

    for s in esc:
        uid = f"S{s['scene_id']}"
        rec = be.get(uid)
        if not rec or rec.get("status") != "ok":
            skipped.append(uid)
            continue
        base = {"movie": mov, "level": "scene", "unit": uid, "scene_id": s["scene_id"],
                "t0": s["t0"], "t1": s["t1"], "t0_hms": hms(s["t0"]), "t1_hms": hms(s["t1"]),
                "dur": s["dur"], "topic_dominante": s["topic_dominante"],
                "pureza_topico": round(s["pureza_topico"], 3), "mixed": bool(s["mixed_blocks"]),
                "n_mixed_blocks": len(s["mixed_blocks"])}
        add_brief_doc(base, [[s["t0"], s["t1"]]], rec, frozenset(s["mixed_blocks"]))

    for t in tm["levels"]["default"]["topics"]:
        sp = merge(t["spans"])
        base = {"movie": mov, "level": "topic", "unit": f"T{t['topic_id']}", "topic_id": t["topic_id"],
                "t0": sp[0][0], "t1": sp[-1][1], "t0_hms": hms(sp[0][0]), "t1_hms": hms(sp[-1][1]),
                "dur": t["duration_s"], "n_spans": len(sp), "label": t.get("label") or ""}
        rec = bt.get(str(t["topic_id"]))
        lab = f"Label: {t.get('label')}" if t.get("label") else ""
        if rec and rec.get("status") == "ok":
            add_brief_doc(base, sp, rec, extra_text=lab)
        else:
            d = len(docs)
            docs.append({**base, "doc": d, "spans": sp, "has_brief": False, "names": [], "warnings": [],
                         "n_evidence": 0, "evidence_ids": [], "uncertain": [], "text": t.get("label") or ""})
            chunks.append({"doc": d, "section": "label", "text": t.get("label") or "", "evidence": [], "ev_rows": []})

    for t in tm["levels"]["fine"]["topics"]:
        sp = merge(t["spans"])
        d = len(docs)
        docs.append({"movie": mov, "level": "fine", "unit": f"F{t['topic_id']}", "topic_id": t["topic_id"],
                     "t0": sp[0][0], "t1": sp[-1][1], "t0_hms": hms(sp[0][0]), "t1_hms": hms(sp[-1][1]),
                     "dur": t["duration_s"], "n_spans": len(sp), "label": t.get("label") or "",
                     "doc": d, "spans": sp, "has_brief": False, "names": [], "warnings": [], "n_evidence": 0,
                     "evidence_ids": [], "uncertain": [], "text": t.get("label") or ""})
        chunks.append({"doc": d, "section": "label", "text": t.get("label") or "", "evidence": [], "ev_rows": []})

    t0 = time.time()
    doc_vecs = bge([d["text"] for d in docs], max_length=512)
    chunk_vecs = bge([c["text"] for c in chunks], max_length=256)
    ev_vecs = bge([e["text"] for e in evl], max_length=256)
    t_emb = time.time() - t0
    ntok = [bge.n_tokens(d["text"]) for d in docs if d["level"] == "scene"]

    np.savez_compressed(out_dir / f"{mov}.npz", doc_vecs=doc_vecs, chunk_vecs=chunk_vecs,
                        chunk_doc=np.array([c["doc"] for c in chunks], np.int32),
                        ev_vecs=ev_vecs, ev_doc=np.array([e["doc"] for e in evl], np.int32))
    lv = {k: sum(d["level"] == k for d in docs) for k in ("scene", "topic", "fine")}
    meta = {"movie": mov, "built": time.strftime("%Y-%m-%d %H:%M:%S"), "bge": "BAAI/bge-base-en-v1.5 (CLS+L2)",
            "doc_max_length": 512, "chunk_max_length": 256,
            "sources": {k: {"path": str(v.relative_to(CAVA.parent)), "sha256_16": sha(v)} for k, v in src.items()},
            "counts": {**lv, "chunks": len(chunks), "evlines": len(evl), "scenes_skipped_not_ok": skipped},
            "scene_doc_tokens": {"median": int(np.median(ntok)), "max": int(max(ntok)),
                                 "n_over_512": int(sum(n > 512 for n in ntok))},
            "embed_seconds": round(t_emb, 1),
            "docs": docs, "chunks": chunks, "evlines": evl}
    (out_dir / f"{mov}.meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    print(f"[F5 index] {mov}: {lv} chunks={len(chunks)} evlines={len(evl)} "
          f"scene tokens median={meta['scene_doc_tokens']['median']} max={meta['scene_doc_tokens']['max']} "
          f">512={meta['scene_doc_tokens']['n_over_512']} embed={t_emb:.1f}s skipped={skipped}", flush=True)
    return docs


def build_fts(all_docs, path):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.execute('CREATE VIRTUAL TABLE docs USING fts5(doc_key UNINDEXED, movie UNINDEXED, level UNINDEXED, '
                'idx UNINDEXED, text, tokenize="porter unicode61")')
    con.executemany("INSERT INTO docs(doc_key, movie, level, idx, text) VALUES (?,?,?,?,?)",
                    [(f"{d['movie']}:{d['unit']}", d["movie"], d["level"], d["doc"], d["text"]) for d in all_docs])
    con.commit()
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--movies", nargs="+", default=MOVIES)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--out", default=str(F5 / "index"))
    # Para enchufar F2 calibrado o briefs F3 sin tocar código: plantillas con {mov}. Usar otro --out.
    ap.add_argument("--escenas", help="p. ej. exp036/outputs/{mov}/escenas_calibradas.json")
    ap.add_argument("--briefs-escenas", help="p. ej. exp036/outputs/{mov}/briefs_f3_escenas.json")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    bge = Bge(device=a.device)
    for mov in a.movies:
        build_movie(mov, bge, out, a.escenas, a.briefs_escenas)
    # FTS se reconstruye con todas las películas indexadas en out/, no solo las de esta llamada
    all_docs = [d for m in sorted(out.glob("*.meta.json")) for d in load_json(m)["docs"]]
    build_fts(all_docs, out / "bm25.sqlite")
    print(f"[F5 index] FTS5 -> {out / 'bm25.sqlite'} ({len(all_docs)} docs)")


if __name__ == "__main__":
    main()
