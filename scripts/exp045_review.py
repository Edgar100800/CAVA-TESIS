"""EXP-045-Q: revisión humana a ciegas de textos LLM (20 pares por pista: etiquetas FP8 / vjudge vLLM).

Preparar: python scripts/exp045_review.py prepare --pairs results/exp045_q/human_review_answer_key/llm_pairs_all.json --out results/exp045_q/human_review/labels --track labels
  -> review.html (formulario autocontenido), review.csv (respuestas en blanco); la clave se escribe aparte en ../human_review_answer_key/<pista>.csv (NO entregar)
Puntuar:  python scripts/exp045_review.py score --responses review_respondido.csv --key results/exp045_q/human_review_answer_key/labels.csv
Muestra aleatoria con semilla fija (45) sobre TODOS los pares (incluye pares idénticos, como en la población real);
el orden de los pares y cuál texto es A/B se aleatorizan; la persona no ve qué variante es cuál.
Regla registrada: >= 18 de 20 pares "equivalentes".
"""
import argparse
import csv
import html
import json
import random
from pathlib import Path

SEED = 45


def prepare(a):
    pairs = json.loads(Path(a.pairs).read_text())
    rng = random.Random(SEED)
    items = [(a.track, p) for p in rng.sample(pairs[a.track], 20)]
    rows, key = [], []
    for i, (track, p) in enumerate(items, 1):
        ref_first = rng.random() < 0.5
        A, B = (p["ref"], p["fast"]) if ref_first else (p["fast"], p["ref"])
        rows.append({"id": i, "tipo": "resumen de escena" if track == "vjudge" else "etiqueta de tópico", "texto_A": A, "texto_B": B})
        key.append({"id": i, "track": track, "video": p["video"], "ref_is_A": ref_first,
                    "identical": p["ref"].strip() == p["fast"].strip(), "locator": p.get("block", p.get("key"))})
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "review.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, ["id", "tipo", "texto_A", "texto_B", "equivalentes (si/no)", "comentario"])
        w.writeheader()
        for r in rows:
            w.writerow(r | {"equivalentes (si/no)": "", "comentario": ""})
    keydir = out.parent.parent / "human_review_answer_key"  # clave FUERA de human_review/ para no desenmascarar al revisor
    keydir.mkdir(parents=True, exist_ok=True)
    with open(keydir / f"{a.track}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, list(key[0]))
        w.writeheader()
        w.writerows(key)
    cards = "".join(
        f"<div class=c><b>#{r['id']}</b> <i>{html.escape(r['tipo'])}</i><p><b>A:</b> {html.escape(r['texto_A'])}</p>"
        f"<p><b>B:</b> {html.escape(r['texto_B'])}</p>"
        f"<label><input type=radio name=q{r['id']} value=si> equivalentes</label> "
        f"<label><input type=radio name=q{r['id']} value=no> no equivalentes</label> "
        f"<input name=n{r['id']} placeholder='comentario (opcional)' size=50></div>" for r in rows)
    (out / "review.html").write_text(f"""<!doctype html><meta charset=utf-8><title>Revisión a ciegas EXP-045-Q</title>
<style>body{{font:15px sans-serif;max-width:900px;margin:2em auto}}.c{{border:1px solid #ccc;padding:.6em 1em;margin:1em 0;border-radius:6px}}</style>
<h2>Revisión a ciegas (20 pares)</h2>
<p>Para cada par, ¿los dos textos <b>dicen lo mismo en lo esencial</b> (mismas personas, lugar y hecho/tema; sin contradicciones ni datos
inventados distintos)? Diferencias de redacción no importan. No sabrá cuál texto viene de qué sistema.</p>
{cards}
<button onclick="exp()">Descargar respuestas (CSV)</button>
<script>
function exp(){{var rows=[["id","equivalentes (si/no)","comentario"]];
for(var i=1;i<=20;i++){{var r=document.querySelector('input[name=q'+i+']:checked');
rows.push([i,r?r.value:"",(document.querySelector('input[name=n'+i+']').value||"").replace(/"/g,"'")]);}}
var csv=rows.map(function(r){{return r.map(function(x){{return '"'+x+'"'}}).join(',')}}).join('\\n');
var a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));a.download='review_respondido.csv';a.click();}}
</script>""")
    print(f"preparados {len(rows)} pares en {out}")


def score(a):
    key = {int(r["id"]): r for r in csv.DictReader(open(a.key))}
    resp = {}
    for r in csv.DictReader(open(a.responses)):
        resp[int(r["id"])] = (r.get("equivalentes (si/no)") or "").strip().lower()
    eq = {t: [0, 0] for t in ("vjudge", "labels")}
    for i, k in key.items():
        eq[k["track"]][1] += 1
        eq[k["track"]][0] += resp.get(i) in ("si", "sí", "yes", "s")
    total = sum(v[0] for v in eq.values())
    print(json.dumps({"equivalentes": total, "de": 20, "por_pista": eq, "pasa_ge_18": total >= 18}, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--pairs", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--track", choices=("labels", "vjudge"), required=True)
    s = sub.add_parser("score")
    s.add_argument("--responses", required=True)
    s.add_argument("--key", required=True)
    a = ap.parse_args()
    {"prepare": prepare, "score": score}[a.cmd](a)
