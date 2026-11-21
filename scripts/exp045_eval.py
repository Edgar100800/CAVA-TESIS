"""EXP-045-Q: tablas de tolerancia ref vs fast sobre refset_v1 (todas las métricas registradas).

Uso: python scripts/exp045_eval.py --out results/exp045_q
Lee /data/tesis-cava/exp045/{runs,vox,diag}; escribe asr/embeddings/llm/e2e/timing .json en --out.
Lecturas fijadas al ejecutar (el registro no las especifica; los umbrales no cambian):
  - WER <= 3 %: WER agrupado (suma de errores / suma de palabras ref) sobre todos los archivos; se reporta por archivo.
  - Embeddings: mediana y p1 del coseno agrupando todas las unidades (ambos vectores no nulos).
  - Extremo a extremo: umbral exigido a CADA video (lectura estricta); se reporta también el agrupado.
"""
import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp045_common import EXP, VIDEOS, e2e_metrics, load_run  # noqa: E402
from topicagg.versions import check_versions  # noqa: E402

VOX = "abjxc afjiv ahnss aisvi akthc ampme asxwr atgpi aufkn azisu bauzd bdopb bkwns blwmj bravd bspxd bwzyf bxpwa bydui ccokr".split()
AMI_WORDS = Path("/data/tesis-cava/exp044/data/ami/annotations/words")
FROZEN = {"Spider_Man": Path("/data/tesis-cava/CAVA_minimo/outputs/Spider_Man"),
          "bbc_01": Path("/data/tesis-cava/v11_work/inputs/bbc_01_frozen")}


# ---------------------------------------------------------------- utilidades
def words(text):
    return re.sub(r"[^\w\s']", " ", text.lower().replace("’", "'")).split()


def lev(a, b):
    """Distancia de Levenshtein entre listas de palabras (DP vectorizado por filas)."""
    if not a:
        return len(b)
    if not b:
        return len(a)
    vocab = {w: i for i, w in enumerate(set(a) | set(b))}
    A, B = np.array([vocab[w] for w in a]), np.array([vocab[w] for w in b])
    m = len(B)
    prev = np.arange(m + 1)
    idx = np.arange(m + 1)
    for i in range(1, len(A) + 1):
        cost = (B != A[i - 1]).astype(np.int64)
        tmp = np.empty(m + 1, np.int64)
        tmp[0] = i
        tmp[1:] = np.minimum(prev[1:] + 1, prev[:-1] + cost)
        prev = np.minimum.accumulate(tmp - idx) + idx
    return int(prev[m])


def seg_text(segs):
    return " ".join(t for *_, t in segs)


def cos_rows(a, b):
    na, nb = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
    ok = (na > 0) & (nb > 0)
    c = np.full(len(a), np.nan)
    c[ok] = (a[ok] * b[ok]).sum(1) / (na[ok] * nb[ok])
    return c, ok


def dist(c):
    c = np.asarray(c, float)
    c = c[~np.isnan(c)]
    return {"n": int(len(c)), "median": float(np.median(c)), "p1": float(np.percentile(c, 1)),
            "min": float(c.min()), "mean": float(c.mean())} if len(c) else {"n": 0}


def gate(units, segs):
    return np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in segs) >= 0.5 * (u1 - u0) for u0, u1 in units])


def load_ref_asr(n):
    st = json.loads((EXP / f"runs/ref/{n}/work/state.json").read_text())
    return st["asr_segments"], st["units"], st["duration"]


def load_fast_asr(n):
    return json.loads((EXP / f"runs/fast/{n}/work/asr.fast.json").read_text())["segments"]


def ami_gt_words():
    ws = []
    for f in sorted(AMI_WORDS.glob("ES2002c.*.words.xml")):
        for el in ET.parse(f).getroot().iter():
            if el.tag.endswith("}w") or el.tag == "w":
                if el.get("punc") == "true" or not (el.text or "").strip() or el.get("starttime") is None:
                    continue
                ws.append((float(el.get("starttime")), el.text.strip()))
    ws.sort()
    return words(" ".join(w for _, w in ws))


