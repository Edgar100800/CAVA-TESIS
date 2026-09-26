"""Demo multimodal REAL (T1b→v2.1): transcript + visual + densidad de voz.

Sobre los 3 videos del piloto CAVA (TVSum): ASR tiny (transcript temporizado),
features SigLIP+BaSSL por shot (ya extraídas), y el gestor SIN FUSIÓN
(multimodal_manager.manage) que produce cortes por consenso y grupos de
tópicos con provenance por señal.

OCR y audio-espectro pendientes de extracción — el gestor los acepta cuando
existan (contrato en signals/).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/edgar.chambilla/Tesis/SegLoop")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from topicagg.signals.core import TranscriptSignal
from topicagg.multimodal_manager import manage


def tfidf_embeddings(bins_text):
    vocab = {}
    docs = []
    for txt in bins_text:
        toks = [w for w in "".join(c if c.isalnum() else " " for c in txt.lower()).split()
                if len(w) > 2]
        docs.append(toks)
        for w in set(toks):
            vocab.setdefault(w, len(vocab))
    n_docs = len(docs)
    df = np.zeros(len(vocab))
    for toks in docs:
        for w in set(toks):
            df[vocab[w]] += 1
    idf = np.log((1 + n_docs) / (1 + df)) + 1.0
    rows = []
    for toks in docs:
        v = np.zeros(len(vocab), dtype=np.float32)
        for w in toks:
            v[vocab[w]] += 1.0
        for w in set(toks):
            v[vocab[w]] *= idf[vocab[w]]
        n = np.linalg.norm(v)
        rows.append(v / n if n > 0 else v)
    return np.asarray(rows, dtype=np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--videos", nargs="+", required=True)
    ap.add_argument("--fa-root", default="data/fa")
    ap.add_argument("--fusion-dir", default="data/tvsum/processing/segmenter/siglip_bassl_fusion")
    ap.add_argument("--out", default="data/cava_pilot")
    ap.add_argument("--link-quorum", type=int, default=2)
    ap.add_argument("--asr-device", default="cpu")
    args = ap.parse_args()

    from segloop.io import video_loader, asr_whisper

    for video in args.videos:
        vid = Path(video).stem
        print(f"\n===== {vid} =====", flush=True)

        # señal visual: tokens de fusión por shot (ya extraídos)
        npz = Path(args.fusion_dir) / f"{vid}.npz"
        d = np.load(npz)
        visual = d["tokens"].astype(np.float32)
        n_seg = len(visual)

        # señal transcript: ASR tiny + TF-IDF por shot (texto solapado)
        segs = asr_whisper.transcribe(video, model_size="tiny", device=args.asr_device,
                                      compute_type="int8")
        sentences = [s.text for s in segs]
        times = [[float(s.start), float(s.end)] for s in segs]
        sig = TranscriptSignal(sentences, times, np.zeros((len(sentences), 4), np.float32))

        meta = video_loader.read_meta(video)
        dur = meta.num_frames / meta.fps
        shot_rows = [json.loads(l) for l in
                     open(Path(args.fa_root).parent / "tvsum_manifest.ndjson")] \
            if False else None
        # shots por video desde el manifest del piloto
        shots = {}
        for line in open("/home/edgar.chambilla/Tesis/SegLoop/" +
                         "data/tvsum/processing/segmenter/shots.ndjson"):
            r = json.loads(line)
            if r["video_id"] == vid:
                shots.setdefault(int(r["shot_id"]), r)

        # transcript embedding por shot: TF-IDF del texto solapado al shot
        shot_text = []
        shot_times = []
        for sid in sorted(shots):
            r = shots[sid]
            txt = " ".join(s for s, (a, b) in zip(sentences, times)
                           if a < float(r["end_ts"]) and b > float(r["start_ts"]))
            shot_text.append(txt)
            shot_times.append([float(r["start_ts"]), float(r["end_ts"])])
        transcript = tfidf_embeddings(shot_text)
        n = min(n_seg, len(transcript), len(shot_times))
        visual_n = visual[:n]
        transcript_n = transcript[:n]

        plan = manage({"transcript": transcript_n, "visual": visual_n[:n]},
                      speech_times=shot_times[:n], n_segments=n,
                      link_quorum=args.link_quorum)

        print(f"señales: transcript {transcript_n.shape}, visual {visual_n.shape[:1]}")
        print(f"cortes por señal: {plan.per_signal_cuts}")
        print(f"consenso (mayoría): {plan.consensus_cuts} | quorum enlace: {plan.quorum}")
        print(f"grupos: {len(plan.groups)}")
        for g in plan.groups:
            rep_t = [shot_text[i][:60] for i in g.segment_indices[:1]]
            print(f"  grupo {g.topic_id}: segs={g.segment_indices} "
                  f"soporte={g.signal_support} | «{rep_t[0] if rep_t else ''}»")

        out = Path(args.out) / vid / "topics_multimodal.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "protocol": "topicagg_multimodal_v2_1_no_fusion",
            "video_id": vid,
            "signals": sorted(signals := ["transcript", "visual"]),
            "consensus_cuts": plan.consensus_cuts,
            "per_signal_cuts": plan.per_signal_cuts,
            "groups": [{"topic_id": g.topic_id,
                        "segment_indices": g.segment_indices,
                        "signal_support": g.signal_support}
                       for g in plan.groups],
        }, indent=1, ensure_ascii=False))
        print(f"[out] {out}", flush=True)


if __name__ == "__main__":
    main()
