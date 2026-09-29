"""G-enlace: hoja de revisión humana de enlaces no contiguos (≥ 20 casos).

Muestrea, de los mapas de tópicos (nivel default), pares (aparición temprana,
aparición posterior) del MISMO tópico separados por ≥ --min-gap shots, uno por
tópico y a lo sumo --per-film por película, con semilla fija. Para cada caso:
tiempos, resumen VJudge de cada lado, keyframes y columnas vacías para el
veredicto (mismo hilo sí/no/dudoso + nota). El cast NO se muestra: el revisor
juzga a ciegas.

Salida local (frames de películas comerciales, no se publica):
  <out>/review.html · <out>/review.csv · <out>/cases.json
"""
import argparse
import csv
import html
import json
import random
from pathlib import Path

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")


def summary_at(sums, shot):
    for u in sums:
        if u["lo"] <= shot < u["hi"]:
            return u["summary"]
    return ""


def keyframe(tt, shot):
    for j in (1, 0, 2):
        p = MN / "240P_frames" / tt / f"shot_{shot:04d}_img_{j}.jpg"
        if p.exists():
            return str(p)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", default="data/topic_maps")
    ap.add_argument("--summary-dir", default="data/vjudge_ledger")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--per-film", type=int, default=2)
    ap.add_argument("--min-gap", type=int, default=80)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--out", default="data/review_g_enlace")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pool = []
    for f in sorted(Path(args.maps).glob("*.topic_map.json")):
        doc = json.loads(f.read_text())
        tt, ut = doc["video_id"], doc["unit_times"]
        sums = json.loads((Path(args.summary_dir) / f"{tt}.summaries.json").read_text())
        cands = []
        for t in doc["levels"]["default"]["topics"]:
            shots = t["shots"]
            runs = [[shots[0]]]
            for s in shots[1:]:
                (runs[-1].append(s) if s == runs[-1][-1] + 1 else runs.append([s]))
            for i, a in enumerate(runs):
                for b in runs[i + 1:]:
                    if b[0] - a[-1] >= args.min_gap:
                        cands.append((t, a, b))
        rng.shuffle(cands)
        seen = set()
        for t, a, b in cands:
            if t["topic_id"] in seen or len([p for p in pool if p["film"] == tt]) >= args.per_film:
                continue
            seen.add(t["topic_id"])
            ma, mb = a[len(a) // 2], b[len(b) // 2]
            pool.append({"film": tt, "topic_id": t["topic_id"], "topic_label": t["label"],
                         "provenance": {k: v["agreement"] for k, v in t["provenance"].items()},
                         "a": {"t0": ut[a[0]][0], "t1": ut[a[-1]][1], "summary": summary_at(sums, ma),
                               "frames": [keyframe(tt, s) for s in (a[0], ma, a[-1])]},
                         "b": {"t0": ut[b[0]][0], "t1": ut[b[-1]][1], "summary": summary_at(sums, mb),
                               "frames": [keyframe(tt, s) for s in (b[0], mb, b[-1])]}})
    rng.shuffle(pool)
    cases = pool[:args.n]
    for i, c in enumerate(cases, 1):
        c["case"] = i
    (out / "cases.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False))

    with open(out / "review.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "film", "a_time", "a_summary", "b_time", "b_summary",
                    "same_thread (yes/no/unsure)", "note"])
        for c in cases:
            fmt = lambda s: f"{int(s['t0'] // 60)}:{int(s['t0'] % 60):02d}–{int(s['t1'] // 60)}:{int(s['t1'] % 60):02d}"  # noqa: E731
            w.writerow([c["case"], c["film"], fmt(c["a"]), c["a"]["summary"], fmt(c["b"]),
                        c["b"]["summary"], "", ""])

    def side(s, name):
        imgs = "".join(f'<img src="file://{html.escape(p)}" alt="">' for p in s["frames"] if p)
        return (f'<div class="side"><h4>{name} · {s["t0"] / 60:.1f}–{s["t1"] / 60:.1f} min</h4>'
                f'<div class="frames">{imgs}</div><p>{html.escape(s["summary"])}</p></div>')
    body = "".join(
        f'<section><h3>Case {c["case"]} · {c["film"]} · gap {(c["b"]["t0"] - c["a"]["t1"]) / 60:.1f} min</h3>'
        f'<div class="pair">{side(c["a"], "A (earlier)")}{side(c["b"], "B (later)")}</div>'
        f'<p class="q">Same storyline / thread? &nbsp; ☐ yes &nbsp; ☐ no &nbsp; ☐ unsure</p></section>'
        for c in cases)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>G-enlace review</title>
<style>
:root{{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--line:#dcdcd6}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a1a18;--fg:#ececea;--muted:#a3a39c;--line:#3a3a36}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px}}
section{{border-top:1px solid var(--line);padding:12px 0}} h3{{margin:.2em 0}} h4{{margin:.2em 0;color:var(--muted);font-weight:500}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} @media (max-width:700px){{.pair{{grid-template-columns:1fr}}}}
.frames{{display:flex;gap:4px}} .frames img{{width:32%;height:auto;border-radius:4px}} .q{{font-weight:600}}
</style></head><body><h1>G-enlace — human review of non-adjacent links</h1>
<p>Each case shows two moments that CAVA placed in the <b>same topic</b>, far apart in time.
Judge whether they belong to the same storyline/thread. Record answers in <code>review.csv</code>.</p>
{body}</body></html>"""
    (out / "review.html").write_text(page)
    print(f"[review] {len(cases)} casos de {len({c['film'] for c in cases})} películas -> {out}")


if __name__ == "__main__":
    main()