# ---------------------------------------------------------------- pistas
def track_asr():
    rows, E, N = {}, 0, 0
    for n in VIDEOS:
        r, units, dur = load_ref_asr(n)
        f = load_fast_asr(n)
        wr, wf = words(seg_text(r)), words(seg_text(f))
        e = lev(wr, wf)
        g1, g2 = gate(units, r), gate(units, f)
        rows[n] = {"kind": "pipeline", "n_words_ref": len(wr), "n_words_fast": len(wf), "edits": e,
                   "wer_vs_ref": e / max(len(wr), 1), "n_units": len(units), "gate_equal_units": int((g1 == g2).sum()),
                   "gate_equal_frac": float((g1 == g2).mean()), "duration_s": dur}
        E, N = E + e, N + len(wr)
    vE, vN, vG, vU = 0, 0, 0, 0
    for u in VOX:
        pr, pf = EXP / f"vox/ref/{u}.asr.json", EXP / f"vox/fast/{u}.asr.json"
        if not (pr.exists() and pf.exists()):
            continue
        r, f = json.loads(pr.read_text()), json.loads(pf.read_text())
        wr, wf = words(seg_text(r)), words(seg_text(f))
        e = lev(wr, wf)
        tm = json.loads((EXP / "vox/ref/timings.json").read_text())["duration_s"][u]
        units = [[float(s), float(min(s + 5.0, tm))] for s in np.arange(0, tm - 1, 5.0)]
        g1, g2 = gate(units, r), gate(units, f)
        rows[f"vox:{u}"] = {"kind": "vox", "n_words_ref": len(wr), "edits": e, "wer_vs_ref": e / max(len(wr), 1),
                            "n_units": len(units), "gate_equal_frac": float((g1 == g2).mean())}
        vE, vN, vG, vU = vE + e, vN + len(wr), vG + int((g1 == g2).sum()), vU + len(units)
    allE, allN = E + vE, N + vN
    pipe_units = sum(r["n_units"] for r in rows.values() if r["kind"] == "pipeline")
    pipe_eq = sum(r["gate_equal_units"] for r in rows.values() if r["kind"] == "pipeline")
    # AMI con GT
    gt = ami_gt_words()
    r, _, _ = load_ref_asr("ES2002c.Room")
    f = load_fast_asr("ES2002c.Room")
    er, ef = lev(gt, words(seg_text(r))), lev(gt, words(seg_text(f)))
    ami = {"n_gt_words": len(gt), "wer_ref_vs_gt": er / len(gt), "wer_fast_vs_gt": ef / len(gt),
           "delta_pp": 100 * (ef - er) / len(gt)}
    pooled = allE / max(allN, 1)
    worst = max(rows.items(), key=lambda kv: kv[1]["wer_vs_ref"])
    res = {"per_file": rows,
           "wer_pooled_all": pooled, "wer_pooled_pipeline": E / max(N, 1), "wer_pooled_vox": vE / max(vN, 1),
           "n_files": len(rows), "files_above_3pct": [k for k, v in rows.items() if v["wer_vs_ref"] > 0.03],
           "worst_file": {worst[0]: worst[1]["wer_vs_ref"]},
           "gate_equal_frac_pipeline": pipe_eq / pipe_units, "gate_equal_frac_vox": (vG / vU) if vU else None,
           "gate_equal_frac_all": (pipe_eq + vG) / (pipe_units + vU), "ami_gt": ami}
    res["pass"] = {"wer_le_3pct": pooled <= 0.03, "ami_delta_wer_le_0.5pp": ami["delta_pp"] <= 0.5,
                   "gate_equal_ge_99pct": res["gate_equal_frac_all"] >= 0.99}
    res["pass_all"] = all(res["pass"].values())
    return res


def check_emb(dists, label):
    ok = {"median_ge_0.995": dists["pooled"]["median"] >= 0.995, "p1_ge_0.98": dists["pooled"]["p1"] >= 0.98}
    return {"pooled": dists["pooled"], "per_video": dists["per_video"], "pass": ok, "pass_all": all(ok.values()), "label": label}


