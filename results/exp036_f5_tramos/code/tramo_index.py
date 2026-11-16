"""EXP-036 F5 piloto de tramos: índice = índice congelado + nivel `tramo` (no toca exp036/f5/index/).

  index_add/      escenas + tópicos + fine (copiados) + tramos de las escenas seleccionadas
  index_replace/  igual, pero los documentos de escena seleccionados pasan a level="scene_replaced"
                  (quedan fuera de --levels scene,topic,tramo: los tramos los sustituyen)
Mismos campos, texto, fragmentos, evidencia -> tiempo y BGE que f5_index.py. Los ids de evidencia de cada
tramo se verifican contra f1_briefs.evidence_lines (assert).

Uso: CAVA_minimo/.venv/bin/python -I exp036/f5/tramos/tramo_index.py [--device cpu]
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from f5_common import (CAVA, EXP, F5, MOVIES, Bge, brief_items, brief_text, evidence_rows, load_json,  # noqa: E402
                       names_of)
from f5_index import build_fts  # noqa: E402

sys.path.insert(0, str(EXP / "scripts"))
from f1_briefs import evidence_lines  # noqa: E402

FROZEN = F5 / "index"


def tramo_docs(mov, briefs_dir=HERE):
    md = CAVA / "outputs" / mov
    st = load_json(md / "work/state.json")
    units = [tuple(u) for u in st["units"]]
    asr = st.get("asr_segments", [])
    summ = load_json(md / "work/summaries.json")
    briefs = load_json(Path(briefs_dir) / f"briefs_tramos_{mov}.json")
    mixed_of = {f"S{s['scene_id']}": frozenset(s["mixed_blocks"])
                for s in load_json(EXP / "outputs" / mov / "escenas.json")["scenes"]}
    docs, chunks, evl, skipped = [], [], [], []
    for uid in sorted(briefs):
        rec = briefs[uid]
        if rec.get("status") != "ok":
            skipped.append(uid)
            continue
        t0, t1 = rec["t0"], rec["t1"]
        mixed = mixed_of[rec["scene"]]
        rows = evidence_rows([[t0, t1]], units, summ, asr, mixed)
        assert [r["line"] for r in rows] == evidence_lines([[t0, t1]], units, summ, asr, mixed)
        assert len(rows) == rec["n_evidence"], uid
        byid = {r["id"]: r for r in rows}
        brief = rec["brief"]
        items = brief_items(brief)
        d = len(docs)
        cited = sorted({e for _, _, ev in items for e in ev if e in byid}, key=lambda e: int(e[1:]))
        docs.append({"movie": mov, "level": "tramo", "unit": uid, "parent_scene": rec["scene"], "t0": t0, "t1": t1,
                     "t0_hms": rec["t0_hms"], "t1_hms": rec["t1_hms"], "dur": t1 - t0, "doc": d,
                     "spans": [[t0, t1]], "has_brief": True, "names": names_of(brief),
                     "warnings": rec["problems"]["warn"], "n_evidence": rec["n_evidence"], "evidence_ids": cited,
                     "uncertain": brief.get("uncertain") or [], "text": brief_text(brief)})
        loc = {}
        for e in cited:
            r = byid[e]
            loc[e] = len(evl)
            evl.append({"doc": d, "id": e, "kind": r["kind"], "t0": r["t0"], "t1": r["t1"], "text": r["text"]})
        for sec, t, ev in items:
            ev = [e for e in ev if e in byid]
            chunks.append({"doc": d, "section": sec, "text": t, "evidence": ev, "ev_rows": [loc[e] for e in ev]})
    return docs, chunks, evl, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--briefs-dir", default=str(HERE), help="carpeta con briefs_tramos_<mov>.json")
    ap.add_argument("--out-root", default=str(HERE), help="se escriben <out-root>/index_add y/o index_replace")
    ap.add_argument("--variants", default="index_add,index_replace")
    a = ap.parse_args()
    bge = Bge(device=a.device, threads=8)
    built = {}
    for mov in MOVIES:
        meta = load_json(FROZEN / f"{mov}.meta.json")
        z = np.load(FROZEN / f"{mov}.npz")
        td, tc, te, skipped = tramo_docs(mov, a.briefs_dir)
        off, coff, eoff = len(meta["docs"]), len(meta["chunks"]), len(meta["evlines"])
        for d in td:
            d["doc"] += off
        for c in tc:
            c["doc"] += off
            c["ev_rows"] = [r + eoff for r in c["ev_rows"]]
        for e in te:
            e["doc"] += off
        dv = bge([d["text"] for d in td], max_length=512)
        cv = bge([c["text"] for c in tc], max_length=256)
        ev = bge([e["text"] for e in te], max_length=256)
        arrays = dict(doc_vecs=np.concatenate([z["doc_vecs"], dv]), chunk_vecs=np.concatenate([z["chunk_vecs"], cv]),
                      chunk_doc=np.concatenate([z["chunk_doc"], np.array([c["doc"] for c in tc], np.int32)]),
                      ev_vecs=np.concatenate([z["ev_vecs"], ev]),
                      ev_doc=np.concatenate([z["ev_doc"], np.array([e["doc"] for e in te], np.int32)]))
        new = {**meta, "docs": meta["docs"] + td, "chunks": meta["chunks"] + tc, "evlines": meta["evlines"] + te,
               "tramo_pilot": {"n_tramos": len(td), "skipped_not_ok": skipped, "chunks": len(tc), "evlines": len(te),
                               "frozen_index": str(FROZEN)}}
        built[mov] = (new, arrays)
        print(f"[tramo index] {mov}: +{len(td)} tramos, +{len(tc)} fragmentos, +{len(te)} evidencias; "
              f"omitidos {skipped}", flush=True)
    # escenas con tramos (en el piloto, exactamente las 4 pre-registradas)
    sel = {(m, d["parent_scene"]) for m, (meta, _) in built.items() for d in meta["docs"] if d["level"] == "tramo"}
    for variant in a.variants.split(","):
        out = Path(a.out_root) / variant
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        all_docs = []
        for mov, (meta, arrays) in built.items():
            meta = json.loads(json.dumps(meta))
            if variant == "index_replace":
                for d in meta["docs"]:
                    if d["level"] == "scene" and (mov, d["unit"]) in sel:
                        d["level"] = "scene_replaced"
                meta["tramo_pilot"]["replaced"] = sorted(u for m, u in sel if m == mov)
            np.savez_compressed(out / f"{mov}.npz", **arrays)
            (out / f"{mov}.meta.json").write_text(json.dumps(meta, ensure_ascii=False))
            all_docs += meta["docs"]
        build_fts(all_docs, out / "bm25.sqlite")
        print(f"[tramo index] {variant} -> {out} ({len(all_docs)} docs)", flush=True)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    main()
