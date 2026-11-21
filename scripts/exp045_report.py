"""EXP-045-Q: arma results/exp045_q/report.md y summary.json (adopción por pista) a partir de los JSON de exp045_eval.py.

Regla (registro): una variante se adopta por pista solo si cumple su fila Y las de extremo a extremo.
Extremo a extremo por pista = sustitución de esa sola pista sobre el mapa ref (abl/<pista>=fast); además se exige que la
combinación de las pistas adoptables (abl/combo) también pase. Pistas LLM: la revisión humana (>= 18/20) queda pendiente.
"""
import argparse
import json
from pathlib import Path


def pct(x, d=2):
    return "—" if x is None else f"{100 * x:.{d}f} %"


def f(x, d=4):
    return "—" if x is None else (f"{x:.{d}f}" if isinstance(x, float) else str(x))


def fails(d):
    return [k for k, v in d.items() if not v]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="results/exp045_q")
    a = ap.parse_args()
    D = Path(a.dir)
    L = lambda n: json.loads((D / f"{n}.json").read_text()) if (D / f"{n}.json").exists() else {}  # noqa: E731
    asr, emb, llm, e2e, tim = L("asr"), L("emb"), L("llm"), L("e2e"), L("timing")
    sp = e2e.get("specs", {})
    out = ["# EXP-045-Q · Resultado de la validación de tolerancia de variantes `fast`", "",
           "Umbrales, refset_v1 y reglas: los registrados en `docs/EXPERIMENT_LOG.md` (EXP-045-Q, commit a4a30ec). Sin cambios.", ""]
    # ---------------- pistas
    out += ["## 1. Pistas (variante vs ref)", ""]
    if asr:
        out += ["### ASR (faster-whisper int8_float16 vs float16)", "",
                "| métrica | valor | umbral | ok |", "|---|---|---|---|",
                f"| WER(fast, ref) agrupado, {asr['n_files']} archivos | {pct(asr['wer_pooled_all'])} | ≤ 3 % | {asr['pass']['wer_le_3pct']} |",
                f"| · pipeline (5 videos) / VoxConverse dev (20) | {pct(asr['wer_pooled_pipeline'])} / {pct(asr['wer_pooled_vox'])} | | |",
                f"| · peor archivo | {asr['worst_file']} | (informativo) | |",
                f"| · archivos con WER > 3 % | {len(asr['files_above_3pct'])}: {', '.join(asr['files_above_3pct']) or '—'} | (informativo) | |",
                f"| AMI ES2002c: WER ref vs GT / fast vs GT / Δ | {pct(asr['ami_gt']['wer_ref_vs_gt'])} / {pct(asr['ami_gt']['wer_fast_vs_gt'])} / {asr['ami_gt']['delta_pp']:+.3f} pp | Δ ≤ +0,5 pp | {asr['pass']['ami_delta_wer_le_0.5pp']} |",
                f"| Filtro de habla por unidad idéntico (todas las unidades) | {pct(asr['gate_equal_frac_all'])} | ≥ 99 % | {asr['pass']['gate_equal_ge_99pct']} |",
                f"| · pipeline / vox | {pct(asr['gate_equal_frac_pipeline'])} / {pct(asr['gate_equal_frac_vox'])} | | |", ""]
        out += ["| archivo | palabras ref | WER vs ref | unidades con mismo filtro |", "|---|---|---|---|"]
        for k, v in asr["per_file"].items():
            out.append(f"| {k} | {v['n_words_ref']} | {pct(v['wer_vs_ref'])} | {pct(v['gate_equal_frac'])} |")
        out.append("")
    out += ["### Embeddings (coseno por unidad; ref vs fast)", "", "| pista | n | mediana | p1 | mín | ok (≥0,995 / ≥0,98) |", "|---|---|---|---|---|---|"]
    for k, v in emb.items():
        if k == "faces":
            out.append(f"| rostros | — | — | — | — | **no evaluada**: {v['reason']} |")
            continue
        p = v["pooled"]
        out.append(f"| {k} | {p['n']} | {f(p['median'], 5)} | {f(p['p1'], 5)} | {f(p['min'], 4)} | {v['pass_all']} ({fails(v['pass']) or 'cumple'}) |")
    out += ["", "### VJudge / etiquetas (coseno bge entre textos ref y fast)", "",
            "| pista | n | mediana cos | p1 | % idénticos | automático (mediana ≥ 0,90) | revisión humana (≥ 18/20) |", "|---|---|---|---|---|---|---|"]
    for k, v in llm.items():
        out.append(f"| {k} | {v['n']} | {f(v['pooled']['median'], 4)} | {f(v['pooled']['p1'], 4)} | {pct(v['identical_frac'])} | "
                   f"{all(v['pass_automatic'].values())} | pendiente de revisión humana |")
    out += ["", "Diarización: **no se toca** (EXP-045-Q: «si se toca»); sin variante. Rostros: ver arriba.", ""]
    # ---------------- e2e
    out += ["## 2. Extremo a extremo (cada video; lectura estricta: todos los videos deben pasar)", "",
            "Columnas: ARI unidad→tópico (≥0,95) · F1 fronteras ±1 (≥0,95) · Δ nº tópicos (≤2 %) · Δ retornos (≤2 %) · G-versión igual · "
            "IoU highlights10pct / recap60 (≥0,90) · capítulos con mismo tópico, Jaccard ≥ 0,9 (≥95 %).", ""]
    for label, s in sp.items():
        out += [f"### {label} — {'PASA en todos los videos' if s['pass_all_videos'] else 'FALLA en: ' + ', '.join(s['videos_failing'])}", "",
                "| video | ARI | F1 | Δtóp | Δret | G= | IoU hl | IoU recap | cap. | ok |", "|---|---|---|---|---|---|---|---|---|---|"]
        for n, m in s["per_video"].items():
            out.append(f"| {n} | {f(m['ari_unit_topic'], 3)} | {f(m['f1_boundaries_pm1'], 3)} | {pct(m['delta_n_topics_rel'], 1)} ({m['n_topics_ref']}→{m['n_topics_cand']}) | "
                       f"{pct(m['delta_returns_rel'], 1)} ({m['n_returning_ref']}→{m['n_returning_cand']}) | {m['G_version_equal']} | "
                       f"{f(m['iou_highlights10pct'], 3)} | {f(m['iou_recap60'], 3)} | {f(m['chapters_same_topics_j09'], 3)} | {m['pass_all']} |")
        out.append("")
    if e2e.get("noise_floor_ref_vs_frozen"):
        out += ["### Piso de ruido: corrida ref de este experimento vs salidas congeladas (otra GPU/versión de biblioteca)", "",
                "| video | ARI | F1 | Δtóp | Δret | IoU hl | IoU recap |", "|---|---|---|---|---|---|---|"]
        for n, m in e2e["noise_floor_ref_vs_frozen"].items():
            out.append(f"| {n} | {f(m['ari_unit_topic'], 3)} | {f(m['f1_boundaries_pm1'], 3)} | {pct(m['delta_n_topics_rel'], 1)} | "
                       f"{pct(m['delta_returns_rel'], 1)} | {f(m['iou_highlights10pct'], 3)} | {f(m['iou_recap60'], 3)} |")
        out.append("")
    # ---------------- tiempos
    if tim:
        out += ["## 3. Tiempos (s por hora de video; ref y fast, misma familia de GPU)", "",
                "| etapa | ref s/h | fast s/h | aceleración |", "|---|---|---|---|"]
        for s, v in tim["stages"].items():
            out.append(f"| {s} | {f(v['ref_s_per_h'], 1)} | {f(v['fast_s_per_h'], 1)} | {f(v['speedup'], 2)}× |")
        t = tim["total"]
        out.append(f"| **total** | {f(t['ref_s_per_h'], 1)} | {f(t['fast_s_per_h'], 1)} | {f(t.get('speedup'), 2)}× |")
        out.append("")
    (D / "report_tables.md").write_text("\n".join(out) + "\n")
    print("report_tables.md escrito")


if __name__ == "__main__":
    main()
