"""Add grounded descriptions and a chronological narrative to an existing CAVA run."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from topicagg.narrative import run_narrative
from topicagg.narrative_model import NarrativeModel, MODEL, file_hash


def verify_smoke(directory, frames, max_candidate_s):
    import json
    expected = {p.name: file_hash(p) for p in [Path(__file__).resolve().parents[1] / "topicagg/narrative.py",
                                              Path(__file__).resolve().parents[1] / "topicagg/narrative_model.py"]}
    for name in ["Avengers_Endgame", "Spider_Man"]:
        folder = Path(directory) / name
        protocol = json.loads((folder / "protocol.json").read_text())
        report = json.loads((folder / "run_report.json").read_text())
        gpu_tasks = report.get("model_tasks_devices", {})
        all_gpu = all(gpu_tasks.get(task) == ["cuda"] for task in
                      ["events", "description", "outline", "assessment", "continuity", "narration"])
        if not (report["G_narrative"] and report["decoded"] and protocol["code_hashes"] == expected
                and protocol["model"] == list(MODEL) and protocol["frame_count"] == frames
                and protocol["max_candidate_s"] == max_candidate_s and all_gpu):
            raise ValueError(f"{name}: successful smoke with identical analysis code/model/frames is required")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--script", type=Path, help="Optional JSON screenplay with t0, t1, text, aligned to prepared video")
    ap.add_argument("--budget-fraction", type=float, default=0.10)
    ap.add_argument("--frames", type=int, default=10)
    ap.add_argument("--max-candidate-seconds", type=float, default=30)
    ap.add_argument("--decode", action="store_true", help="Decode every selected clip and final movie")
    ap.add_argument("--require-continuity", action="store_true")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--validated-by", type=Path, help="Require successful smoke for both films using identical analysis code")
    args = ap.parse_args()
    if args.validated_by:
        verify_smoke(args.validated_by, args.frames, args.max_candidate_seconds)
    os.environ.setdefault("HF_HOME", "/home/edgar.chambilla/Tesis/SegLoop/data/hf_cache")
    model = NarrativeModel(args.out / "cache", args.device)
    run_narrative(args.run_dir, args.out, model, script=args.script,
                  budget_fraction=args.budget_fraction, frame_count=args.frames,
                  max_candidate_s=args.max_candidate_seconds, decode=args.decode,
                  require_continuity=args.require_continuity)


if __name__ == "__main__":
    main()
