"""EXP-036 F5 cobertura completa: informe TRAMO_FULL.md + decisión de adopción (F5_METHOD_AMENDMENT_v1.md §2).

Lee full/merge_report.json, full/jobs.json, full/fetched/*/gpu_time.jsonl, full/briefs_tramos_*.json,
full/index_add/ y results/eval_tramo_full.json. Escribe exp036/f5/TRAMO_FULL.md, full/adoption.json y
full/full_index_hashes.txt. Si falta alguna pieza, lo dice en el informe y F no se adopta.

Uso: CAVA_minimo/.venv/bin/python -I exp036/f5/tramos/full_report.py
"""
import collections
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
F5 = HERE.parent
FULL = HERE / "full"
sys.path.insert(0, str(F5))
from f5_common import CAVA  # noqa: E402


def load(p):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else None


def sha16(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def fmt_ci(x, k):
    return f"{x[k]:.3f} [{x[k + '_ci95'][0]:.3f}-{x[k + '_ci95'][1]:.3f}]"


def main():
    import argparse
    global FULL
    ap = argparse.ArgumentParser()
    ap.add_argument("--full-dir", default=str(FULL))
    ap.add_argument("--eval", default=str(F5 / "results" / "eval_tramo_full.json"))
    ap.add_argument("--out-md", default=str(F5 / "TRAMO_FULL.md"))
    ap.add_argument("--index-subdir", default="index_add", help="índice F dentro de --full-dir")
    ap.add_argument("--adoption-out", help="copia adicional de adoption.json (p. ej. tramos/full/adoption.json)")
    ap.add_argument("--notes", help="Markdown con la interpretación, se incluye como sección final")
    a = ap.parse_args()
    FULL = Path(a.full_dir).resolve()
    merge = load(FULL / "merge_report.json")
    jobs = load(FULL / "jobs.json") or []
    ev = load(a.eval)
    base = load(F5 / "results" / "eval_provisional_v0.json")
    orch = load(FULL / "orchestrator_state.json") or {}
    L = [f"# EXP-036 F5 — Cobertura completa de tramos (F)", "",
         f"Generado automáticamente por `tramos/full_report.py` el {time.strftime('%Y-%m-%d %H:%M:%S')}. "
         "Consultas **provisionales** (no gold). Reglas de adopción: `F5_METHOD_AMENDMENT_v1.md` §2.", ""]

    # ---------------- índice y hashes
    hashes = []
    idx = FULL / a.index_subdir
    n_tramo_docs = None
    if idx.exists():
        for f in sorted(idx.iterdir()):
            hashes.append(f"{sha16(f)} {f.relative_to(HERE.parent.parent)}")
        n_tramo_docs = sum(1 for m in ("Avengers_Endgame", "Spider_Man")
                           for d in load(idx / f"{m}.meta.json")["docs"] if d["level"] == "tramo")
        (FULL / "full_index_hashes.txt").write_text("\n".join(hashes) + "\n")

    # ---------------- adopción
    A = {}
    if merge:
        # A1 = cobertura COMPLETA (corregido en v2: en v1 se aceptaba >= 95 %, contrario a la enmienda §2 A1)
        A["A1_coverage"] = {"n_manifest": merge["n_manifest"], "n_ok": merge["n_ok"], "covers_all": merge["covers_all"],
                            "disjoint": merge["shards_disjoint"], "tramo_docs_in_index": n_tramo_docs,
                            "ok": merge["n_manifest"] == 501 and merge["n_ok"] == merge["n_manifest"]
                            and merge["covers_all"] and merge["shards_disjoint"] and n_tramo_docs == merge["n_ok"]}
    else:
        A["A1_coverage"] = {"ok": False, "detail": "sin merge_report.json"}
    cf = (ev or {}).get("criteria_by_condition", {}).get("F")
    if cf:
        A["A2_confirms_pilot"] = {"L_net_hits": cf["1_R@3_L_delta>=0.10"]["net_hits"],
                                  "IoU_L_F": cf["2_IoU@3_L>=B"]["F"], "IoU_L_B": cf["2_IoU@3_L>=B"]["B"],
                                  "ok": cf["1_R@3_L_delta>=0.10"]["ok"] and cf["2_IoU@3_L>=B"]["ok"]}
        A["A3_no_global_regression"] = cf["3_no_global_regression"]
        A["A4_C_no_worse_than_B"] = cf["C_no_worse_than_B"]
        A["A5_latency"] = cf["4_latency_p95<2s"]
    else:
        for k in ("A2_confirms_pilot", "A3_no_global_regression", "A4_C_no_worse_than_B", "A5_latency"):
            A[k] = {"ok": False, "detail": "sin evaluación de F"}
    adopted = all(v["ok"] for v in A.values())
    adoption = {"decided": time.strftime("%Y-%m-%d %H:%M:%S"), "adopted": adopted,
                "candidate_for_gold": "F = hybrid_rerank_loc[scene,topic,tramo] @ tramos/full/index_add" if adopted
                else "B = hybrid_rerank_loc[scene,topic] @ exp036/f5/index (tramos exploratorios)",
                "conditions": A, "index_hashes": hashes, "gold_seen": False}
    adoption["index_dir"] = str(idx.relative_to(HERE.parent.parent))
    (FULL / "adoption.json").write_text(json.dumps(adoption, ensure_ascii=False, indent=1))
    if a.adoption_out:
        Path(a.adoption_out).write_text(json.dumps(adoption, ensure_ascii=False, indent=1))

    L += [f"## 1. Decisión: **{'F ADOPTADO como candidato para el gold' if adopted else 'F NO adoptado: el candidato sigue siendo B; tramos exploratorios'}**", "",
          "| condición | medido | ¿cumple? |", "|---|---|---|"]
    for k, v in A.items():
        L.append(f"| {k} | `{json.dumps({x: y for x, y in v.items() if x != 'ok'}, ensure_ascii=False)}` | "
                 f"{'sí' if v['ok'] else '**no**'} |")
    L += ["", "Ningún dato gold existe ni se ha visto (`gold_seen: false` en `tramos/full/adoption.json`).", ""]

    # ---------------- generación distribuida
    L += ["## 2. Generación distribuida", "",
          "| job | host | partición | asignados | inicio | fin | duración | rc | ok | gen (GPU) | carga |",
          "|---|---|---|---:|---|---|---:|---|---:|---:|---:|"]
    tot_gen = 0.0
    for j in jobs:
        gts = [json.loads(l) for l in (FULL / "fetched" / j["job"] / "gpu_time.jsonl").read_text().splitlines()
               if l.strip()] if (FULL / "fetched" / j["job"] / "gpu_time.jsonl").exists() else []
        g = sum(x["gen_s"] for x in gts)
        tot_gen += g
        dur = (j.get("end_ts", 0) - j.get("start_ts", 0)) if j.get("end_ts") else None
        L.append(f"| {j['job']} | {j['host']} | {j['shard']} | {j.get('assigned', '—')} | {j.get('start', '—')} | "
                 f"{j.get('end', '—')} | {f'{dur / 60:.0f} min' if dur else '—'} | {j.get('rc', '—')} | "
                 f"{j.get('ok_units', '—')} | {g / 60:.1f} min | {sum(x['load_s'] for x in gts):.0f} s |")
    n_new = merge["n_ok"] - 56 if merge else 0
    L += ["", f"GPU de generación sumada en los 4 workers: **{tot_gen / 3600:.2f} h** "
              f"({tot_gen / max(1, n_new):.0f} s por tramo nuevo válido; piloto: 75 s/tramo). "
              f"Tiempo de pared del orquestador: {orch.get('wall_min', '—')} min.", ""]
    if orch.get("events"):
        L += ["Eventos del orquestador (reintentos/reasignaciones/avisos):", ""] + \
             [f"- {e}" for e in orch["events"]] + [""]

    # ---------------- fusión
    if merge:
        L += ["## 3. Validación y fusión", "",
              f"- Manifiesto: {merge['n_manifest']} tramos; válidos: **{merge['n_ok']}/{merge['n_manifest']}**; "
              f"ausentes: {merge['n_missing']}; inválidos: {merge['n_invalid']}; particiones disjuntas: "
              f"{merge['shards_disjoint']}; cobertura completa: **{merge['covers_all']}** → A1 "
              f"{'cumple' if A['A1_coverage']['ok'] else '**NO cumple** (A1 exige 501/501)'}.",
              f"- Unidades regeneradas en la reparación v2: {merge.get('n_repaired_units', 0)}.",
              f"- Por película: {merge['per_movie_ok']}. Por origen: `{json.dumps(merge['per_source'])}`.",
              "- Cada registro aceptado: misma evidencia (sha256) que el manifiesto, recalculada localmente; `validate()` "
              "de F1 re-ejecutado sobre la salida cruda sin problemas duros; JSON idéntico al guardado.", ""]
        if merge["problems"]:
            L += ["Unidades no aceptadas (primeras 20):", ""] + \
                 [f"- {p['movie']} {p['uid']}: {p['status']} {json.dumps(p['detail'])[:200]}" for p in merge["problems"][:20]] + [""]

    # ---------------- resultados
    if ev:
        S = ev["summary"]
        L += ["## 4. Resultados (60 consultas provisionales; `hybrid_rerank_loc`)", "",
              "B = candidato congelado (`scene,topic`); P = piloto (56 tramos en 4 escenas); F = cobertura completa "
              "(`scene,topic,tramo`). L = 29 consultas de las 4 escenas del piloto; C = 31 restantes.", "",
              "| cond. | subconj. | n | R@3 (IC 95 %) | IoU@3 (IC 95 %) | R@3[IoU≥.1] | R@1 | dur@3 | lat. media/p95 |",
              "|---|---|---:|---|---|---|---|---|---|"]
        for s in ("all", "L_long", "C_rest"):
            for n in S:
                x = S[n][s]
                L.append(f"| {n} | {s} | {x['n']} | {fmt_ci(x, 'R@3')} | {fmt_ci(x, 'IoU@3')} | {x['R@3_iou10']:.3f} | "
                         f"{x['R@1']:.3f} | {x['dur@3']:.0f} s | {x['lat_mean_ms']:.0f}/{x['lat_p95_ms']:.0f} ms |")
        L += ["", "**Por escena larga** (R@3 / IoU@3, n):", "", "| escena | " + " | ".join(S) + " |",
              "|---|" + "---|" * len(S)]
        for k in S["B"]["by_long_scene"]:
            L.append(f"| {k} | " + " | ".join(f"{S[n]['by_long_scene'][k]['R@3']:.3f} / {S[n]['by_long_scene'][k]['IoU@3']:.3f} "
                                             f"({S[n]['by_long_scene'][k]['n']})" for n in S) + " |")
        L += ["", "McNemar exacto (R@3, x frente a B): " +
              "; ".join(f"{k}: {v['x_only']}/{v['B_only']} (p = {v['p_exact']})" for k, v in ev["paired"].items()), ""]
        pq = {d["qid"]: d for d in ev["per_query"]}
        if "F" in S:
            gained = [q for q, d in pq.items() if d["B"]["R@3"] == 0 and d["F"]["R@3"] == 1]
            lost = [q for q, d in pq.items() if d["B"]["R@3"] == 1 and d["F"]["R@3"] == 0]
            lostC = [q for q in lost if not pq[q]["long_scene"]]
            L += [f"Frente a B, F gana {len(gained)} consultas ({', '.join(gained) or '—'}) y pierde {len(lost)} "
                  f"({', '.join(lost) or '—'}); pérdidas en C: {len(lostC)} ({', '.join(lostC) or '—'}). "
                  f"Piloto P perdía en C: S13, S19.", ""]
            if base:
                miss = [d["qid"] for d in base["per_query"] if d["hybrid_rerank"]["R@3"] == 0]
                rec = [q for q in miss if pq[q]["F"]["R@3"] == 1]
                L += [f"De los 21 fallos de `hybrid_rerank` a nivel escena (`F5_BASELINE.md`), F recupera **{len(rec)}** "
                      f"({', '.join(rec)}); P recuperaba 14.", ""]
            for q in lost:
                d = pq[q]
                L.append(f"- pérdida {q} ({d['query'][:70]}; ref {d['ref']}): F top-3 = " +
                         ", ".join(f"{t['level']}:{t['unit']} {t['t0_hms']}-{t['t1_hms']}" for t in d["F"]["top3"]))
            L.append("")
    else:
        L += ["## 4. Resultados", "", "**Sin evaluación** (`results/eval_tramo_full.json` no existe): ver el log del orquestador.", ""]

    # ---------------- calidad
    W, nul, mism, n = collections.Counter(), 0, [], 0
    for mov in ("Avengers_Endgame", "Spider_Man"):
        d = load(FULL / f"briefs_tramos_{mov}.json") or {}
        reg = {}
        rp = CAVA / "outputs" / mov / "characters_registry.txt"
        for l in rp.read_text().splitlines():
            if " - " in l:
                rname, rdesc = l.split(" - ", 1)
                reg[rname.strip()] = rdesc.strip().lower()
        for uid, r in d.items():
            n += 1
            W.update(r["problems"]["warn"])
            for c in r["brief"].get("characters") or []:
                if not isinstance(c, dict):
                    continue
                nm = c.get("name")
                if isinstance(nm, str) and nm.strip().lower() == "null":
                    nul += 1
                desc = (c.get("description") or "").lower()
                for rn, rd in reg.items():
                    if rd[:30] and rd[:30] in desc and rn.lower() not in str(nm or "").lower():
                        mism.append(f"{mov} {uid}: name={nm!r} con la descripción del registro de {rn}")
    L += ["## 5. Calidad e identidades (sin F3)", "",
          f"Sobre {n} briefs de tramo válidos: avisos `{dict(W)}`; nombres con el string literal \"null\": {nul}; "
          f"descripciones del registro atribuidas a otro nombre (heurística): **{len(mism)}**.", ""] + \
         [f"- {m}" for m in mism[:25]] + (["- …"] if len(mism) > 25 else []) + [""]

    # ---------------- hashes y lectura
    L += ["## 6. Índice F congelado (forma parte de la enmienda v1)", "", "```"] + (hashes or ["(índice no construido)"]) + ["```", "",
          "## 7. Límites", "",
          "- Consultas provisionales escritas por el agente desde ASR/VJudge; referencias sin verificar en video; n = 60.",
          "- L se definió con las escenas donde B fallaba (dentro de la muestra); C es la comprobación de desplazamiento.",
          "- El objetivo + 15 pp frente a EXP-035 solo es afirmable sobre gold humano (`F5_METHOD_FREEZE.md` §2.2).",
          "", "## 8. Reproducción", "", "```bash",
          "cd /data/tesis-cava; P=CAVA_minimo/.venv/bin/python; T=exp036/f5/tramos",
          "python3 $T/repair_run.py                       # v2: regenera las 24 unidades de la colisión (GPU)",
          "$P -I $T/full_merge.py --jobs $T/full_v2/jobs.json --out-dir $T/full_v2",
          "$P -I $T/tramo_index.py --briefs-dir $T/full_v2 --out-root $T/full_v2 --variants index_add",
          "$P -I $T/tramo_eval.py --tag eval_tramo_full_v2 --conds \"B=exp036/f5/index:scene,topic\" "
          "\"P=exp036/f5/tramos/index_add:scene,topic,tramo\" \"F=exp036/f5/tramos/full_v2/index_add:scene,topic,tramo\"",
          "$P -I $T/full_report.py --full-dir $T/full_v2 --eval exp036/f5/results/eval_tramo_full_v2.json "
          "--adoption-out $T/full/adoption.json --notes $T/full_v2/LECTURA.md",
          "```", ""]
    if a.notes and Path(a.notes).exists():
        L += [Path(a.notes).read_text()]
    Path(a.out_md).write_text("\n".join(L))
    print(f"[full report] adoptado={adopted} -> {a.out_md}")


if __name__ == "__main__":
    main()