def track_embeddings():
    out = {}
    # SigLIP: fast completo (decode-once + FP16 lotes) y diagnóstico FP16 sobre fotogramas exactos
    for tag, loader in (("siglip_fast", lambda n: np.load(EXP / f"runs/fast/{n}/work/signals.visual.fast.npy")),
                        ("siglip_fp16_exact_frames_diag", lambda n: np.load(EXP / f"runs/diag/{n}/visual_fp16_exact.npy"))):
        allc, per, mism = [], {}, {}
        for n in VIDEOS:
            try:
                ref = dict(np.load(EXP / f"runs/ref/{n}/work/signals.npz"))["visual"]
                cand = loader(n)
            except FileNotFoundError:
                continue
            c, ok = cos_rows(ref, cand)
            per[n] = dist(c)
            mism[n] = {"units": len(ref), "null_mismatch": int(((np.linalg.norm(ref, axis=1) > 0) != (np.linalg.norm(cand, axis=1) > 0)).sum())}
            allc.append(c)
        if allc:
            out[tag] = check_emb({"pooled": dist(np.concatenate(allc)), "per_video": per}, tag) | {"null_mask_mismatch": mism}
    # bge GPU FP16 vs CPU FP32 (texto ASR por unidad y resúmenes ref)
    for tag, key in (("bge_transcript_units", "asr"), ("bge_vjudge_blocks", "vj")):
        allc, per = [], {}
        for n in VIDEOS:
            try:
                a, b = np.load(EXP / f"runs/diag/{n}/bge_{key}_cpu.npy"), np.load(EXP / f"runs/diag/{n}/bge_{key}_gpu.npy")
            except FileNotFoundError:
                continue
            c, ok = cos_rows(a, b)
            c = c[ok]
            per[n] = dist(c)
            allc.append(c)
        if allc:
            out[tag] = check_emb({"pooled": dist(np.concatenate(allc)), "per_video": per}, tag)
    # WavLM FP16 vs FP32: VoxConverse dev (mismo gate) y x-vectors de los documentales de la corrida
    allc, per = [], {}
    for u in VOX:
        pr, pf = EXP / f"vox/ref/{u}.xvec.npy", EXP / f"vox/fast/{u}.xvec.npy"
        if pr.exists() and pf.exists():
            c, ok = cos_rows(np.load(pr), np.load(pf))
            per[f"vox:{u}"] = dist(c)
            allc.append(c)
    for n in VIDEOS:
        pr, pf = EXP / f"runs/ref/{n}/work/speaker_xvec.npy", EXP / f"runs/fast/{n}/work/speaker_xvec.fast.npy"
        if pr.exists() and pf.exists():
            c, ok = cos_rows(np.load(pr), np.load(pf))
            per[n] = dist(c)
            allc.append(c)
    if allc:
        out["wavlm_fp16"] = check_emb({"pooled": dist(np.concatenate(allc)), "per_video": per}, "wavlm_fp16")
    out["faces"] = {"status": "no_evaluada", "reason": "variante de rostros no definida entre las variantes de esta validación; "
                    "buffalo_l es research_only y no está en el pipeline de producto"}
    return out


def track_llm():
    from topicagg.embed import BgeEmbedder
    from topicagg.labels import clean_label
    bge = BgeEmbedder()
    out = {}
    pairs = {"vjudge": [], "labels": []}
    specs = {"vjudge_vllm_exact_frames": ("abl/vjudge-fast_exact", "summaries.fast_exact.json", "summaries.json"),
             "vjudge_vllm_decode_once": ("abl/vjudge-fast", "summaries.fast.json", "summaries.json"),
             "vjudge_chain_fast_all_tracks": ("fast", "summaries.fast.json", "summaries.json")}
    for tag, (d, fast_f, ref_f) in specs.items():
        per, allc, ident, tot = {}, [], 0, 0
        for n in VIDEOS:
            pf, pr = EXP / f"runs/{d}/{n}/work/{fast_f}", EXP / f"runs/ref/{n}/work/{ref_f}"
            if not (pf.exists() and pr.exists()):
                continue
            r, f = json.loads(pr.read_text()), json.loads(pf.read_text())
            tr, tf = [s["summary"] for s in r], [s["summary"] for s in f]
            c = (bge(tr) * bge(tf)).sum(1)
            same = sum(x.strip() == y.strip() for x, y in zip(tr, tf))
            per[n] = {**dist(c), "identical": same, "n": len(tr)}
            allc.append(c)
            ident, tot = ident + same, tot + len(tr)
            if tag == "vjudge_vllm_exact_frames":
                pairs["vjudge"] += [{"video": n, "block": i, "ref": x, "fast": y} for i, (x, y) in enumerate(zip(tr, tf))]
        if allc:
            pooled = dist(np.concatenate(allc))
            ok = {"median_cos_ge_0.90": pooled["median"] >= 0.90}
            out[tag] = {"pooled": pooled, "identical_frac": ident / tot, "n": tot, "per_video": per, "pass_automatic": ok,
                        "human_review": "pendiente de revisión humana"}
    per, allc, ident, tot = {}, [], 0, 0
    for n in VIDEOS:
        pf = EXP / f"runs/abl/labels-fast+LBL/{n}/work/topic_labels.fast.json"
        pr = EXP / f"runs/ref/{n}/work/topic_labels.json"
        if not (pf.exists() and pr.exists()):
            continue
        r, f = json.loads(pr.read_text()), json.loads(pf.read_text())
        keys = [k for k in r if k in f]
        tr, tf = [clean_label(r[k]) for k in keys], [clean_label(f[k]) for k in keys]
        if not keys:
            continue
        c = (bge(tr) * bge(tf)).sum(1)
        same = sum(x == y for x, y in zip(tr, tf))
        per[n] = {**dist(c), "identical": same, "n": len(keys), "keys_ref": len(r), "keys_fast": len(f), "keys_common": len(keys)}
        allc.append(c)
        ident, tot = ident + same, tot + len(keys)
        pairs["labels"] += [{"video": n, "key": k, "ref": x, "fast": y} for k, x, y in zip(keys, tr, tf)]
    if allc:
        pooled = dist(np.concatenate(allc))
        out["labels_vllm_fp8"] = {"pooled": pooled, "identical_frac": ident / tot, "n": tot, "per_video": per,
                                  "pass_automatic": {"median_cos_ge_0.90": pooled["median"] >= 0.90},
                                  "human_review": "pendiente de revisión humana"}
    out["_pairs"] = pairs
    return out


