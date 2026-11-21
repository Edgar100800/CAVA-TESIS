"""EXP-046-STAB: métricas por pares de corridas, piso de ruido, atribución, lectura pre-declarada y re-evaluación EXP-045-Q.

Uso: python scripts/exp046_analyze.py --runs /data/tesis-cava/exp046/runs --out results/exp046_stab
Reutiliza `exp045_common.e2e_metrics` y las funciones de `exp045_eval` (WER, coseno): no reimplementa las métricas.
Corridas: <runs>/<máquina>/<modo>/<video>/r<k>; máquinas 56 (r1..r3), 54, 55, 61 (r1).
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp045_common import STACK, VIDEOS, boundaries, e2e_metrics, f1_tol, topic_of_units  # noqa: E402
from exp045_eval import cos_rows, dist, lev, seg_text, words  # noqa: E402
from topicagg.pipeline import units_text  # noqa: E402
from topicagg.profiles import get_profile  # noqa: E402
from topicagg.versions import check_versions  # noqa: E402

LABELS = ["56.1", "56.2", "56.3", "54", "55", "61"]
LOC = {"56.1": ("56", 1), "56.2": ("56", 2), "56.3": ("56", 3), "54": ("54", 1), "55": ("55", 1), "61": ("61", 1)}
VIDS = list(VIDEOS)
MODES = ("R", "D")
FLOOR_KEYS = ("ari_unit_topic", "f1_boundaries_pm1", "delta_n_topics_rel", "delta_returns_rel", "iou_highlights10pct",
              "iou_recap60", "chapters_same_topics_j09")
WORST = {"ari_unit_topic": min, "f1_boundaries_pm1": min, "delta_n_topics_rel": max, "delta_returns_rel": max,
         "iou_highlights10pct": min, "iou_recap60": min, "chapters_same_topics_j09": min}


def run_dir(root, mode, video, label):
    m, k = LOC[label]
    return Path(root) / m / mode / video / f"r{k}"


class Run:
    def __init__(self, d):
        self.d = Path(d)
        self.doc = json.loads((self.d / "topic_map.json").read_text())
        self.vers = json.loads((self.d / "versions.json").read_text())
        self.st = json.loads((self.d / "work/state.json").read_text())
        self.units = self.st["units"]
        det = self.d / "work/asr.det.json"
        self.asr = json.loads(det.read_text())["segments"] if det.exists() else self.st["asr_segments"]
        self.asr_text = units_text(self.asr, self.units)
        z = np.load(self.d / "work/signals.npz")
        self.voice, self.visual = z["voice"], z["visual"]
        b = np.load(self.d / "work/sig_bge.npz")
        self.bge_t, self.bge_v = b["transcript"], b["vjudge"]
        self.summaries = json.loads((self.d / "work/summaries.json").read_text())
        self.done = json.loads((self.d / "stab_done.json").read_text())
        self.lab = topic_of_units(self.doc, len(self.doc["unit_times"]))

    def tracks(self):
        return {"asr": (self.bge_t, self.asr_text), "vjudge": (self.bge_v, self.summaries),
                "visual": self.visual, "voice": self.voice}


def track_diffs(a, b):
    wa, wb = words(seg_text(a.asr)), words(seg_text(b.asr))
    e = lev(wa, wb)
    out = {"asr_wer": e / max(len(wa), 1), "asr_edits": e, "asr_words": len(wa),
           "asr_segments_identical": a.asr == b.asr}
    n = min(len(a.visual), len(b.visual))
    c, _ = cos_rows(a.visual[:n], b.visual[:n])
    out["siglip_cos"] = dist(c) | {"identical_frac": float(np.mean(np.all(a.visual[:n] == b.visual[:n], axis=1)))}
    c, _ = cos_rows(a.bge_t[:n], b.bge_t[:n])
    out["bge_transcript_cos"] = dist(c) | {"identical_frac": float(np.mean(np.all(a.bge_t[:n] == b.bge_t[:n], axis=1)))}
    ta, tb = [s["summary"].strip() for s in a.summaries], [s["summary"].strip() for s in b.summaries]
    if len(ta) == len(tb):
        # similitud de texto del vjudge: coseno bge entre resúmenes (vectores ya guardados, expandidos por unidad)
        idx = [s["lo"] for s in a.summaries]
        c, _ = cos_rows(a.bge_v[idx], b.bge_v[idx])
        out["vjudge_text"] = dist(c) | {"identical_frac": float(np.mean([x == y for x, y in zip(ta, tb)])), "n_blocks": len(ta)}
        # diagnóstico: ¿el vjudge es determinista dado el mismo texto de entrada? (el habla del bloque entra en su prompt)
        same_in = [(" ".join(a.asr_text[s["lo"]:s["hi"]])[:500] or "(no speech)") == (" ".join(b.asr_text[s["lo"]:s["hi"]])[:500] or "(no speech)")
                   for s in a.summaries]
        same_out = [x == y for x, y in zip(ta, tb)]
        out["vjudge_given_input"] = {
            "blocks_same_input": int(sum(same_in)), "blocks": len(same_in),
            "same_output_given_same_input": int(sum(o for i, o in zip(same_in, same_out) if i)),
            "same_output_given_diff_input": int(sum(o for i, o in zip(same_in, same_out) if not i)),
            "blocks_diff_input": int(len(same_in) - sum(same_in))}
    else:
        out["vjudge_text"] = {"n_blocks_a": len(ta), "n_blocks_b": len(tb)}
    va, vb = a.voice[:n].astype(np.float64), b.voice[:n].astype(np.float64)
    out["voice_max_abs_diff"] = float(np.max(np.abs(va - vb))) if va.size else 0.0
    out["voice_identical"] = bool(np.array_equal(va, vb))
    return out


def rebuild(tr, run, tracks):
    """Recalcula el mapa con las pistas dadas (mismo código que Pipeline.topic_map; sin recomputar ninguna pista)."""
    from topicagg.identities import identities, speaker_turn_scores
    from topicagg.topic_map import build_topic_map
    cfg = get_profile(STACK, run.cfg_profile)
    (bt, atext), (bv, summ) = tracks["asr"], tracks["vjudge"]
    n = len(run.units)
    vj = np.zeros((n, bv.shape[1]), np.float32)
    vj[:] = bv[:n]
    sig = {"voice": tracks["voice"][:n], "visual": tracks["visual"][:n], "transcript": bt, "vjudge": vj}
    bnd = None
    if cfg.get("speaker_turns_w"):
        vid = identities(np.asarray(sig["voice"], np.float32), "ward", k_rule="bic")
        bnd = {"turns": speaker_turn_scores(vid, cfg["speaker_turns_w"])}
    return build_topic_map(Path(run.st.get("name", "x")).stem, sig, run.units, unit_summaries=summ, boundary_signals=bnd,
                           snap_visual_s=cfg.get("snap_visual_s"), percentile=cfg["percentile"],
                           return_percentile=cfg["return_percentile"], abstain=True, unit_texts=atext)


def doc_metrics(ref_doc, cand_doc):
    n = len(ref_doc["unit_times"])
    la, lb = topic_of_units(ref_doc, n), topic_of_units(cand_doc, min(n, len(cand_doc["unit_times"])))
    m = min(len(la), len(lb))
    la, lb = la[:m], lb[:m]
    da, db = ref_doc["levels"]["default"], cand_doc["levels"]["default"]
    return {"ari": float(adjusted_rand_score(la, lb)), "f1": float(f1_tol(boundaries(la), boundaries(lb), 1)),
            "n_topics": [da["n_topics"], db["n_topics"]], "n_returning": [da["n_returning"], db["n_returning"]],
            "partition_identical": bool(np.array_equal(la, lb))}


def attribution(a, b):
    """Mapa de a con una pista tomada de b; la pista cuya sustitución baja más el ARI frente al mapa de a es la fuente principal."""
    base = rebuild(None, a, a.tracks())
    out = {"sanity_rebuild_reproduces_a": doc_metrics(a.doc, base), "ari_a_vs_b": doc_metrics(a.doc, b.doc)["ari"], "swap": {}}
    for k in ("asr", "vjudge", "visual", "voice"):
        tr = a.tracks() | {k: b.tracks()[k]}
        out["swap"][k] = doc_metrics(base, rebuild(None, a, tr))
    sw = {k: v["ari"] for k, v in out["swap"].items()}
    lo = min(sw.values())
    out["ari_by_track"] = sw
    out["main_source"] = None if lo >= 1.0 - 1e-12 else min(sw, key=sw.get)
    return out


def floors(pairs, same):
    sel = [p["metrics"] for p in pairs if p["same_machine"] == same]
    if not sel:
        return None
    f = {k: WORST[k]([m[k] for m in sel]) for k in FLOOR_KEYS}
    f["n_pairs"] = len(sel)
    f["n_pairs_partition_identical"] = sum(1 for p in pairs if p["same_machine"] == same and p["partition_identical"])
    f["G_version_equal_all"] = all(m["G_version_equal"] for m in sel)
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="/data/tesis-cava/exp046/runs")
    ap.add_argument("--out", default="results/exp046_stab")
    ap.add_argument("--exp045", default="/data/tesis-cava/exp045/runs")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res = {"schema": "exp046-stab-v1", "labels": LABELS, "videos": VIDS, "pairs": {}, "floors": {}, "attribution": {},
           "inventory": {}, "missing": []}
    runs = {}
    for mode in MODES:
        for v in VIDS:
            for lab in LABELS:
                d = run_dir(a.runs, mode, v, lab)
                if (d / "stab_done.json").exists():
                    r = Run(d)
                    r.cfg_profile = VIDEOS[v]["profile"]
                    runs[(mode, v, lab)] = r
                    res["inventory"][f"{mode}/{v}/{lab}"] = r.done | {"G_version": r.done["G_version"],
                                                                      "n_topics": r.doc["levels"]["default"]["n_topics"]}
                else:
                    res["missing"].append(f"{mode}/{v}/{lab}")
    for mode in MODES:
        for v in VIDS:
            have = [l for l in LABELS if (mode, v, l) in runs]
            pairs = []
            for la, lb in itertools.combinations(have, 2):
                ra, rb = runs[(mode, v, la)], runs[(mode, v, lb)]
                met = e2e_metrics(ra.doc, ra.vers, rb.doc, rb.vers, check_versions)
                pairs.append({"a": la, "b": lb, "same_machine": LOC[la][0] == LOC[lb][0], "metrics": met,
                              "partition_identical": bool(np.array_equal(ra.lab, rb.lab)),
                              "topic_map_bytes_identical": (ra.d / "topic_map.json").read_bytes() == (rb.d / "topic_map.json").read_bytes(),
                              "tracks": track_diffs(ra, rb)})
            res["pairs"][f"{mode}/{v}"] = pairs
            res["floors"][f"{mode}/{v}"] = {"same_machine": floors(pairs, True), "cross_machine": floors(pairs, False)}
            att = {}
            for la, lb in (("56.1", "56.2"), ("56.1", "56.3"), ("56.2", "56.3")):
                if (mode, v, la) in runs and (mode, v, lb) in runs:
                    att[f"{la}<-{lb}"] = attribution(runs[(mode, v, la)], runs[(mode, v, lb)])
            res["attribution"][f"{mode}/{v}"] = att
    # R frente a D (informativo): misma máquina, corrida 1
    res["R_vs_D_56.1"] = {v: e2e_metrics(runs[("R", v, "56.1")].doc, runs[("R", v, "56.1")].vers, runs[("D", v, "56.1")].doc,
                                         runs[("D", v, "56.1")].vers, check_versions)
                          for v in VIDS if ("R", v, "56.1") in runs and ("D", v, "56.1") in runs}
    # lectura pre-declarada
    dec = {"D_same_machine_min_ari": {}, "criterion": "ARI >= 0,95 en todos los pares de la misma máquina en los 5 videos (modo D)"}
    ok = True
    for v in VIDS:
        f = res["floors"].get(f"D/{v}", {}).get("same_machine")
        dec["D_same_machine_min_ari"][v] = f["ari_unit_topic"] if f else None
        n_pairs = f["n_pairs"] if f else 0
        ok &= bool(f) and n_pairs == 3 and f["ari_unit_topic"] >= 0.95
    dec["adopt_D"] = bool(ok)
    dec["R_same_machine_min_ari"] = {v: (res["floors"].get(f"R/{v}", {}).get("same_machine") or {}).get("ari_unit_topic") for v in VIDS}
    res["decision"] = dec
    res["reeval_exp045q"] = reeval(res, Path(a.exp045))
    (out / "stab.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    write_report(res, out)
    print("escrito", out)


def reeval(res, exp045):
    """Enmienda declarada: pistas que fallaron SOLO la fila de extremo a extremo, frente al piso de R (por video y métrica)."""
    cands = {"vjudge vLLM BF16, fotogramas exactos (vjudge=fast_exact)": "abl/vjudge-fast_exact"}
    out = {}
    for tag, d in cands.items():
        per, ok_all = {}, True
        for v in VIDS:
            fl = (res["floors"].get(f"R/{v}") or {}).get("same_machine")
            ref, cd = exp045 / "ref" / v, exp045 / d / v
            if not fl or not (cd / "topic_map.json").exists():
                per[v] = {"error": "falta piso de R o la corrida de la variante"}
                ok_all = False
                continue
            rd, rv = json.loads((ref / "topic_map.json").read_text()), json.loads((ref / "versions.json").read_text())
            cdd, cv = json.loads((cd / "topic_map.json").read_text()), json.loads((cd / "versions.json").read_text())
            m = e2e_metrics(rd, rv, cdd, cv, check_versions)
            chk = {"ari_unit_topic": m["ari_unit_topic"] >= fl["ari_unit_topic"],
                   "f1_boundaries_pm1": m["f1_boundaries_pm1"] >= fl["f1_boundaries_pm1"],
                   "delta_n_topics_rel": m["delta_n_topics_rel"] <= fl["delta_n_topics_rel"],
                   "delta_returns_rel": m["delta_returns_rel"] <= fl["delta_returns_rel"],
                   "iou_highlights10pct": m["iou_highlights10pct"] >= fl["iou_highlights10pct"],
                   "iou_recap60": m["iou_recap60"] >= fl["iou_recap60"]}
            per[v] = {"variant_vs_ref": {k: m[k] for k in FLOOR_KEYS + ("G_version_equal",)},
                      "floor_R": {k: fl[k] for k in FLOOR_KEYS}, "pass_by_metric": chk, "pass": all(chk.values())}
            ok_all &= all(chk.values())
        out[tag] = {"per_video": per, "adopted_e2e": bool(ok_all)}
    return out


NOTES = """## Notas y desviaciones

