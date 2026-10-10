"""EXP-034: evaluación del filtro de habla aislado (ver pre-registro en EXPERIMENT_LOG).

--mode dev   AVA dev: elige el candidato adoptable (exactitud balanceada, recall >= recall(W) − 0.05); además
             reporta (sin elegir nada con él) el narrador sintético dev y el control de alineación con ina publicado
--mode conf  aplica la elección congelada: criterios 1–4 + secundarias BBC + exportación de unidades a escuchar
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_bbc import k_eff, voice_ids  # noqa: E402
from exp034_items import G, LAB, all_items, coverage  # noqa: E402
from topicagg.speaker import single_speaker  # noqa: E402

THETAS = [round(0.1 * k, 1) for k in range(1, 10)]
MIN_UNITS = 5  # unidades sin habla (FSR) / con habla (recall) mínimas por video AVA
ADOPTABLE = ["W", "S", "I", "S&W", "I&W"] + [f"A{t}" for t in THETAS] + [f"A{t}&W" for t in THETAS]
REFERENCE = ["P", "P&W"]
SECONDARY = ["S&W", "I&W"]  # declaradas tras el dev, sin criterio (mejor bacc pero fuera del piso de recall)


def gates(it):
    """Filtro por unidad de cada candidato para un ítem."""
    c = json.loads((G / "cache" / it["dom"] / f"{it['id']}.json").read_text())
    ina = json.loads((G / "ina" / it["dom"] / f"{it['id']}.json").read_text())
    u = c["units"]
    g = {"W": np.array(c["whisper_gate"], bool) if "whisper_gate" in c else coverage(u, c["whisper_segments"]) >= 0.5,
         "P": np.array([bool(t.strip()) for t in c["parakeet"]]),
         "S": coverage(u, c["silero_segments"]) >= 0.5,
         "I": coverage(u, [(a, b) for lab, a, b in ina if lab == "speech"]) >= 0.5}
    sp = np.array(c["ast_speech"])
    for t in THETAS:
        g[f"A{t}"] = sp >= t
    for k in list(g):
        if k != "W":
            g[f"{k}&W"] = g[k] & g["W"]
    return g, c


def read_lab(f, delim):
    return [(float(r[0]), float(r[1])) for r in csv.reader(open(f), delimiter=delim) if r]


def ava_rows(split):
    rows = {}
    for it in all_items(["ava"]):
        if it["split"] != split:
            continue
        g, _ = gates(it)
        gt = coverage(it["units"], read_lab(LAB / "speech labels" / f"{it['id']}.csv", "\t")) >= 0.5
        mus = (coverage(it["units"], read_lab(LAB / "music labels" / f"{it['id']}.csv", ",")) >= 0.5) & ~gt
        oth = ~gt & ~mus
        r = {"n_speech": int(gt.sum()), "n_nonspeech": int((~gt).sum()), "n_music": int(mus.sum())}
        for k, p in g.items():
            r[k] = {"recall": float(p[gt].mean()) if gt.sum() >= MIN_UNITS else None,
                    "fsr": float(p[~gt].mean()) if (~gt).sum() >= MIN_UNITS else None,
                    "fsr_music": float(p[mus].mean()) if mus.sum() >= MIN_UNITS else None,
                    "fsr_other": float(p[oth].mean()) if oth.sum() >= MIN_UNITS else None}
        pub = G / "AVASpeech_Music_Labels" / "evaluation" / "inaSpeechSegmenter" / "avaspeech" / f"{it['id']}.csv"
        if pub.exists():
            r["ina_pub_agree"] = float(((coverage(it["units"], read_lab(pub, "\t")) >= 0.5) == g["I"]).mean())
        rows[it["id"]] = r
    return rows


def mean_of(rows, k, m):
    v = [r[k][m] for r in rows.values() if r[k][m] is not None]
    return float(np.mean(v)) if v else None


def summary(rows, keys):
    out = {}
    for k in keys:
        rec, fsr = mean_of(rows, k, "recall"), mean_of(rows, k, "fsr")
        out[k] = {"recall": rec, "fsr": fsr, "bacc": 0.5 * (rec + 1 - fsr),
                  "fsr_music": mean_of(rows, k, "fsr_music"), "fsr_other": mean_of(rows, k, "fsr_other")}
    return out


def paired(d):
    d = np.asarray(d, float)
    se = float(d.std(ddof=1) / np.sqrt(len(d))) if len(d) > 1 else float("nan")
    return {"mean": float(d.mean()), "se": se, "z": float(d.mean() / se) if se else None, "n": len(d)}


def identities(x, gate):
    single = single_speaker(x, gate)
    if single:
        vid = np.full(len(x), -1)
        vid[gate & (np.linalg.norm(x, axis=1) > 0)] = 1
        return vid, True
    return voice_ids(x, gate=gate), False


def narrator_rows(split, keys, sub="mix"):
    rows = {}
    for it in all_items([sub]):
        if it["split"] != split:
            continue
        g, _ = gates(it)
        m = json.loads(Path(it["wav"]).with_suffix(".json").read_text())
        x = np.load(G / "cache" / sub / f"{it['id']}.xall.npy").astype(np.float32)
        gt = np.array(m["gt_speech"], bool)
        r = {"k_true": m["k_true"], "cond": m["cond"], "src": m["src"]}
        for k in keys:
            vid, s = identities(x, g[k])
            r[k] = {"single": bool(s), "kerr": abs(k_eff(vid, g[k]) - m["k_true"]),
                    "fsr": float(g[k][~gt].mean()) if (~gt).sum() else None, "recall": float(g[k][gt].mean())}
        rows[it["id"]] = r
    return rows


def narrator_summary(rows, keys):
    out = {}
    for k in keys:
        o = {}
        for cond in ("clean", "music", "noise"):
            one = [r[k]["single"] for r in rows.values() if r["cond"] == cond and r["k_true"] == 1]
            many = [r[k]["single"] for r in rows.values() if r["cond"] == cond and r["k_true"] >= 2]
            o[cond] = {"single_rate_k1": float(np.mean(one)) if one else None,
                       "false_single_rate_k2": float(np.mean(many)) if many else None,
                       "kerr_k1": float(np.mean([r[k]["kerr"] for r in rows.values() if r["cond"] == cond and r["k_true"] == 1] or [np.nan]))}
        out[k] = o
    return out


def dev():
    rows = ava_rows("dev")
    s = summary(rows, ADOPTABLE + REFERENCE)
    floor = s["W"]["recall"] - 0.05
    ok = [k for k in ADOPTABLE if s[k]["recall"] >= floor]
    choice = max(ok, key=lambda k: s[k]["bacc"])
    nar = narrator_rows("dev", ["W", choice] + REFERENCE)
    agree = [r["ina_pub_agree"] for r in rows.values() if "ina_pub_agree" in r]
    out = {"choice": choice, "recall_floor": floor, "n_videos": len(rows), "ava_dev": s,
           "narrator_dev_descriptive": narrator_summary(nar, ["W", choice] + REFERENCE),
           "control_ina_vs_published": {"mean_unit_agreement": float(np.mean(agree)), "min": float(np.min(agree)), "n": len(agree)}}
    Path("results/exp034_dev.json").write_text(json.dumps(out, indent=1))
    Path("results/exp034_dev_rows.json").write_text(json.dumps({"ava": rows, "narrator": nar}, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "ava_dev"}, indent=1))
    for k in sorted(s, key=lambda k: -s[k]["bacc"])[:12]:
        print(f"{k:8s} bacc {s[k]['bacc']:.3f} recall {s[k]['recall']:.3f} fsr {s[k]['fsr']:.3f} "
              f"fsr_music {s[k]['fsr_music']:.3f}" + ("  ← elegido" if k == choice else ""))
    print(f"W        bacc {s['W']['bacc']:.3f} recall {s['W']['recall']:.3f} fsr {s['W']['fsr']:.3f} fsr_music {s['W']['fsr_music']:.3f}")


def audit_bbc(it, g, ch, n=10, rng=np.random.default_rng(0)):
    """Unidades BBC donde W y el elegido discrepan → wav de 5 s para escuchar (sin criterio)."""
    import subprocess
    out = G / "audit" / it["id"]
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind, mask in (("W_si_elegido_no", g["W"] & ~g[ch]), ("W_no_elegido_si", ~g["W"] & g[ch])):
        idx = np.where(mask)[0]
        for i in sorted(rng.choice(idx, min(n, len(idx)), replace=False)) if len(idx) else []:
            a, b = it["units"][i]
            f = out / f"{kind}_{i:04d}_{int(a)}s.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", str(b - a), "-i", it["wav"], str(f)], check=True)
            rows.append({"archivo": f.name, "tipo": kind, "t0": a, "t1": b, "etiqueta": ""})
    with open(out / "anotar.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["archivo", "tipo", "t0", "t1", "etiqueta"])
        w.writeheader()
        w.writerows(rows)


def conf():
    sel = json.loads(Path("results/exp034_dev.json").read_text())
    ch = sel["choice"]
    keys = ["W", ch] + REFERENCE + [k for k in SECONDARY if k != ch]
    # 1. AVA conf
    rows = ava_rows("conf")
    s = summary(rows, keys)
    d_fsr = [r["W"]["fsr"] - r[ch]["fsr"] for r in rows.values() if r["W"]["fsr"] is not None]
    c1 = {"fsr_W_minus_choice": paired(d_fsr), "recall_W": s["W"]["recall"], "recall_choice": s[ch]["recall"]}
    c1["pass"] = bool(c1["fsr_W_minus_choice"]["z"] > 2 and s[ch]["recall"] >= s["W"]["recall"] - 0.05)
    # 2–3. narrador sintético conf
    nar = narrator_rows("conf", keys)
    d1 = [int(r[ch]["single"]) - int(r["W"]["single"]) for r in nar.values() if r["k_true"] == 1 and r["cond"] in ("music", "noise")]
    c2 = {"single_choice_minus_W": paired(d1)}
    c2["pass"] = bool(c2["single_choice_minus_W"]["z"] is not None and c2["single_choice_minus_W"]["z"] > 2)
    many = [r for r in nar.values() if r["k_true"] >= 2]
    c3 = {"false_single_W": float(np.mean([r["W"]["single"] for r in many])),
          "false_single_choice": float(np.mean([r[ch]["single"] for r in many])), "n": len(many)}
    c3["pass"] = bool(c3["false_single_choice"] <= c3["false_single_W"] + 0.05)
    # 4. AMI fresh3
    ami = {}
    for it in all_items(["ami"]):
        g, c = gates(it)
        x = np.load(G / "cache" / "ami" / f"{it['id']}.xall.npy").astype(np.float32)
        dom = [d if d not in ("", "None") else None for d in c["dom_gt"]]
        r = {}
        for k in keys:
            vid, sg = identities(x, g[k])
            idx = [i for i in range(len(dom)) if dom[i] and vid[i] >= 0]
            r[k] = {"single": bool(sg), "ari": float(adjusted_rand_score([dom[i] for i in idx], vid[idx])) if len(idx) > 5 else None,
                    "speech_frac": float(g[k].mean())}
        ami[it["id"]] = r
    da = [r[ch]["ari"] - r["W"]["ari"] for r in ami.values() if r[ch]["ari"] is not None and r["W"]["ari"] is not None]
    c4 = {"ari_choice_minus_W": paired(da), "single_meetings": int(sum(r[ch]["single"] for r in ami.values())), "n": len(ami)}
    c4["pass"] = bool(c4["ari_choice_minus_W"]["mean"] > -0.02 and c4["single_meetings"] == 0)
    # secundarias BBC
    bbc = {}
    for it in all_items(["bbc"]):
        g, _ = gates(it)
        x = np.load(G / "cache" / "bbc" / f"{it['id']}.xall.npy").astype(np.float32)
        bbc[it["id"]] = {}
        for k in keys:
            vid, sg = identities(x, g[k])
            bbc[it["id"]][k] = {"speech_frac": float(g[k].mean()), "single": bool(sg), "k_eff": k_eff(vid, g[k])}
        audit_bbc(it, g, ch)
    rep = {"choice": ch, "c1_ava": c1, "c2_narrator_k1": c2, "c3_no_false_narrator": c3, "c4_ami": c4,
           "validated": bool(c1["pass"] and c2["pass"] and c3["pass"] and c4["pass"]),
           "secondary": {"ava_conf": s, "narrator_conf": narrator_summary(nar, keys),
                         "bbc_single": {k: int(sum(v[k]["single"] for v in bbc.values())) for k in keys},
                         "bbc_speech_frac": {k: float(np.mean([v[k]["speech_frac"] for v in bbc.values()])) for k in keys},
                         "bbc": bbc}}
    Path("results/exp034_conf.json").write_text(json.dumps(rep, indent=1))
    Path("results/exp034_conf_rows.json").write_text(json.dumps({"ava": rows, "narrator": nar, "ami": ami}, indent=1))
    print(json.dumps({k: v for k, v in rep.items() if k != "secondary"}, indent=1))
    print(json.dumps({k: rep["secondary"][k] for k in ("bbc_single", "bbc_speech_frac", "narrator_conf")}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["dev", "conf"], required=True)
    dev() if ap.parse_args().mode == "dev" else conf()
