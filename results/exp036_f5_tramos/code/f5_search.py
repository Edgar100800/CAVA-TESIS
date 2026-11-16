"""EXP-036 F5: búsqueda híbrida sobre el índice de f5_index.py.

Métodos (todos devuelven intervalos reales del film, en s y hms):
  bm25               SQLite FTS5 bm25() sobre el texto del brief (porter unicode61; consulta = OR de términos)
  bge                coseno BGE (consulta con instrucción bge-v1.5) contra el texto completo del documento
  hybrid             RRF k=60 sobre los rankings bm25 y bge (sin pesos ni normalización de scores)
  hybrid_rerank      top-20 de hybrid reordenado con 0.5*cos(doc) + 0.5*max cos(fragmento del brief)
  hybrid_rerank_loc  = hybrid_rerank, pero el intervalo devuelto se recorta a la evidencia citada por el
                     fragmento ganador (<=3 líneas más afines a la consulta), dentro de los spans del doc
  exp035b            réplica de CAVA_minimo/scripts/scene_search.py sobre su scene_index.npz (solo lectura):
                     BGE sin instrucción, max_length 256, niveles scene+block+topic de EXP-035
  exp035b_scene      igual, solo nivel `scene` de EXP-035 (briefs EXP-035 por tópico, intervalo envolvente)
  exp035b_noblock    igual, niveles scene+topic de EXP-035 (sin bloques VJudge crudos)
No hay cross-encoder local: el "reranker" es BGE por fragmentos (documentado en F5_BASELINE.md).

Uso:
  P=CAVA_minimo/.venv/bin/python
  $P -I exp036/f5/f5_search.py "Thor talks to his mother" --movie Avengers_Endgame --topk 5
  $P -I exp036/f5/f5_search.py "..." --method hybrid --levels scene,topic --json
  $P -I exp036/f5/f5_search.py --selftest
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f5_common import (BGE_QUERY_INSTRUCTION, CAVA, F5, MOVIES, clip, fts_query, hms, load_json,  # noqa: E402
                       merge)

METHODS = ["bm25", "bge", "hybrid", "hybrid_rerank", "hybrid_rerank_loc", "exp035b", "exp035b_scene",
           "exp035b_noblock"]
EXP035_LEVELS = {"exp035b": {"scene", "block", "topic"}, "exp035b_scene": {"scene"},
                 "exp035b_noblock": {"scene", "topic"}}
RRF_K = 60
N_CAND = 20
LOC_MAX_EV = 3
QUERY_LEN = 128   # tokens; consultas rellenadas a longitud fija (latencia estable). Truncaría consultas >~115 palabras


class F5Index:
    def __init__(self, index_dir=F5 / "index", movies=MOVIES, embedder=None, with_exp035=True):
        index_dir = Path(index_dir)
        self.docs, dv, cv, cd, ev, ed = [], [], [], [], [], []
        self.chunks, self.evl, self.offset = [], [], {}
        for mov in movies:
            meta = load_json(index_dir / f"{mov}.meta.json")
            z = np.load(index_dir / f"{mov}.npz")
            off, coff, eoff = len(self.docs), len(self.chunks), len(self.evl)
            self.offset[mov] = off
            self.docs += meta["docs"]
            self.chunks += [{**c, "doc": c["doc"] + off, "ev_rows": [r + eoff for r in c["ev_rows"]]}
                            for c in meta["chunks"]]
            self.evl += [{**e, "doc": e["doc"] + off} for e in meta["evlines"]]
            dv.append(z["doc_vecs"]); cv.append(z["chunk_vecs"]); ev.append(z["ev_vecs"])
            cd.append(z["chunk_doc"] + off); ed.append(z["ev_doc"] + off)
        self.doc_vecs, self.chunk_vecs, self.ev_vecs = np.concatenate(dv), np.concatenate(cv), np.concatenate(ev)
        self.chunk_doc, self.ev_doc = np.concatenate(cd), np.concatenate(ed)
        self.doc_chunks = [[] for _ in self.docs]
        for i, d in enumerate(self.chunk_doc):
            self.doc_chunks[d].append(i)
        self.doc_chunks = [np.array(x, np.int64) for x in self.doc_chunks]
        self.con = sqlite3.connect(f"file:{index_dir / 'bm25.sqlite'}?mode=ro", uri=True, check_same_thread=False)
        self.level = np.array([d["level"] for d in self.docs])
        self.movie = np.array([d["movie"] for d in self.docs])
        self.emb = embedder
        self.exp035 = {}
        if with_exp035:
            for mov in movies:
                f = CAVA / "outputs" / mov / "scene_index.npz"
                if f.exists():
                    z = np.load(f, allow_pickle=False)
                    self.exp035[mov] = (z["vecs"].astype(np.float32), json.loads(str(z["meta"])))

    # ------------------------------------------------------------ piezas
    def mask(self, movie, levels):
        m = np.isin(self.level, list(levels))
        if movie and movie != "all":
            m &= self.movie == movie
        return np.flatnonzero(m)

    def qvec(self, q, instruction=True):
        v = self.emb([(BGE_QUERY_INSTRUCTION if instruction else "") + q], max_length=QUERY_LEN, pad_fixed=True)[0]
        return v / (np.linalg.norm(v) + 1e-9)

    def bm25_rank(self, q, movie, levels):
        fq = fts_query(q)
        if not fq:
            return [], {}
        movs = MOVIES if not movie or movie == "all" else [movie]
        sql = (f"SELECT movie, idx, bm25(docs) FROM docs WHERE docs MATCH ? "
               f"AND movie IN ({','.join('?' * len(movs))}) AND level IN ({','.join('?' * len(levels))}) "
               f"ORDER BY bm25(docs) LIMIT 2000")
        rows = self.con.execute(sql, [fq, *movs, *levels]).fetchall()
        ids = [self.offset[m] + int(i) for m, i, _ in rows if m in self.offset]
        return ids, {self.offset[m] + int(i): -float(s) for m, i, s in rows if m in self.offset}

    def dense_rank(self, qv, cand):
        s = self.doc_vecs[cand] @ qv
        o = np.argsort(-s, kind="stable")
        return [int(cand[i]) for i in o], {int(cand[i]): float(s[i]) for i in o}

    @staticmethod
    def rrf(*rankings):
        sc = {}
        for r in rankings:
            for k, d in enumerate(r, 1):
                sc[d] = sc.get(d, 0.0) + 1.0 / (RRF_K + k)
        return sorted(sc, key=lambda d: -sc[d]), sc

    def best_chunk(self, d, qv):
        idx = self.doc_chunks[d]
        if len(idx) == 0:
            return None, 0.0
        s = self.chunk_vecs[idx] @ qv
        j = int(np.argmax(s))
        return int(idx[j]), float(s[j])

    def localize(self, d, c, qv):
        """Intervalo de la evidencia citada por el fragmento c (o, si no cita, la del doc), <=3 líneas."""
        doc = self.docs[d]
        rows = self.chunks[c]["ev_rows"] if c is not None else []
        if not rows:
            rows = list(np.flatnonzero(self.ev_doc == d))
        if not rows:
            return doc["spans"], []
        rows = np.array(rows, np.int64)
        if len(rows) > LOC_MAX_EV:
            rows = rows[np.argsort(-(self.ev_vecs[rows] @ qv))[:LOC_MAX_EV]]
        a = min(self.evl[r]["t0"] for r in rows)
        b = max(self.evl[r]["t1"] for r in rows)
        iv = clip([[a, b]], doc["spans"])
        return (iv or doc["spans"]), [self.evl[r]["id"] for r in rows]

    # ------------------------------------------------------------ API
    def search(self, q, movie="all", levels=("scene",), method="hybrid_rerank_loc", topk=5):
        t_start = time.perf_counter()
        if method.startswith("exp035b"):
            res = self.search_exp035(q, movie, topk, EXP035_LEVELS[method])
            return res, time.perf_counter() - t_start
        cand = self.mask(movie, levels)
        out = []
        if method == "bm25":
            ids, sc = self.bm25_rank(q, movie, levels)
            out = [(d, sc[d], None, None) for d in ids[:topk]]
        else:
            qv = self.qvec(q)
            dids, dsc = self.dense_rank(qv, cand)
            if method == "bge":
                out = [(d, dsc[d], None, None) for d in dids[:topk]]
            else:
                bids, _ = self.bm25_rank(q, movie, levels)
                fused, fsc = self.rrf(bids, dids)
                if method == "hybrid":
                    out = [(d, fsc[d], None, None) for d in fused[:topk]]
                else:
                    rer = []
                    for d in fused[:N_CAND]:
                        c, cs = self.best_chunk(d, qv)
                        rer.append((d, 0.5 * dsc[d] + 0.5 * cs, c, cs))
                    rer.sort(key=lambda x: -x[1])
                    out = rer[:topk]
        res = []
        for d, s, c, cs in out:
            doc = self.docs[d]
            iv, ev_ids = doc["spans"], []
            if method == "hybrid_rerank_loc":
                iv, ev_ids = self.localize(d, c, qv)
            res.append({"movie": doc["movie"], "level": doc["level"], "unit": doc["unit"], "score": round(s, 5),
                        "intervals": iv, "t0_hms": hms(iv[0][0]), "t1_hms": hms(iv[-1][1]),
                        "doc_t0_hms": doc["t0_hms"], "doc_t1_hms": doc["t1_hms"],
                        "best_fragment": self.chunks[c]["text"] if c is not None else None,
                        "evidence_used": ev_ids, "warnings": doc["warnings"],
                        "snippet": doc["text"][:300]})
        return res, time.perf_counter() - t_start

    def search_exp035(self, q, movie, topk, levels=frozenset({"scene", "block", "topic"})):
        v = self.emb([q], max_length=QUERY_LEN, pad_fixed=True)[0]   # como scene_search.py: sin instrucción
        v = v / (np.linalg.norm(v) + 1e-9)
        rows = []
        for mov in (MOVIES if not movie or movie == "all" else [movie]):
            if mov not in self.exp035:
                continue
            vecs, meta = self.exp035[mov]
            sims = vecs @ v
            n_mov = 0
            for i in np.argsort(-sims):
                m = meta[i]
                if m["level"] not in levels:
                    continue
                rows.append({"movie": mov, "level": "exp035_" + m["level"], "unit": str(m.get("topic_id")),
                             "score": round(float(sims[i]), 5), "intervals": [[m["t0"], m["t1"]]],
                             "t0_hms": m["t0_hms"], "t1_hms": m["t1_hms"], "doc_t0_hms": m["t0_hms"],
                             "doc_t1_hms": m["t1_hms"], "best_fragment": None, "evidence_used": [],
                             "warnings": [], "snippet": m["text"][:300]})
                n_mov += 1
                if n_mov >= topk:
                    break
        rows.sort(key=lambda r: -r["score"])
        return rows[:topk]


def load(device="cpu", threads=8, **kw):
    """threads=8: esta CPU (Core Ultra 9 285K) tiene 8 núcleos P + 16 E sin SMT. Con 24 hilos OpenMP
    el embebido de la consulta sufría esperas de ~1.3 s (barreras entre núcleos P/E); con 8 es estable."""
    from f5_common import Bge
    return F5Index(embedder=Bge(device=device, threads=threads), **kw)


def selftest():
    """Prueba sintética sin modelo: intervalos, RRF, BM25 FTS5, rerank y localización."""
    import tempfile
    from f5_common import hit, inter_len, iou
    assert inter_len([[0, 10]], [[5, 20]]) == 5 and abs(iou([[0, 10]], [[5, 15]]) - 1 / 3) < 1e-9
    assert hit([[0, 10]], [[9, 30]]) and not hit([[0, 10]], [[9.5, 30]])
    assert iou([[0, 10], [20, 30]], [[0, 10]]) == 0.5 and merge([[5, 9], [0, 6]]) == [[0, 9]]
    order, _ = F5Index.rrf([1, 2, 3], [3, 1, 2])
    assert order[0] == 1, order

    dim = 8
    rng = np.random.default_rng(0)
    basis = np.eye(dim, dtype=np.float32)
    vocab = {"thor": 0, "hammer": 1, "rocket": 2, "raccoon": 3, "mother": 4, "elevator": 5}

    class FakeEmb:
        def __call__(self, texts, max_length=None, bs=32, pad_fixed=False):
            out = []
            for t in texts:
                v = sum((basis[i] for w, i in vocab.items() if w in t.lower()), np.zeros(dim, np.float32))
                v = v + 0.01 * rng.normal(size=dim).astype(np.float32)
                out.append(v / (np.linalg.norm(v) + 1e-9))
            return np.array(out, np.float32)

    emb = FakeEmb()
    docs = [
        {"movie": "Avengers_Endgame", "level": "scene", "unit": "S0", "t0": 0, "t1": 100, "t0_hms": hms(0),
         "t1_hms": hms(100), "spans": [[0, 100]], "warnings": [], "doc": 0,
         "text": "Actions: Thor lifts the hammer. Setting: hall."},
        {"movie": "Avengers_Endgame", "level": "scene", "unit": "S1", "t0": 100, "t1": 300, "t0_hms": hms(100),
         "t1_hms": hms(300), "spans": [[100, 300]], "warnings": [], "doc": 1,
         "text": "Actions: Rocket the raccoon talks to Thor about his mother."},
    ]
    chunks = [{"doc": 0, "section": "actions", "text": "Thor lifts the hammer", "evidence": ["E1"], "ev_rows": [0]},
              {"doc": 1, "section": "actions", "text": "Rocket raccoon talks", "evidence": ["E1"], "ev_rows": [1]},
              {"doc": 1, "section": "states", "text": "Thor misses his mother", "evidence": ["E2"], "ev_rows": [2]}]
    evl = [{"doc": 0, "id": "E1", "kind": "vision", "t0": 40, "t1": 80, "text": "Thor hammer"},
           {"doc": 1, "id": "E1", "kind": "dialogue", "t0": 110, "t1": 115, "text": "rocket raccoon"},
           {"doc": 1, "id": "E2", "kind": "dialogue", "t0": 250, "t1": 260, "text": "my mother dies today"}]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "Avengers_Endgame.meta.json").write_text(json.dumps({"docs": docs, "chunks": chunks, "evlines": evl}))
        np.savez(td / "Avengers_Endgame.npz", doc_vecs=emb([d["text"] for d in docs]),
                 chunk_vecs=emb([c["text"] for c in chunks]), chunk_doc=np.array([0, 1, 1], np.int32),
                 ev_vecs=emb([e["text"] for e in evl]), ev_doc=np.array([0, 1, 1], np.int32))
        con = sqlite3.connect(td / "bm25.sqlite")
        con.execute('CREATE VIRTUAL TABLE docs USING fts5(doc_key UNINDEXED, movie UNINDEXED, level UNINDEXED, '
                    'idx UNINDEXED, text, tokenize="porter unicode61")')
        con.executemany("INSERT INTO docs VALUES (?,?,?,?,?)",
                        [(d["unit"], d["movie"], d["level"], d["doc"], d["text"]) for d in docs])
        con.commit(); con.close()
        ix = F5Index(td, movies=["Avengers_Endgame"], embedder=emb, with_exp035=False)
        r, _ = ix.search("hammers of Thor", movie="Avengers_Endgame", method="bm25")
        assert r[0]["unit"] == "S0", r          # porter: hammers -> hammer
        r, _ = ix.search("Thor mother", movie="Avengers_Endgame", method="hybrid_rerank_loc")
        assert r[0]["unit"] == "S1" and r[0]["intervals"] == [[250.0, 260.0]], r
        for m in ("bge", "hybrid", "hybrid_rerank"):
            r, _ = ix.search("Thor mother", movie="Avengers_Endgame", method=m)
            assert r[0]["unit"] == "S1" and r[0]["intervals"] == [[100, 300]], (m, r)
        ix.con.close()
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--movie", default="all")
    ap.add_argument("--levels", default="scene")
    ap.add_argument("--method", choices=METHODS, default="hybrid_rerank_loc")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.query:
        ap.error("query requerida")
    t0 = time.perf_counter()
    ix = load(device=a.device, threads=a.threads)
    t_load = time.perf_counter() - t0
    res, dt = ix.search(a.query, a.movie, tuple(a.levels.split(",")), a.method, a.topk)
    if a.json:
        print(json.dumps({"query": a.query, "method": a.method, "latency_s": round(dt, 4),
                          "load_s": round(t_load, 2), "results": res}, ensure_ascii=False, indent=1))
        return
    print(f"QUERY {a.query!r}  method={a.method} levels={a.levels}  latency={dt * 1000:.0f} ms (load {t_load:.1f}s)")
    for k, r in enumerate(res, 1):
        print(f"#{k} {r['movie']} [{r['level']} {r['unit']}] {r['t0_hms']}-{r['t1_hms']} "
              f"(doc {r['doc_t0_hms']}-{r['doc_t1_hms']}) score={r['score']:.4f}")
        if r["best_fragment"]:
            print(f"    fragment: {r['best_fragment'][:160]}  ev={r['evidence_used']}")
        print(f"    {r['snippet'][:200].replace(chr(10), ' | ')}")


if __name__ == "__main__":
    main()