- **Corridas: 40/60.** `.54` y `.55` quedaron inalcanzables (ver el registro): faltan las 10 corridas de cada una (R y D × 5 videos). El piso de
  ruido y la lectura pre-declarada usan solo pares de la misma máquina (`.56`, 3 corridas por video y modo: completos). Entre máquinas solo hay
  pares `.56` × `.61` (3 por video y modo): no hay el diseño de 12 pares.
- Cada corrida parte del video (sin cachés), pila v1.1, sin etiquetas del LLM, hilos BLAS = 1, mismo commit de código (`dc4edac`) y mismas
  versiones de biblioteca en `.56` y `.61` (`env/<máquina>/pip_freeze.txt`; difieren el controlador NVIDIA, 580.178.04 frente a 595.99.02, y
  el equipo). No se cortaron mp4 (`cut=False`): IoU de highlights/recap se calcula sobre los segundos de `versions.json`.
- Varias corridas concurrentes por máquina (5 procesos con un libro de memoria de GPU de 22 GB por etapa): la concurrencia es una condición
  común a R y D; no se midió su efecto por separado.
- Atribución: la regla pre-declarada (la sustitución que más baja el ARI) devuelve ASR o vjudge, nunca visual ni voz. Diagnóstico añadido (no
  registrado): dado el mismo texto de entrada, el vjudge repite su salida (columna «vjudge igual con misma entrada»), de modo que sus
  diferencias son consecuencia del ASR; en D (ASR idéntico) todas las pistas son idénticas.
