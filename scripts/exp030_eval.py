"""EXP-030: Parakeet frente a Whisper como ASR único (criterios 1–3 del pre-registro)."""
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import f1_b, k_eff, local_pairs, m_local, scenes_per_unit, voice_ids  # noqa: E402
from eval_topic_map import mcc  # noqa: E402
from eval_voice_identities import identities  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from speaker_turns import speaker_turn_scores  # noqa: E402
from topicagg.multimodal_manager import manage  # noqa: E402
from topicagg.speaker import single_speaker  # noqa: E402
from topicagg.topic_map import snap_boundaries  # noqa: E402

O = Path("data/asr_compare")
WORD = re.compile(r"\w", re.U)


def pk_gate(texts):
    return np.array([bool(WORD.search(t or "")) for t in texts])


def wh_gate(units, segs, frac=0.5):
    return np.array([sum(max(0.0, min(u1, b) - max(u0, a)) for a, b, *_ in segs) >= frac * (u1 - u0)
                     for u0, u1 in units])


def wh_text(units, segs):
    return [" ".join(t for a, b, t in segs if a < u1 and b > u0) for u0, u1 in units]


def paired(d):
    d = np.asarray(d, float)
    se = d.std(ddof=1) / np.sqrt(len(d))
    return {"mean": round(float(d.mean()), 4), "se": round(float(se), 4), "n": len(d),
            "z": round(float(d.mean() / se), 2) if se > 0 else None}


def k_true_of(dom):
    lab = [d for d in dom if d]
    if not lab:
        return 0
    _, c = np.unique(lab, return_counts=True)
    return int((c / len(lab) >= 0.05).sum())


def ids_with_detector(x, gate):
    if single_speaker(x, gate):
        out = np.full(len(x), -1)
        out[gate & (np.linalg.norm(x, axis=1) > 0)] = 1
        return out
    return voice_ids(x, gate=gate)


def crit12():
    rows = {}
    for f in sorted((O / "vox_test").glob("*.json")):
        d = json.loads(f.read_text())
        z = np.load(Path("data/voxconverse/xvec/test") / f"{f.stem}.npz")
        gt, dom = z["gate"], [str(x) for x in z["dom"]]
        x = np.load(O / f"vox_test_{f.stem}.xall.npy").astype(np.float32)
        n = min(len(gt), len(x), len(d["parakeet"]))
        gt, dom, x = gt[:n], dom[:n], x[:n]
        units = d["units"][:n]
        gates = {"whisper": wh_gate(units, d["whisper_segments"]), "parakeet": pk_gate(d["parakeet"][:n])}
        r = {"n_nonspeech": int((~gt).sum()), "k_true": k_true_of(dom)}
        for k, g in gates.items():
            r[f"fsr_{k}"] = float(g[~gt].mean()) if (~gt).sum() else None
            r[f"miss_{k}"] = float((~g[gt]).mean()) if gt.sum() else None
            r[f"kerr_{k}"] = abs(k_eff(ids_with_detector(x, g), g) - r["k_true"])
        rows[f.stem] = r
    fsr = [r["fsr_whisper"] - r["fsr_parakeet"] for r in rows.values() if r["n_nonspeech"] >= 5]
    miss = [r["miss_parakeet"] - r["miss_whisper"] for r in rows.values() if r["miss_whisper"] is not None]
    kerr = [r["kerr_parakeet"] - r["kerr_whisper"] for r in rows.values()]
    mean = lambda k, c=lambda r: True: round(float(np.mean([r[k] for r in rows.values() if c(r) and r[k] is not None])), 4)  # noqa: E731
    return {"c1_fsr_whisper_minus_parakeet": paired(fsr),
            "c1_miss_parakeet_minus_whisper": {"mean": round(float(np.mean(miss)), 4), "ok": bool(np.mean(miss) < 0.02)},
            "c2_kerr_parakeet_minus_whisper": {"mean": round(float(np.mean(kerr)), 4), "ok": bool(np.mean(kerr) < 0.05)},
            "means": {k: mean(k, (lambda r: r["n_nonspeech"] >= 5) if k.startswith("fsr") else (lambda r: True))
                      for k in ("fsr_whisper", "fsr_parakeet", "miss_whisper", "miss_parakeet", "kerr_whisper", "kerr_parakeet")},
            "per_file": rows}


