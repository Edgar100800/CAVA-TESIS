"""EXP-036 F5 piloto de tramos: briefs F1 por tramos fijos de 40 s dentro de escenas F2 largas.

Pre-registro: exp036/f5/TRAMO_PILOT_PREREG.md. Reutiliza SIN modificar exp036/scripts/f1_briefs.py:
PROMPT, validate, evidence_lines, MID/REV (mismo modelo, revisión, registro y decodificación greedy).
Diferencias de ingeniería: generación por lotes con relleno a la izquierda y presupuestos escalonados
900 -> 1600 -> 3500 -> 8000 (se reintenta solo lo truncado, como F1 + enmienda 8000).

Uso (desde /data/tesis-cava):
  P=CAVA_minimo/.venv/bin/python
  $P -I exp036/f5/tramos/tramo_briefs.py --dry-run
  $P -I exp036/f5/tramos/tramo_briefs.py --batch 8 [--limit N] [--movies Spider_Man]
  $P -I exp036/f5/tramos/tramo_briefs.py --selftest

Cobertura completa (F5_METHOD_AMENDMENT_v1.md), repartida entre PCs:
  $P -I exp036/f5/tramos/tramo_briefs.py --make-manifest exp036/f5/tramos/full/manifest_full.json --shards 4
  $P -I exp036/f5/tramos/tramo_briefs.py --manifest <manifest> --shard K/4 --out-dir <dir> [--cava <raíz CAVA>]
  (en las PCs L507 la raíz CAVA es /data/tesis-cava/cava-exp036; aquí, /data/tesis-cava/CAVA_minimo)
Las particiones son disjuntas: cada tramo pendiente tiene un único `shard` en el manifiesto. El trabajador
recalcula la evidencia y exige el mismo sha256 que el manifiesto; si no coincide, no genera esa unidad.
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "exp036"
CAVA = ROOT / "CAVA_minimo" if (ROOT / "CAVA_minimo").exists() else ROOT
OUT = Path(__file__).resolve().parent
MOVIE_ORDER = ["Avengers_Endgame", "Spider_Man"]
sys.path.insert(0, str(EXP / "scripts"))
from f1_briefs import MID, PROMPT, REV, evidence_lines, hms, validate  # noqa: E402

SELECTED = {"Avengers_Endgame": [37, 40], "Spider_Man": [30, 42]}   # pre-registrado
TRAMO_UNITS, MIN_LAST_S = 8, 20.0
BUDGETS = [900, 1600, 3500, 8000]


def make_tramos(scene, units):
    """Tramos de 8 unidades desde u0; un resto < 20 s se une al tramo anterior."""
    u0, u1 = scene["u0"], scene["u1"]
    cuts = list(range(u0, u1, TRAMO_UNITS)) + [u1]
    if len(cuts) > 2 and units[u1 - 1][1] - units[cuts[-2]][0] < MIN_LAST_S:
        cuts.pop(-2)
    return [(units[a][0], units[b - 1][1]) for a, b in zip(cuts[:-1], cuts[1:])]


def ev_sha(ev):
    return hashlib.sha256("\n".join(ev).encode()).hexdigest()


def load_movie(mov, scene_ids=None):
    """scene_ids=None -> escenas pre-registradas del piloto; "all" -> todas las escenas F2."""
    md = CAVA / "outputs" / mov
    st = json.loads((md / "work/state.json").read_text())
    units = [tuple(u) for u in st["units"]]
    asr = st.get("asr_segments", [])
    summ = json.loads((md / "work/summaries.json").read_text())
    reg_txt = (md / "characters_registry.txt").read_text() if (md / "characters_registry.txt").exists() else ""
    reg_names = tuple(l.split(" - ")[0].strip() for l in reg_txt.splitlines() if " - " in l)
    registry = f"CHARACTER REGISTRY (automatic, may be incomplete):\n{reg_txt.strip()}\n\n" if reg_txt.strip() else ""
    esc = {s["scene_id"]: s for s in json.loads((EXP / "outputs" / mov / "escenas.json").read_text())["scenes"]}
    todo = []
    for sid in (sorted(esc) if scene_ids == "all" else SELECTED[mov] if scene_ids is None else scene_ids):
        s = esc[sid]
        for k, (a, b) in enumerate(make_tramos(s, units)):
            ev = evidence_lines([[a, b]], units, summ, asr, frozenset(s["mixed_blocks"]))
            todo.append({"uid": f"S{sid}_T{k:02d}", "scene": f"S{sid}", "scene_id": sid, "k": k, "t0": a, "t1": b,
                         "t0_hms": hms(a), "t1_hms": hms(b), "mixed_blocks": s["mixed_blocks"],
                         "evidence": ev, "ev_sha": ev_sha(ev),
                         "prompt": PROMPT.format(registry=registry, evidence="\n".join(ev))})
    return todo, reg_names


def make_manifest(path, n_shards):
    """Todos los tramos de todas las escenas; los ok del piloto quedan marcados y fuera de las particiones.
    Orden determinista (película, escena, k); partición = índice entre pendientes % n_shards."""
    entries, pend = [], 0
    for mov in MOVIE_ORDER:
        todo, _ = load_movie(mov, "all")
        pf = OUT / f"briefs_tramos_{mov}.json"
        pilot = json.loads(pf.read_text()) if pf.exists() else {}
        for u in todo:
            p = pilot.get(u["uid"])
            done = bool(p and p.get("status") == "ok")
            if done:   # el piloto debe ser exactamente el mismo tramo y la misma evidencia
                assert abs(p["t0"] - u["t0"]) < 1e-6 and abs(p["t1"] - u["t1"]) < 1e-6
                assert p["n_evidence"] == len(u["evidence"]), u["uid"]
            e = {"movie": mov, "uid": u["uid"], "scene": u["scene"], "t0": u["t0"], "t1": u["t1"],
                 "n_evidence": len(u["evidence"]), "ev_sha": u["ev_sha"], "pilot_done": done,
                 "shard": None if done else pend % n_shards}
            pend += 0 if done else 1
            entries.append(e)
    doc = {"built": time.strftime("%Y-%m-%d %H:%M:%S"), "n_shards": n_shards, "n_total": len(entries),
           "n_pilot_done": sum(e["pilot_done"] for e in entries), "n_pending": pend,
           "per_shard": {k: sum(e["shard"] == k for e in entries) for k in range(n_shards)}, "entries": entries}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=1))
    print(json.dumps({k: v for k, v in doc.items() if k != "entries"}))


def gen_batch(model, tok, chats, budget, eos):
    import torch
    enc = tok(chats, return_tensors="pt", padding=True).to(model.device)
    with torch.inference_mode():
        g = model.generate(**enc, max_new_tokens=budget, do_sample=False, pad_token_id=tok.pad_token_id)
    outs = []
    L = enc.input_ids.shape[1]
    for i in range(len(chats)):
        new = g[i, L:].tolist()
        n = next((j for j, t in enumerate(new) if t in eos), len(new))
        outs.append((tok.decode(new[:n], skip_special_tokens=True).strip(), n, n >= budget))
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--movies", nargs="+", default=list(SELECTED))
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gpu-mem", default="15GiB")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cava", help="raíz CAVA (outputs/, models/); por defecto CAVA_minimo local")
    ap.add_argument("--out-dir", help="carpeta de salida (por defecto, la del piloto)")
    ap.add_argument("--make-manifest", metavar="PATH")
    ap.add_argument("--shards", type=int, default=4)
    ap.add_argument("--manifest")
    ap.add_argument("--shard", help="K/N: procesa solo los tramos del manifiesto con shard == K")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    global CAVA, OUT
    if a.cava:
        CAVA = Path(a.cava)
    if a.make_manifest:
        return make_manifest(a.make_manifest, a.shards)
    out_dir = Path(a.out_dir) if a.out_dir else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    assign = None
    if a.manifest:
        man = json.loads(Path(a.manifest).read_text())
        k, n = map(int, a.shard.split("/"))
        assert n == man["n_shards"], (n, man["n_shards"])
        assign = {(e["movie"], e["uid"]): e for e in man["entries"] if e["shard"] == k}
        a.movies = [m for m in MOVIE_ORDER if any(mv == m for mv, _ in assign)]
        print(f"[tramos] manifiesto {a.manifest} shard {k}/{n}: {len(assign)} tramos asignados", flush=True)
    os.environ.update(HF_HOME=str(CAVA / "models"), HF_HUB_CACHE=str(CAVA / "models/hub"),
                      HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MID, revision=REV)
    tok.padding_side = "left"
    eos = {tok.convert_tokens_to_ids("<|im_end|>"), tok.convert_tokens_to_ids("<|endoftext|>")}

    jobs = []
    for mov in a.movies:
        todo, reg_names = load_movie(mov, "all" if assign is not None else None)
        f_out = out_dir / f"briefs_tramos_{mov}.json"
        done = json.loads(f_out.read_text()) if f_out.exists() else {}
        if assign is not None:
            todo = [u for u in todo if (mov, u["uid"]) in assign]
            assert len(todo) == sum(1 for mv, _ in assign if mv == mov), (mov, len(todo))
            bad = [u for u in todo if u["ev_sha"] != assign[(mov, u["uid"])]["ev_sha"]
                   or abs(u["t0"] - assign[(mov, u["uid"])]["t0"]) > 1e-6]
            for u in bad:
                print(f"[tramos] EVIDENCIA DISTINTA {mov} {u['uid']}: no se genera", flush=True)
                done[u["uid"]] = {"movie": mov, "scene": u["scene"], "t0": u["t0"], "t1": u["t1"],
                                  "status": "failed", "brief": None, "attempts": [],
                                  "problems": {"hard": ["evidence_mismatch"], "warn": []}}
            todo = [u for u in todo if u not in bad]
            if bad:
                f_out.write_text(json.dumps(done, ensure_ascii=False, indent=1))
        for u in todo:
            u["chat"] = tok.apply_chat_template([{"role": "user", "content": u["prompt"]}], tokenize=False,
                                                add_generation_prompt=True)
            u["n_in"] = len(tok(u["chat"]).input_ids)
            u.update(mov=mov, reg=reg_names, f_out=f_out)
        jobs += [(u, done) for u in todo]
    if a.dry_run:
        n = [u["n_in"] for u, _ in jobs]
        print(json.dumps({"tramos": len(jobs), "por_escena": {s: sum(1 for u, _ in jobs if f"{u['mov']}:{u['scene']}" == s)
                          for s in sorted({f"{u['mov']}:{u['scene']}" for u, _ in jobs})},
                          "prompt_tokens_mediana": sorted(n)[len(n) // 2], "prompt_tokens_max": max(n),
                          "evidencias_max": max(len(u["evidence"]) for u, _ in jobs)}, indent=1))
        return
    pending = [(u, d) for u, d in jobs if d.get(u["uid"], {}).get("status") != "ok"]
    if a.limit:
        pending = pending[:a.limit]
    print(f"[tramos] pendientes {len(pending)}/{len(jobs)}", flush=True)
    if not pending:
        return

    import torch
    from transformers import AutoModelForCausalLM
    t_load = time.time()
    model = AutoModelForCausalLM.from_pretrained(MID, revision=REV, dtype=torch.bfloat16, device_map="auto",
                                                 max_memory={0: a.gpu_mem, "cpu": "58GiB"}).eval()
    print(f"[tramos] modelo cargado en {time.time() - t_load:.0f}s", flush=True)
    t_gen0 = time.time()
    # clave (película, uid): los uid "S<n>_T<k>" se repiten entre películas. Con clave solo uid, dos tramos de
    # películas distintas en el mismo job compartían registro (bug de la cobertura completa v1).
    key = lambda u: (u["mov"], u["uid"])
    assert len({key(u) for u, _ in pending}) == len(pending)
    stage = {key(u): 0 for u, _ in pending}
    recs = {key(u): {"movie": u["mov"], "scene": u["scene"], "t0": u["t0"], "t1": u["t1"], "t0_hms": u["t0_hms"],
                       "t1_hms": u["t1_hms"], "n_evidence": len(u["evidence"]), "ev_sha": u["ev_sha"],
                       "prompt_tokens": u["n_in"], "shard": a.shard, "attempts": []} for u, _ in pending}
    assert all(recs[key(u)]["movie"] == u["mov"] and recs[key(u)]["ev_sha"] == u["ev_sha"] for u, _ in pending)
    queue = list(pending)
    for si, budget in enumerate(BUDGETS):
        cur = [(u, d) for u, d in queue if stage[key(u)] == si]
        if not cur:
            continue
        bs = {900: a.batch, 1600: max(1, a.batch // 2)}.get(budget, 1)
        cur.sort(key=lambda x: x[0]["n_in"])
        for i in range(0, len(cur), bs):
            batch = cur[i:i + bs]
            t0 = time.time()
            try:
                outs = gen_batch(model, tok, [u["chat"] for u, _ in batch], budget, eos)
            except torch.OutOfMemoryError:
                torch.cuda.empty_cache()
                outs = []
                for u, _ in batch:
                    try:
                        outs += gen_batch(model, tok, [u["chat"]], budget, eos)
                    except torch.OutOfMemoryError:
                        torch.cuda.empty_cache()
                        outs.append(None)
            dt = time.time() - t0
            for (u, d), o in zip(batch, outs):
                r = recs[key(u)]
                assert r["movie"] == u["mov"] and abs(r["t0"] - u["t0"]) < 1e-6 and r["ev_sha"] == u["ev_sha"]
                if o is None:
                    prob = {"hard": ["oom"], "warn": []}
                    r["attempts"].append({"max_new": budget, "problems": prob, "raw": "", "batch": len(batch)})
                    r.update(status="failed", brief=None, problems=prob)
                else:
                    txt, n, hit = o
                    obj, prob = validate(txt, len(u["evidence"]), hit, u["reg"])
                    r["attempts"].append({"max_new": budget, "gen_tokens": n, "problems": prob, "raw": txt,
                                          "batch": len(batch), "batch_seconds": round(dt, 1)})
                    r.update(status="ok" if not prob["hard"] else "failed", brief=obj, problems=prob)
                    if prob["hard"] and hit and si + 1 < len(BUDGETS):
                        stage[key(u)] = si + 1      # solo se reintenta lo truncado
                d[u["uid"]] = r
                u["f_out"].write_text(json.dumps(d, ensure_ascii=False, indent=1))
            ntok = sum(o[1] for o in outs if o)
            print(f"[tramos] budget={budget} lote {i // bs + 1} ({len(batch)}) {dt:.0f}s gen_tok={ntok} "
                  f"({ntok / dt:.1f} tok/s) " + " ".join(f"{u['mov'][:2]}:{u['uid']}:{recs[key(u)]['status']}" for u, _ in batch),
                  flush=True)
    gpu_s = time.time() - t_gen0
    for mov in a.movies:
        f = out_dir / f"briefs_tramos_{mov}.json"
        if f.exists():
            d = json.loads(f.read_text())
            print(f"[tramos] FIN {mov}: {sum(v['status'] == 'ok' for v in d.values())}/{len(d)} ok", flush=True)
    log = out_dir / "gpu_time.jsonl"
    with open(log, "a") as fh:
        fh.write(json.dumps({"end": time.strftime("%Y-%m-%d %H:%M:%S"), "units": len(pending), "batch": a.batch,
                             "load_s": round(t_gen0 - t_load, 1), "gen_s": round(gpu_s, 1),
                             "gpu": torch.cuda.get_device_name(0), "gpu_mem": a.gpu_mem,
                             "host": os.uname().nodename, "shard": a.shard}) + "\n")
    print(f"[tramos] tiempo de generación {gpu_s / 60:.1f} min (carga {t_gen0 - t_load:.0f}s)", flush=True)


def selftest():
    units = [(5.0 * i, 5.0 * i + 5) for i in range(100)]
    s = {"u0": 10, "u1": 33}                      # 115 s -> 40 + 40 + 35 (resto >= 20 s)
    assert make_tramos(s, units) == [(50.0, 90.0), (90.0, 130.0), (130.0, 165.0)], make_tramos(s, units)
    s = {"u0": 10, "u1": 27}                      # 85 s -> 40 + 45 (resto 5 s se une)
    assert make_tramos(s, units) == [(50.0, 90.0), (90.0, 135.0)], make_tramos(s, units)
    s = {"u0": 0, "u1": 3}                        # escena corta: un solo tramo
    assert make_tramos(s, units) == [(0.0, 15.0)]
    print("selftest OK")


if __name__ == "__main__":
    main()
