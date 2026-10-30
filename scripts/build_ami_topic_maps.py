"""Mapas de tópicos CAVA para reuniones AMI, perfil "meeting" (p95/r90 + turnos w = 6), con hablantes.

Señales (sin fusión, todas propias de CAVA): voice, visual, transcript (bge del
ASR), vjudge (bge del resumen). Además de lo que lleva cualquier mapa (tramos,
retornos, etiqueta, provenance, contexto por clip), cada tópico y cada clip
llevan `speakers`: identidades V# del embedding de hablante WavLM-sv sobre unidades con habla
(ward + K por BIC; EXP-022d, 028) con su fracción de unidades. El votante de turnos usa los rasgos de voz (EXP-023). El GT de AMI no se usa aquí.
Salida: data/ami/topic_maps/<m>.topic_map.json y data/ami/versions/<m>.versions.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval_voice_identities import identities  # noqa: E402
from narrative_eval import BgeEmbedder  # noqa: E402
from speaker_turns import speaker_turn_scores  # noqa: E402
from topicagg.identities import speakers_of  # noqa: E402,F401  (movido a topicagg/identities.py)
from topicagg.speaker import single_speaker  # noqa: E402
from topicagg.topic_map import build_topic_map  # noqa: E402
from topicagg.versions import build_versions, check_versions  # noqa: E402

D = Path("data/ami")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--meetings", required=True)
    args = ap.parse_args()
    bge = BgeEmbedder()
    (D / "topic_maps").mkdir(parents=True, exist_ok=True)
    (D / "versions").mkdir(parents=True, exist_ok=True)
    ok = 0
    for m in Path(args.meetings).read_text().split():
        fj, fz, fv = D / "signals" / f"{m}.json", D / "signals" / f"{m}.npz", D / "vjudge" / f"{m}.summaries.json"
        if not (fj.exists() and fz.exists() and fv.exists() and (D / "signals" / f"{m}.xvec.npz").exists()):
            continue
        meta, z, sums = json.loads(fj.read_text()), np.load(fz), json.loads(fv.read_text())
        units = meta["unit_times"]
        n = min(len(units), len(sums), len(z["voice"]))
        texts = [t or "" for t in meta["asr_text"][:n]]
        sig = {"voice": z["voice"][:n], "visual": z["visual"][:n], "transcript": bge(texts),
               "vjudge": bge([s["summary"] for s in sums[:n]])}
        vid_voice = identities(np.asarray(z["voice"][:n], np.float32), "ward", k_rule="bic")  # EXP-022d
        doc = build_topic_map(m, sig, units[:n], unit_summaries=sums[:n], percentile=95,
                              return_percentile=90, abstain=True, unit_texts=texts,
                              boundary_signals={"turns": speaker_turn_scores(vid_voice, 6)})  # EXP-023
        # identidad (V#): embedding de hablante sobre unidades con habla (EXP-028; caché de cache_xvec.py)
        xz = np.load(D / "signals" / f"{m}.xvec.npz")
        xs, gate = xz["x"][:n].astype(np.float32), xz["gate"][:n]
        vid = np.full(n, -1)
        if single_speaker(xs, gate):  # EXP-029 (0/40 reuniones fresh3 lo activan)
            vid[gate] = 1
        elif gate.sum() >= 10:
            vid[gate] = identities(xs[gate], "ward", k_rule="bic")
        for level in doc["levels"].values():
            for t in level["topics"]:
                t["speakers"] = speakers_of(t["shots"], vid)
                for c, (a, b) in zip(t["context"], t["spans"]):
                    span_units = [u for u in t["shots"] if units[u][0] >= a - 1e-6 and units[u][1] <= b + 1e-6]
                    c["speakers"] = speakers_of(span_units, vid)
        doc["params"]["profile"] = "meeting"
        doc["voice_identity_signal"] = "wavlm_sv"
        doc["voice_identities"] = sorted({f"V{int(v)}" for v in vid if v >= 0})
        (D / "topic_maps" / f"{m}.topic_map.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))
        v = build_versions(doc, recap_s=60, highlight_frac=0.10)
        (D / "versions" / f"{m}.versions.json").write_text(json.dumps(v, ensure_ascii=False, indent=1))
        g = check_versions(v)["G_version"]
        ok += g
        d = doc["levels"]["default"]
        print(f"[ami-map] {m}: {d['n_topics']} tópicos ({d['n_returning']} con retornos), "
              f"{len(doc['voice_identities'])} voces, G-versión {g}", flush=True)
    print(f"[ami-map] G-versión {ok} reuniones")


if __name__ == "__main__":
    main()
