"""EXP-036 F5: plantilla de revisión humana de consultas y conversión a conjunto gold.

  template : JSON provisional -> CSV de revisión (filas provisionales + filas vacías para consultas nuevas)
  to-gold  : CSV revisado -> JSON con status "gold_reviewed" SOLO con filas marcadas keep=Y/EDIT y con
             intervalo verificado en el MP4 (reviewer + ref_verified_on_video=Y). Las demás se descartan.

Reglas para el revisor (también en la cabecera de F5_BASELINE.md):
  - Mirar el MP4 de la ventana test (01:10:00-01:35:00). No mirar resultados del sistema ni los briefs F1.
  - keep: Y (vale tal cual) / EDIT (corregir texto o intervalo en las columnas reviewer_*) / N (descartar).
  - El intervalo de referencia es el tramo donde el evento ocurre en pantalla, en hh:mm:ss.
  - Filas NEW: consultas nuevas escritas por el revisor (qid libre, p. ej. A31).

Uso:
  P=CAVA_minimo/.venv/bin/python
  $P -I exp036/f5/f5_queries.py template --queries exp036/f5/queries/queries_provisional_v0.json \
      --out exp036/f5/queries/review_template_v0.csv
  $P -I exp036/f5/f5_queries.py to-gold --csv <revisado.csv> --out exp036/f5/queries/queries_gold_v1.json
  $P -I exp036/f5/f5_queries.py --selftest
"""
import argparse
import csv
import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f5_common import hms, parse_hms  # noqa: E402

COLS = ["qid", "movie", "type", "query", "ref_t0_hms", "ref_t1_hms", "ref2_t0_hms", "ref2_t1_hms", "source",
        "keep", "reviewer_query", "reviewer_ref_t0_hms", "reviewer_ref_t1_hms", "reviewer_ref2_t0_hms",
        "reviewer_ref2_t1_hms", "ref_verified_on_video", "reviewer", "notes"]
TYPES = {"entity", "action", "place", "state", "dialogue"}


def template(qs, n_new=10):
    rows = []
    for q in qs["queries"]:
        r = {c: "" for c in COLS}
        r.update(qid=q["qid"], movie=q["movie"], type=q["type"], query=q["query"], source=q.get("source", ""),
                 ref_t0_hms=hms(q["ref"][0][0]), ref_t1_hms=hms(q["ref"][0][1]))
        if len(q["ref"]) > 1:
            r.update(ref2_t0_hms=hms(q["ref"][1][0]), ref2_t1_hms=hms(q["ref"][1][1]))
        rows.append(r)
    for mov in sorted({q["movie"] for q in qs["queries"]}):
        for i in range(n_new):
            r = {c: "" for c in COLS}
            r.update(qid=f"NEW_{mov[:1]}{i + 1:02d}", movie=mov, keep="NEW")
            rows.append(r)
    return rows


def to_gold(rows):
    out, dropped = [], []
    for r in rows:
        keep = (r.get("keep") or "").strip().upper()
        if keep not in {"Y", "EDIT", "NEW"} or (r.get("ref_verified_on_video") or "").strip().upper() != "Y" \
                or not (r.get("reviewer") or "").strip():
            dropped.append(r["qid"])
            continue
        q = (r.get("reviewer_query") or "").strip() or (r.get("query") or "").strip()
        pairs = [("reviewer_ref_t0_hms", "reviewer_ref_t1_hms"), ("reviewer_ref2_t0_hms", "reviewer_ref2_t1_hms")]
        if not (r.get("reviewer_ref_t0_hms") or "").strip():
            pairs = [("ref_t0_hms", "ref_t1_hms"), ("ref2_t0_hms", "ref2_t1_hms")]
        ref = [[parse_hms(r[a]), parse_hms(r[b])] for a, b in pairs if (r.get(a) or "").strip()]
        typ = (r.get("type") or "").strip()
        if not q or not ref or any(b <= a for a, b in ref) or typ not in TYPES:
            dropped.append(r["qid"])
            continue
        out.append({"qid": r["qid"], "movie": r["movie"], "type": typ, "query": q, "ref": ref,
                    "source": "human review: " + (r.get("reviewer") or "").strip(), "notes": r.get("notes", "")})
    return out, dropped


def selftest():
    qs = {"queries": [{"qid": "A01", "movie": "M", "type": "action", "query": "q", "ref": [[60, 90], [100, 110]]}]}
    rows = template(qs, n_new=1)
    assert rows[0]["ref_t0_hms"] == "00:01:00" and rows[0]["ref2_t1_hms"] == "00:01:50" and rows[1]["keep"] == "NEW"
    buf = io.StringIO()
    w = csv.DictWriter(buf, COLS)
    w.writeheader()
    rows[0].update(keep="EDIT", reviewer_ref_t0_hms="00:01:05", reviewer_ref_t1_hms="00:01:20",
                   ref_verified_on_video="Y", reviewer="ann1")
    w.writerows(rows)
    gold, dropped = to_gold(list(csv.DictReader(io.StringIO(buf.getvalue()))))
    assert gold == [{"qid": "A01", "movie": "M", "type": "action", "query": "q", "ref": [[65.0, 80.0]],
                     "source": "human review: ann1", "notes": ""}], gold
    assert dropped == ["NEW_M01"]
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["template", "to-gold"])
    ap.add_argument("--queries")
    ap.add_argument("--csv")
    ap.add_argument("--out")
    ap.add_argument("--n-new", type=int, default=10)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.cmd == "template":
        rows = template(json.loads(Path(a.queries).read_text()), a.n_new)
        with open(a.out, "w", newline="") as fh:
            w = csv.DictWriter(fh, COLS)
            w.writeheader()
            w.writerows(rows)
        print(f"[F5 queries] plantilla -> {a.out} ({len(rows)} filas)")
    elif a.cmd == "to-gold":
        gold, dropped = to_gold(list(csv.DictReader(open(a.csv))))
        doc = {"name": "EXP-036 F5 reviewed query set", "status": "gold_reviewed",
               "built": time.strftime("%Y-%m-%d %H:%M:%S"), "from_csv": a.csv, "dropped": dropped, "queries": gold}
        Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        print(f"[F5 queries] gold -> {a.out}: {len(gold)} consultas, {len(dropped)} descartadas")
    else:
        ap.error("cmd requerido")


if __name__ == "__main__":
    main()