def crit3_ami(bge):
    D = Path("data/ami")
    AB = dict(min_gap=2, tolerance_bins=1, link_quorum=2, percentile=95, return_percentile=90,
              link_mode="average", abstain=True)
    rows = {}
    for m in (D / "meetings_fresh3.txt").read_text().split():
        fz, fj, fv, fa = (D / "signals" / f"{m}.npz", D / "signals" / f"{m}.json",
                          D / "vjudge" / f"{m}.summaries.json", O / "ami" / f"{m}.json")
        if not all(p.exists() for p in (fz, fj, fv, fa)):
            continue
        z, meta, sums = np.load(fz), json.loads(fj.read_text()), json.loads(fv.read_text())
        gt = json.loads((D / "gt" / f"{m}.json").read_text())
        units = meta["unit_times"]
        pk = json.loads(fa.read_text())["parakeet"]
        n = min(len(units), len(z["voice"]), len(z["visual"]), len(sums), len(pk))
        units = units[:n]
        top = [next((t["label"] for t in gt["topics"] if t["t0"] <= (a + b) / 2 <= t["t1"]), None) for a, b in units]
        I, J = np.triu_indices(n, 18)
        keep = [(i, j) for i, j in zip(I, J) if top[i] and top[j]]
        y = np.array([top[i] == top[j] for i, j in keep])
        if len(keep) < 20 or y.all() or (~y).all():
            continue
        vid = identities(np.asarray(z["voice"][:n], np.float32), "ward", k_rule="bic")
        bnd = {"turns": speaker_turn_scores(vid, 6)}
        base = {"voice": z["voice"][:n], "visual": z["visual"][:n], "vjudge": bge([s["summary"] for s in sums[:n]])}
        r = {}
        for k, texts in (("whisper", [t or "" for t in meta["asr_text"][:n]]), ("parakeet", pk[:n])):
            lab = np.asarray(manage(base | {"transcript": bge(texts)}, boundary_signals=bnd, **AB).labels)
            r[f"mcc_{k}"] = mcc(np.array([lab[i] == lab[j] for i, j in keep]), y)
        rows[m] = r
    return rows


def crit3_bbc(bge):
    AB = dict(min_gap=2, tolerance_bins=1, link_quorum=2, percentile=90, return_percentile=90,
              link_mode="average", abstain=True)
    rows = {}
    for ep in range(1, 12):
        w = Path("data/cava_runs_doc") / f"bbc_{ep:02d}" / "work"
        st, z = json.loads((w / "state.json").read_text()), np.load(w / "signals.npz")
        sums = json.loads((w / "summaries.json").read_text())
        pk = json.loads((O / "bbc" / f"bbc_{ep:02d}.json").read_text())["parakeet"]
        n = min(len(st["units"]), len(z["voice"]), len(z["visual"]), len(pk))
        units = st["units"][:n]
        e = bge([s["summary"] for s in sums])
        vj = np.zeros((n, e.shape[1]), np.float32)
        for s, v in zip(sums, e):
            vj[s["lo"]:min(s["hi"], n)] = v
        base = {"voice": np.asarray(z["voice"][:n], np.float32), "visual": np.asarray(z["visual"][:n], np.float32),
                "vjudge": vj}
        gts = scenes_per_unit(ep, units)
        I, J = local_pairs(n)
        ends = np.array([b for _, b in units], float)
        ref = np.asarray(manage({"visual": base["visual"]}, **(AB | {"link_quorum": 1})).labels)
        r = {}
        for k, texts in (("whisper", st["asr"][:n]), ("parakeet", pk[:n])):
            lab = snap_boundaries(np.asarray(manage(base | {"transcript": bge(texts)}, **AB).labels), ref, ends, 30.0)
            r[f"m_local_{k}"], r[f"f1b_{k}"] = m_local(lab, gts, I, J), f1_b(lab, gts)
        xs = np.load(w / "speaker_xvec.npy")
        r["speech_frac_whisper"] = float(wh_gate(units, st["asr_segments"]).mean())
        r["speech_frac_parakeet"] = float(pk_gate(pk[:n]).mean())
        # xvec cacheada solo en unidades con habla Whisper: el filtro efectivo es Parakeet ∩ Whisper (secundaria)
        g = pk_gate(pk[:n]) & (np.linalg.norm(xs[:n], axis=1) > 0)
        r["single_parakeet_gate"] = bool(single_speaker(xs[:n], g))
        rows[f"bbc_{ep:02d}"] = r
    return rows


def main():
    bge = BgeEmbedder()
    c12 = crit12()
    ami, bbc = crit3_ami(bge), crit3_bbc(bge)
    rep = {k: v for k, v in c12.items() if k != "per_file"}
    rep["c3_ami_mcc_parakeet_minus_whisper"] = paired([r["mcc_parakeet"] - r["mcc_whisper"] for r in ami.values()])
    rep["c3_ami_means"] = {k: round(float(np.mean([r[k] for r in ami.values()])), 4) for k in ("mcc_whisper", "mcc_parakeet")}
    rep["c3_bbc_mlocal_parakeet_minus_whisper"] = paired([r["m_local_parakeet"] - r["m_local_whisper"] for r in bbc.values()])
    rep["c3_bbc_means"] = {k: round(float(np.mean([r[k] for r in bbc.values()])), 4)
                           for k in ("m_local_whisper", "m_local_parakeet", "f1b_whisper", "f1b_parakeet",
                                     "speech_frac_whisper", "speech_frac_parakeet")}
    rep["secondary_bbc_single_parakeet_gate"] = int(sum(r["single_parakeet_gate"] for r in bbc.values()))
    rep["c3_ok"] = bool(rep["c3_ami_mcc_parakeet_minus_whisper"]["mean"] > -0.02
                        and rep["c3_bbc_mlocal_parakeet_minus_whisper"]["mean"] > -0.02)
    Path("results/exp030.json").write_text(json.dumps(rep | {"per_file_vox": c12["per_file"], "ami": ami, "bbc": bbc},
                                                      indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
