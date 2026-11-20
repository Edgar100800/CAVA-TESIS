"""Comprobaciones R1–R8 de adopción del stack v1.1 (EXP-043-DIA).

Uso completo:
  HF_HOME=/data/tesis-cava/CAVA_minimo/models python scripts/check_v11_nonregression.py

Las entradas grandes viven fuera del repo. Cada corrida escribe report.json y report.md;
un shard o una sola ejecución de R7 queda SKIPPED hasta integrar sus artefactos en el
coordinador. Ninguna comprobación usa GT dentro del producto: el GT solo aparece en R4,
para calcular el ARI de validación ya pre-registrado.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from topicagg.diarization import rttm, run_diarization, unit_labels  # noqa: E402
from topicagg.pipeline import Pipeline  # noqa: E402
from topicagg.versions import check_versions  # noqa: E402

FROZEN = Path(os.environ.get("CAVA_FROZEN", "/data/tesis-cava/CAVA_minimo"))
VOX = Path(os.environ.get("CAVA_VOX", "/data/tesis-cava/data_vox"))
AMI = Path(os.environ.get("CAVA_AMI", "/data/tesis-cava/data_ami"))
REVISION = "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee"
R4_TARGETS = {"vox": (0.938, 0.005), "ami": (0.975, 0.005)}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def semantic_diff(a, b):
    """Número de diferencias semánticas JSON; no compara formato ni orden de claves."""
    if type(a) is not type(b):
        return 1
    if isinstance(a, dict):
        return (len(set(a) ^ set(b)) + sum(semantic_diff(a[k], b[k]) for k in set(a) & set(b)))
    if isinstance(a, list):
        return abs(len(a) - len(b)) + sum(semantic_diff(x, y) for x, y in zip(a, b))
    return int(a != b)


def without_speakers(value, versions=False):
    if isinstance(value, dict):
        drop = {"speakers", "voice_identities", "voice_identity_signal", "speaker_turns"}
        if versions:
            drop.add("speaker_threads")
        return {k: without_speakers(v, versions) for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [without_speakers(v, versions) for v in value]
    return value


def copy_work(src, dst, diar_cache=None):
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(Path(src) / "work", dst / "work", dirs_exist_ok=True)
    if diar_cache:
        for suffix in (".json", ".rttm", ".exclusive.rttm"):
            source = Path(diar_cache).with_suffix(suffix)
            target = dst / "work" / f"diar.pyannote_c1.3533c8cf{suffix}"
            shutil.copy2(source, target)


def run_cached(video, frozen, out, profile, stack, diar_cache=None):
    """Recorre el pipeline con work/ congelado; no recorta videos ni recalcula señales."""
    out = Path(out)
    if not (out / "topic_map.json").exists():
        copy_work(frozen, out, diar_cache)
        p = Pipeline(video, out, profile=profile, stack=stack)
        p.run(cut=False)
    return out


def compare_contract_outputs(ref, cand):
    ref, cand = Path(ref), Path(cand)
    result = {}
    for name in ("topic_map.json", "versions.json"):
        a, b = json.loads((ref / name).read_text()), json.loads((cand / name).read_text())
        result[name] = {"semantic_diff": semantic_diff(a, b), "byte_equal": (ref / name).read_bytes() == (cand / name).read_bytes()}
    a, b = load_jsonl(ref / "clips.jsonl"), load_jsonl(cand / "clips.jsonl")
    result["clips.jsonl"] = {"semantic_diff": semantic_diff(a, b),
                             "byte_equal": (ref / "clips.jsonl").read_bytes() == (cand / "clips.jsonl").read_bytes()}
    return result


def check_r1(work):
    runs, details = {}, {}
    for name in ("Spider_Man", "Avengers_Endgame"):
        frozen = FROZEN / "outputs" / name
        if not (frozen / "work/state.json").exists():
            return "SKIPPED", {"reason": f"faltan work/ congelados: {frozen}"}
        out = run_cached(FROZEN / "videos" / f"{name}.mp4", frozen, work / "r1" / name, "film", "v1.0")
        cmp = compare_contract_outputs(frozen, out)
        runs[name] = str(out)
        details[name] = cmp
    ok = all(v["semantic_diff"] == 0 for d in details.values() for v in d.values())
    return ("PASS" if ok else "FAIL"), {"runs": runs, "comparisons": details}


def hash_records():
    lines = (ROOT / "docs/hashes_exp041L_stimuli.sha256").read_text().splitlines()
    remote, local = [], []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        digest, path = line.split("  ", 1)
        (local if path.startswith("/") else remote).append((digest, path))
    return remote, local


def check_r2():
    remote, local = hash_records()
    payload = "".join(f"{digest}  {path}\n" for digest, path in remote)
    proc = subprocess.run(["ssh", "-o", "BatchMode=yes", "khipu", "cd ~/Tesis/CAVA && sha256sum -c -"],
                          input=payload, text=True, capture_output=True, timeout=180)
    remote_bad = [] if proc.returncode == 0 else [line for line in (proc.stdout + proc.stderr).splitlines()
                                                  if "FAILED" in line or "No such" in line]
    local_bad = [path for digest, path in local if not Path(path).exists() or sha256(path) != digest]
    detail = {"stimuli_files": len(remote), "stimuli_mismatches": remote_bad,
              "frozen_reference_files": len(local), "frozen_reference_mismatches": local_bad,
              "ssh_returncode": proc.returncode}
    if proc.returncode != 0 and not remote_bad:
        return "SKIPPED", detail | {"reason": proc.stderr.strip() or "no se pudo ejecutar sha256sum en Khipu"}
    return ("PASS" if not remote_bad and not local_bad else "FAIL"), detail


def check_r3(work):
    name = "Spider_Man"
    frozen = FROZEN / "outputs" / name
    v10 = work / "r1" / name
    if not (v10 / "topic_map.json").exists():
        v10 = run_cached(FROZEN / "videos" / f"{name}.mp4", frozen, v10, "film", "v1.0")
    diar = work / "r7/run1/diar.json"
    v11 = run_cached(FROZEN / "videos" / f"{name}.mp4", frozen, work / "r3/Spider_Man", "film", "v1.1",
                     diar_cache=diar if diar.exists() else None)
    maps = [json.loads(p.read_text()) for p in (v10 / "topic_map.json", v11 / "topic_map.json")]
    vers = [json.loads(p.read_text()) for p in (v10 / "versions.json", v11 / "versions.json")]
    # speaker_threads sí cambia con V#; sus filas no contaminan el contrato de las demás versiones.
    clips = [[r for r in load_jsonl(p) if r.get("version") != "speaker_threads"]
             for p in (v10 / "clips.jsonl", v11 / "clips.jsonl")]
    detail = {
        "topic_map_non_speaker_diff": semantic_diff(without_speakers(maps[0]), without_speakers(maps[1])),
        "versions_non_speaker_diff": semantic_diff(without_speakers(vers[0], True), without_speakers(vers[1], True)),
        "clips_non_speaker_diff": semantic_diff(without_speakers(clips[0]), without_speakers(clips[1])),
        "G_version_v10": check_versions(vers[0])["G_version"],
        "G_version_v11": check_versions(vers[1])["G_version"],
        "voice_identity_signal_v10": maps[0].get("voice_identity_signal"),
        "voice_identity_signal_v11": maps[1].get("voice_identity_signal"),
        "voice_identities_v10": maps[0].get("voice_identities"),
        "voice_identities_v11": maps[1].get("voice_identities"),
        "speaker_turns_v11": len(maps[1].get("speaker_turns", [])),
        "v11": str(v11),
    }
    ok = (detail["topic_map_non_speaker_diff"] == detail["versions_non_speaker_diff"] ==
          detail["clips_non_speaker_diff"] == 0 and detail["G_version_v10"] == detail["G_version_v11"]
          and detail["voice_identity_signal_v11"] == "pyannote_c1" and detail["speaker_turns_v11"] > 0)
    return ("PASS" if ok else "FAIL"), detail


def unit_gt(units, segs):
    """Copia del protocolo EXP-043; GT solo para evaluación R4."""
    dom, gate = [], []
    for u0, u1 in units:
        ov = {}
        for a, b, s in segs:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0.0) + o
        tot = sum(ov.values())
        sp = max(ov, key=ov.get) if ov else None
        dom.append(sp if sp and ov[sp] >= 0.6 * tot and ov[sp] >= 1.5 else None)
        gate.append(min(tot, u1 - u0) >= 0.5 * (u1 - u0))
    return dom, np.array(gate)


def dominant(units, speech):
    """Copia del protocolo AMI fresh3 de EXP-043; GT solo para evaluación R4."""
    dom = []
    for u0, u1 in units:
        ov = {}
        for s, a, b in speech:
            o = max(0.0, min(u1, b) - max(u0, a))
            if o > 0:
                ov[s] = ov.get(s, 0) + o
        tot = sum(ov.values())
        sp = max(ov, key=ov.get) if ov else None
        dom.append(sp if ov and ov[sp] >= 0.6 * tot and tot > 3 else None)
    return dom


def ari_vox(dom, vid):
    idx = [i for i in range(len(dom)) if dom[i] and vid[i] >= 0]
    return float(adjusted_rand_score([dom[i] for i in idx], vid[idx])) if len(idx) > 5 else None


def ari_ami(dom, vid):
    idx = [i for i in range(len(dom)) if dom[i] and vid[i] >= 0]
    return float(adjusted_rand_score([dom[i] for i in idx], vid[idx])) if idx else 0.0


def check_r4_vox(work, shard=None):
    if not (VOX / "xvec/test").exists():
        return {}, "SKIPPED", f"falta {VOX}/xvec/test"
    cache = work / "r4/vox"
    cache.mkdir(parents=True, exist_ok=True)
    files = sorted((VOX / "xvec/test").glob("*.npz"))
    selected = [p for i, p in enumerate(files) if shard is None or i % shard[1] == shard[0]]
    rows = {}
    for z in selected:
        uri = z.stem
        wav = VOX / "wav_test/voxconverse_test_wav" / f"{uri}.wav"
        if not wav.exists():
            return rows, "SKIPPED", f"falta audio de VoxConverse: {wav}"
        out = cache / f"{uri}.json"
        run_diarization(wav, out)
        d = np.load(z, allow_pickle=True)
        units = d["units"].astype(float).tolist()
        gt = rttm(VOX / "voxconverse-master/test" / f"{uri}.rttm")
        dom, gate = unit_gt(units, gt)
        vid = unit_labels(units, rttm(out.with_suffix(".rttm")), gate)
        rows[uri] = {"ari_P": ari_vox(dom, vid)}
    vals = [r["ari_P"] for r in rows.values() if r["ari_P"] is not None]
    summary = {"n_files": len(rows), "n_ari": len(vals), "ari_P_mean": float(np.mean(vals)) if vals else None,
               "per_file": rows}
    target, tol = R4_TARGETS["vox"]
    partial = shard is not None or len(rows) != len(files)
    status = "SKIPPED" if partial else ("PASS" if vals and abs(summary["ari_P_mean"] - target) <= tol else "FAIL")
    reason = f"shard {shard[0]}/{shard[1]}; integrar ambos shards" if partial else None
    return {"summary": summary, "target": [target - tol, target + tol], "reason": reason}, status, None


def check_r4_ami(work):
    if not (AMI / "meetings_fresh3.txt").exists():
        return {"reason": f"falta {AMI}"}, "SKIPPED"
    cache = work / "r4/ami"
    cache.mkdir(parents=True, exist_ok=True)
    meetings = (AMI / "meetings_fresh3.txt").read_text().split()
    rows = {}
    for m in meetings:
        meta = json.loads((AMI / "signals" / f"{m}.json").read_text())
        xz = np.load(AMI / "signals" / f"{m}.xvec.npz")
        n = min(len(xz["x"]), len(meta["unit_times"]))
        units = meta["unit_times"][:n]
        gate = np.array([bool((t or "").strip()) for t in meta["asr_text"][:n]])
        wav = AMI / "wav" / f"{m}.Mix-Headset.wav"
        out = cache / f"{m}.Mix-Headset.json"
        run_diarization(wav, out)
        dom = dominant(units, json.loads((AMI / "gt" / f"{m}.json").read_text())["speech"])
        vid = unit_labels(units, rttm(out.with_suffix(".rttm")), gate)
        rows[m] = {"ari_P": ari_ami(dom, vid)}
    vals = [r["ari_P"] for r in rows.values()]
    target, tol = R4_TARGETS["ami"]
    mean = float(np.mean(vals)) if vals else None
    return {"n_files": len(rows), "ari_P_mean": mean, "target": [target - tol, target + tol], "per_meeting": rows}, \
        ("PASS" if vals and abs(mean - target) <= tol else "FAIL")


def check_r4(work, shard=None, part="all"):
    detail, statuses = {}, []
    if part in ("all", "vox"):
        vox, status, error = check_r4_vox(work, shard)
        detail["vox"] = vox if not error else {"reason": error}
        statuses.append(status)
    if part in ("all", "ami") and shard is None:
        ami, status = check_r4_ami(work)
        detail["ami"] = ami
        statuses.append(status)
    if shard is not None and part == "vox":
        detail["partial"] = True
    if "FAIL" in statuses:
        status = "FAIL"
    elif statuses and all(s == "PASS" for s in statuses) and part == "all" and shard is None:
        status = "PASS"
    else:
        status = "SKIPPED"
    return status, detail


def check_r5(work):
    frozen = work / "inputs/bbc_01_frozen"
    video = work / "inputs/bbc_01.mp4"
    if not (frozen / "work/state.json").exists() or not video.exists():
        return "SKIPPED", {"reason": "faltan bbc_01.mp4 o su work/ congelado en v11_work/inputs"}
    outs = [run_cached(video, frozen, work / f"r5/{stack}", "documentary", stack) for stack in ("v1.0", "v1.1")]
    comparisons = compare_contract_outputs(*outs)
    doc = json.loads((outs[1] / "topic_map.json").read_text())
    ok = all(v["semantic_diff"] == 0 for v in comparisons.values()) and doc.get("voice_identity_signal") == "wavlm_sv"
    return ("PASS" if ok else "FAIL"), {"comparisons": comparisons, "backend_v11": doc.get("voice_identity_signal")}


def check_r6(work):
    frozen = work / "inputs/IS1000c_frozen"
    video, audio = work / "inputs/IS1000c.Room.avi", work / "inputs/IS1000c.Mix-Headset.wav"
    if not (frozen / "work/state.json").exists() or not video.exists() or not audio.exists():
        return "SKIPPED", {"reason": "faltan IS1000c o su work/ congelado en v11_work/inputs"}
    outs = []
    for stack in ("v1.0", "v1.1"):
        out = work / f"r6/{stack}"
        if not (out / "topic_map.json").exists():
            copy_work(frozen, out)
            Pipeline(video, out, profile="meeting", stack=stack, audio=audio).run(cut=False)
        outs.append(out)
    maps = [json.loads((out / "topic_map.json").read_text()) for out in outs]
    diff = semantic_diff(without_speakers(maps[0]), without_speakers(maps[1]))
    speakers_changed = semantic_diff(maps[0], maps[1]) > diff
    detail = {"map_non_speaker_diff": diff, "speakers_changed": speakers_changed,
              "backend_v10": maps[0].get("voice_identity_signal"), "backend_v11": maps[1].get("voice_identity_signal"),
              "voice_identities_v10": maps[0].get("voice_identities"), "voice_identities_v11": maps[1].get("voice_identities"),
              "speaker_turns_v11": len(maps[1].get("speaker_turns", []))}
    ok = diff == 0 and speakers_changed and detail["backend_v11"] == "pyannote_c1" and detail["speaker_turns_v11"] > 0
    return ("PASS" if ok else "FAIL"), detail


def check_r7(work, only_run=None):
    wav = FROZEN / "outputs/Spider_Man/work/audio.wav"
    if not wav.exists():
        return "SKIPPED", {"reason": f"falta {wav}"}
    runs = ("run1", "run2") if only_run is None else (only_run,)
    for run in runs:
        run_diarization(wav, work / f"r7/{run}/diar.json")
    a, b = work / "r7/run1/diar.rttm", work / "r7/run2/diar.rttm"
    if not a.exists() or not b.exists():
        return "SKIPPED", {"reason": "solo se calculó una ejecución; falta integrar la otra GPU",
                           "runs_completed": list(runs)}
    ae, be = a.with_suffix(".exclusive.rttm"), b.with_suffix(".exclusive.rttm")
    detail = {"run1_sha256": sha256(a), "run2_sha256": sha256(b), "rttm_identical": a.read_bytes() == b.read_bytes(),
              "exclusive_rttm_identical": ae.read_bytes() == be.read_bytes(),
              "run1_exclusive_sha256": sha256(ae), "run2_exclusive_sha256": sha256(be)}
    return ("PASS" if detail["rttm_identical"] and detail["exclusive_rttm_identical"] else "FAIL"), detail


def validate_manifest(manifest, out, stack):
    errors = []
    if manifest.get("schema") != "cava-run-v1":
        errors.append("schema != cava-run-v1")
    if manifest.get("gt_used") is not False:
        errors.append("gt_used != false")
    if manifest.get("code", {}).get("git_dirty") is not False:
        errors.append("git_dirty != false")
    if stack == "v1.1":
        if manifest.get("stack") != "v1.1":
            errors.append("falta stack=v1.1")
        if manifest.get("profile", {}).get("speaker_backend") == "pyannote_c1":
            if manifest.get("models", {}).get("diarization") != ["pyannote/speaker-diarization-community-1", REVISION]:
                errors.append("revisión de diarization incorrecta")
            if manifest.get("pyannote_audio") != "4.1.1":
                errors.append("pyannote_audio != 4.1.1")
    for name in manifest.get("outputs", {}).get("files", []):
        if not (Path(out) / name).exists():
            errors.append(f"falta salida {name}")
    required = {"clip_id", "video", "profile", "version", "playlist", "order", "t0", "t1", "duration_s",
                "topic_id", "topic_label", "speakers", "provenance", "flags"}
    rows = load_jsonl(Path(out) / "clips.jsonl")
    bad_rows = [i for i, row in enumerate(rows) if not required <= set(row)]
    if bad_rows:
        errors.append(f"clips sin contrato: {bad_rows[:10]}")
    return {"n_clips": len(rows), "errors": errors}


def check_r8(work):
    candidates = [(work / "r3/Spider_Man", "v1.1"), (work / "r1/Spider_Man", "v1.0"),
                  (work / "r1/Avengers_Endgame", "v1.0"), (work / "r5/v1.1", "v1.1"),
                  (work / "r6/v1.1", "v1.1")]
    detail, missing = {}, []
    for out, stack in candidates:
        if not (out / "run_manifest.json").exists():
            missing.append(str(out))
            continue
        detail[str(out)] = validate_manifest(json.loads((out / "run_manifest.json").read_text()), out, stack)
    if not detail:
        return "SKIPPED", {"reason": "no hay manifiestos generados", "missing": missing}
    ok = all(not d["errors"] for d in detail.values()) and (work / "r3/Spider_Man/run_manifest.json").exists()
    return ("PASS" if ok else "FAIL"), {"manifests": detail, "not_run": missing}


CHECKS = {"R1": check_r1, "R2": check_r2, "R3": check_r3, "R4": check_r4,
          "R5": check_r5, "R6": check_r6, "R7": check_r7, "R8": check_r8}


def brief(detail):
    if "reason" in detail:
        return detail["reason"]
    if "comparisons" in detail:
        values = []
        for value in detail["comparisons"].values():
            if "semantic_diff" in value:
                values.append(value["semantic_diff"])
            else:
                values.extend(v["semantic_diff"] for v in value.values())
        return f"diffs={values}"
    if "vox" in detail:
        v, a = detail.get("vox", {}), detail.get("ami", {})
        vs = v.get("summary", {}) if isinstance(v, dict) else {}
        return f"Vox ARI={vs.get('ari_P_mean')} n={vs.get('n_ari')}; AMI ARI={a.get('ari_P_mean')} n={a.get('n_files')}"
    for key in ("topic_map_non_speaker_diff", "map_non_speaker_diff"):
        if key in detail:
            return f"diff no hablante={detail[key]}; backend={detail.get('voice_identity_signal_v11', detail.get('backend_v11'))}"
    if "rttm_identical" in detail:
        return f"RTTM idéntico={detail['rttm_identical']}; exclusivo={detail['exclusive_rttm_identical']}"
    if "stimuli_files" in detail:
        return f"{detail['stimuli_files']} estímulos; errores={len(detail['stimuli_mismatches'])}"
    if "manifests" in detail:
        return f"manifiestos={len(detail['manifests'])}; errores={sum(len(x['errors']) for x in detail['manifests'].values())}"
    return "ver report.json"


def write_reports(out, results):
    out.mkdir(parents=True, exist_ok=True)
    statuses = [r["status"] for r in results.values()]
    overall = "FAIL" if "FAIL" in statuses else ("PASS" if statuses and all(s == "PASS" for s in statuses) else "SKIPPED")
    doc = {"schema": "cava-v11-nonregression-v1", "overall": overall,
           "code": {"git_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                                  capture_output=True).stdout.strip()},
           "checks": results}
    (out / "report.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    lines = ["# No regresión del stack v1.1", "", f"Estado global: **{overall}**", "",
             "| comprobación | estado | resultado |", "|---|---|---|"]
    for name, result in results.items():
        lines.append(f"| {name} | {result['status']} | {brief(result['detail']).replace('|', '/')} |")
    lines += ["", "Los datos y artefactos grandes quedan en `/data/tesis-cava/v11_work/`.",
              "`SKIPPED` no cuenta como aprobado. El GT de R4 solo evalúa; no entra en el pipeline.", ""]
    (out / "report.md").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--checks", default=",".join(CHECKS))
    ap.add_argument("--work", type=Path, default=Path("/data/tesis-cava/v11_work"))
    ap.add_argument("--out", type=Path, default=ROOT / "results/v11_nonregression")
    ap.add_argument("--vox-shard", help="índice/número, p. ej. 0/2; solo R4 VoxConverse")
    ap.add_argument("--r4-part", choices=("all", "vox", "ami"), default="all")
    ap.add_argument("--r7-run-id", choices=("run1", "run2"))
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    shard = None
    if args.vox_shard:
        a, b = args.vox_shard.split("/")
        shard = (int(a), int(b))
        if not 0 <= shard[0] < shard[1]:
            ap.error("--vox-shard debe cumplir 0 <= índice < número")
    results = {}
    for name in args.checks.split(","):
        name = name.strip().upper()
        if name not in CHECKS:
            ap.error(f"comprobación desconocida: {name}")
        print(f"[v11] {name} en curso", flush=True)
        try:
            if name == "R4":
                status, detail = check_r4(args.work, shard, args.r4_part)
            elif name == "R7":
                status, detail = check_r7(args.work, args.r7_run_id)
            elif name == "R2":
                status, detail = check_r2()
            else:
                status, detail = CHECKS[name](args.work)
        except (FileNotFoundError, NotADirectoryError) as exc:
            status, detail = "SKIPPED", {"reason": str(exc)}
        except Exception as exc:
            status, detail = "FAIL", {"reason": f"{type(exc).__name__}: {exc}"}
        results[name] = {"status": status, "detail": detail}
        write_reports(args.out, results)
        print(f"[v11] {name}: {status} — {brief(detail)}", flush=True)
    print(json.dumps({k: v["status"] for k, v in results.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