- ES2002c.Room (reunión): el modo R es estable en esta cadena (el ASR ref fue idéntico en las 3 corridas), así que su piso de ruido es 1,0 y la
  enmienda de EXP-045-Q, aplicada literalmente, exige a la variante una igualdad exacta en ese video.
"""


def fmt(x, p=3):
    if x is None:
        return "—"
    if isinstance(x, float) and x == float("inf"):
        return "inf"
    return f"{x:.{p}f}" if isinstance(x, float) else str(x)


def write_report(res, out):
    L = ["# EXP-046-STAB · Resultado", "",
         f"Corridas completadas: {len(res['inventory'])}/60; faltan: {res['missing'] or 'ninguna'}.", ""]
    dec = res["decision"]
    L += ["## Lectura pre-declarada (aplicada literalmente)", "",
          f"Criterio: {dec['criterion']}.", "",
          "| video | piso de ruido ARI modo R (misma máquina) | ARI mínimo modo D (misma máquina) |", "|---|---|---|"]
    for v in VIDS:
        L.append(f"| {v} | {fmt(dec['R_same_machine_min_ari'][v], 4)} | {fmt(dec['D_same_machine_min_ari'][v], 4)} |")
    L += ["", f"**Adopción de D: {'SÍ' if dec['adopt_D'] else 'NO'}**", ""]
    for same, title in ((True, "misma máquina (.56 r1-r3: 3 pares por video y modo)"),
                        (False, "entre máquinas (solo los pares con corrida disponible; el diseño prevé 12 con .54/.55/.61)")):
        key = "same_machine" if same else "cross_machine"
        L += [f"## Piso de ruido — {title}", "",
              "Peor par por métrica (ARI/F1/IoU mínimos; Δ máximos). `id` = pares con partición unidad→tópico idéntica / pares.", "",
              "| modo | video | pares | ARI min | F1 min | Δtóp max | Δret max | IoU hl min | IoU recap min | cap. min | G igual | id |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for mode in MODES:
            for v in VIDS:
                f = (res["floors"].get(f"{mode}/{v}") or {}).get(key)
                if not f:
                    L.append(f"| {mode} | {v} | 0 | sin datos ||||||||")
                    continue
                L.append(f"| {mode} | {v} | {f['n_pairs']} | {fmt(f['ari_unit_topic'], 4)} | {fmt(f['f1_boundaries_pm1'], 4)} | {fmt(f['delta_n_topics_rel'])} | "
                         f"{fmt(f['delta_returns_rel'])} | {fmt(f['iou_highlights10pct'])} | {fmt(f['iou_recap60'])} | "
                         f"{fmt(f['chapters_same_topics_j09'])} | {f['G_version_equal_all']} | {f['n_pairs_partition_identical']}/{f['n_pairs']} |")
        L.append("")
    L += ["## Diferencias por pista (peor par de la misma máquina; WER del ASR entre transcripciones, coseno SigLIP/bge, similitud del vjudge)", "",
          "| modo | video | WER ASR máx | segmentos ASR idénticos (pares) | SigLIP cos mín | bge transc. cos mín | vjudge cos mediana mín | vjudge idénticos mín | vjudge igual con misma entrada | voz idéntica |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for mode in MODES:
        for v in VIDS:
            ps = [p for p in res["pairs"].get(f"{mode}/{v}", []) if p["same_machine"]]
            if not ps:
                continue
            tr = [p["tracks"] for p in ps]
            vj = [t["vjudge_text"] for t in tr if "median" in t["vjudge_text"]]
            gi = [t["vjudge_given_input"] for t in tr if "vjudge_given_input" in t]
            gi_s = (f"{sum(g['same_output_given_same_input'] for g in gi)}/{sum(g['blocks_same_input'] for g in gi)}"
                    f" (con entrada distinta: {sum(g['same_output_given_diff_input'] for g in gi)}/{sum(g['blocks_diff_input'] for g in gi)})") if gi else "—"
            L.append(f"| {mode} | {v} | {fmt(max(t['asr_wer'] for t in tr), 4)} | {sum(t['asr_segments_identical'] for t in tr)}/{len(tr)} | "
                     f"{fmt(min(t['siglip_cos']['min'] for t in tr), 5)} | {fmt(min(t['bge_transcript_cos']['min'] for t in tr), 5)} | "
                     f"{fmt(min(x['median'] for x in vj), 4) if vj else '—'} | {fmt(min(x['identical_frac'] for x in vj), 3) if vj else '—'} | "
                     f"{gi_s} | {all(t['voice_identical'] for t in tr)} |")
    L += ["", "## Atribución (pista de la corrida 2 sustituida en la corrida 1, misma máquina; ARI del mapa recalculado frente al de la corrida 1)", "",
          "| modo | video | par | ARI a-vs-b | ARI ASR | ARI vjudge | ARI visual | ARI voz | fuente principal | recálculo reproduce a |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for mode in MODES:
        for v in VIDS:
            for pair, at in (res["attribution"].get(f"{mode}/{v}") or {}).items():
                t = at["ari_by_track"]
                L.append(f"| {mode} | {v} | {pair} | {fmt(at['ari_a_vs_b'], 4)} | {fmt(t['asr'], 4)} | {fmt(t['vjudge'], 4)} | "
                         f"{fmt(t['visual'], 4)} | {fmt(t['voice'], 4)} | {at['main_source'] or 'ninguna (ARI = 1 en todas)'} | "
                         f"{at['sanity_rebuild_reproduces_a']['partition_identical']} |")
    L += ["", "## Re-evaluación de EXP-045-Q según la enmienda declarada", ""]
    for tag, r in res["reeval_exp045q"].items():
        L += [f"### {tag}: extremo a extremo **{'PASA' if r['adopted_e2e'] else 'NO PASA'}** frente al piso de R", "",
              "| video | ARI (≥ piso) | F1 (≥) | Δtóp (≤) | Δret (≤) | IoU hl (≥) | IoU recap (≥) | pasa |", "|---|---|---|---|---|---|---|---|"]
        for v, x in r["per_video"].items():
            if "error" in x:
                L.append(f"| {v} | {x['error']} |||||||")
                continue
            m, f = x["variant_vs_ref"], x["floor_R"]
            c = x["pass_by_metric"]
            cell = lambda k: f"{fmt(m[k], 4)} vs {fmt(f[k], 4)} {'✓' if c[k] else '✗'}"  # noqa: E731
            L.append(f"| {v} | {cell('ari_unit_topic')} | {cell('f1_boundaries_pm1')} | {cell('delta_n_topics_rel')} | "
                     f"{cell('delta_returns_rel')} | {cell('iou_highlights10pct')} | {cell('iou_recap60')} | {x['pass']} |")
        L.append("")
    L += ["", NOTES]
    (out / "report.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