# ---------------------------------------------------------------- extremo a extremo
def track_e2e():
    out = {"specs": {}}
    specs = {"asr=fast": "abl/asr-fast", "visual=fast": "abl/visual-fast", "vjudge=fast": "abl/vjudge-fast",
             "vjudge=fast_exact(diag)": "abl/vjudge-fast_exact", "embed=fast": "abl/embed-fast",
             "ALL_fast_chain": "fast"}
    for p in sorted((EXP / "runs/abl").glob("*")) if (EXP / "runs/abl").exists() else []:
        key = f"abl/{p.name}"
        if key not in specs.values() and not p.name.endswith("+LBL"):
            specs[p.name] = key
    for label, d in specs.items():
        per = {}
        for n in VIDEOS:
            rd, rv = load_run(EXP / f"runs/ref/{n}") if (EXP / f"runs/ref/{n}/topic_map.json").exists() else (None, None)
            cp = EXP / f"runs/{d}/{n}"
            if rd is None or not (cp / "topic_map.json").exists():
                continue
            cd, cv = load_run(cp)
            per[n] = e2e_metrics(rd, rv, cd, cv, check_versions)
        if per:
            out["specs"][label] = {"per_video": per, "pass_all_videos": all(v["pass_all"] for v in per.values()),
                                   "videos_failing": [n for n, v in per.items() if not v["pass_all"]]}
    # piso de ruido: corrida ref nueva vs congelada (mismo código, otra GPU/biblioteca)
    floor = {}
    for n, fz in FROZEN.items():
        if (EXP / f"runs/ref/{n}/topic_map.json").exists() and (fz / "topic_map.json").exists():
            rd, rv = load_run(EXP / f"runs/ref/{n}")
            cd, cv = load_run(fz)
            floor[n] = e2e_metrics(cd, cv, rd, rv, check_versions)
    out["noise_floor_ref_vs_frozen"] = floor
    return out


# ---------------------------------------------------------------- clips (NVENC)
def clip_durations(d, fast):
    """{archivo: duración_s} de los clips de una corrida (ffprobe local o el txt calculado en la máquina que los cortó)."""
    import subprocess
    d = Path(d)
    txt = d / "clips_fast_durations.txt"
    if txt.exists():
        return {a: float(b) for a, b in (l.split() for l in txt.read_text().splitlines() if l.strip())}
    res = {}
    for p in sorted((d / ("clips.fast" if fast else "clips")).glob("*.mp4")):
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True)
        if r.stdout.strip():
            res[p.name] = float(r.stdout)
    return res


def track_clips():
    out = {}
    for n in VIDEOS:
        row = {}
        for v in ("ref", "fast"):
            d = EXP / f"runs/{v}/{n}"
            if not d.exists():
                continue
            durs = clip_durations(d, v == "fast")
            dev = []
            for name, du in durs.items():
                m = re.search(r"_(\d+\.\d+)-(\d+\.\d+)\.mp4$", name)
                if m:
                    dev.append(du - (float(m.group(2)) - float(m.group(1))))
            row[v] = {"n_clips": len(durs), "max_abs_dev_s": float(np.max(np.abs(dev))) if dev else None,
                      "mean_dev_s": float(np.mean(dev)) if dev else None}
        out[n] = row
    return out


# ---------------------------------------------------------------- tiempos
def track_timing():
    out = {"per_video": {}, "stages": {}}
    stages = ["prepare", "asr", "signals", "vjudge", "topic_map", "labels", "speakers", "versions_and_clips"]
    tot = {"ref": {s: 0.0 for s in stages}, "fast": {s: 0.0 for s in stages}}
    hours = {"ref": 0.0, "fast": 0.0}
    for n in VIDEOS:
        row = {}
        for v in ("ref", "fast"):
            f = EXP / f"runs/{v}/{n}/run_manifest.json"
            if not f.exists():
                continue
            m = json.loads(f.read_text())
            tms = dict(m["timings_s"])
            note = None
            if v == "ref" and n == "Spider_Man":
                # la 1.ª pasada falló en pyannote (LD_LIBRARY_PATH) y la reanudación no cronometró las etapas cacheadas:
                # asr/signals/vjudge/labels se reconstruyen de las mtimes de work/ de la 1.ª pasada (ver spider_ref_firstpass_mtimes.txt)
                tms.update({"asr": 696 - 409, "signals": 971 - 696, "vjudge": 1280 - 971,
                            "labels": round((2132 - 1280) - tms["topic_map"], 1)})
                note = "asr/signals/vjudge/labels reconstruidos por mtimes (1.ª pasada)"
            fp = EXP / f"runs/{v}/{n}/run_manifest.first_pass.json"
            if v == "fast" and fp.exists():
                # Spider fast: NVENC falló en la 1.ª pasada (fuente H.264 10 bits) y se repitió solo la etapa de clips con -pix_fmt yuv420p;
                # el resto de etapas toma los tiempos de la 1.ª pasada (la repetición las leyó de caché)
                first = json.loads(fp.read_text())["timings_s"]
                first["versions_and_clips"] = tms["versions_and_clips"]
                tms = first
                note = "etapas de la 1.ª pasada; versions_and_clips de la repetición con -pix_fmt yuv420p"
            m["timings_s"] = tms
            row[v] = {"timings_s": tms, "duration_s": m["video"]["duration_s"],
                      "detail": m.get("timings_detail_s"), "note": note}
            for s in stages:
                tot[v][s] += m["timings_s"].get(s, 0.0)
            hours[v] += m["video"]["duration_s"] / 3600
        out["per_video"][n] = row
    for s in stages:
        r, f = (tot["ref"][s] / hours["ref"] if hours["ref"] else None), (tot["fast"][s] / hours["fast"] if hours["fast"] else None)
        out["stages"][s] = {"ref_s_per_h": r, "fast_s_per_h": f, "speedup": (r / f) if r and f else None}
    tr, tf = sum(tot["ref"].values()), sum(tot["fast"].values())
    out["total"] = {"ref_s_per_h": tr / hours["ref"] if hours["ref"] else None, "fast_s_per_h": tf / hours["fast"] if hours["fast"] else None,
                    "hours_ref": hours["ref"], "hours_fast": hours["fast"]}
    if hours["ref"] and hours["fast"]:
        out["total"]["speedup"] = out["total"]["ref_s_per_h"] / out["total"]["fast_s_per_h"]
    # etapas aisladas (un cliente a la vez)
    iso = {}
    for d in (EXP / "runs/abl").glob("*") if (EXP / "runs/abl").exists() else []:
        for n in VIDEOS:
            f = d / n / "timings.json"
            if f.exists():
                iso.setdefault(d.name, {})[n] = json.loads(f.read_text())
    out["isolated_runs"] = iso
    # vox
    vox = {}
    for v in ("ref", "fast"):
        f = EXP / f"vox/{v}/timings.json"
        if f.exists():
            t = json.loads(f.read_text())
            h = sum(t["duration_s"].values()) / 3600
            vox[v] = {"hours": h, "asr_s_per_h": t.get("asr_total_s", 0) / h, "xvec_s_per_h": t.get("xvec_total_s", 0) / h}
    out["vox"] = vox
    for n in VIDEOS:
        f = EXP / f"runs/diag/{n}/voice_s.json"
        if f.exists():
            out.setdefault("voice_only_s", {})[n] = json.loads(f.read_text())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results/exp045_q")
    ap.add_argument("--parts", default="asr,emb,llm,e2e,timing,clips")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    fns = {"asr": track_asr, "emb": track_embeddings, "llm": track_llm, "e2e": track_e2e, "timing": track_timing,
           "clips": track_clips}
    for p in a.parts.split(","):
        res = fns[p]()
        if p == "llm":
            (out / "human_review_answer_key").mkdir(exist_ok=True)  # pares con su origen: fuera de human_review/ (ciego)
            (out / "human_review_answer_key/llm_pairs_all.json").write_text(json.dumps(res.pop("_pairs"), ensure_ascii=False, indent=1))
        (out / f"{p}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        print("escrito", p, flush=True)


if __name__ == "__main__":
    main()
