"""Submit DS only after both alternative-GPU smoke reports pass exact-code checks."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
import fcntl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cava_narrative import verify_smoke
from topicagg.narrative_model import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-root", type=Path, default=Path("data/films_narrative_smoke_v1"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    verify_smoke(args.smoke_root, 10, 30)
    if args.dry_run:
        print("Both GPU smoke reports passed; production can be submitted.")
        return
    receipt = args.smoke_root / "ds_submission.json"
    with receipt.with_suffix(".lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if receipt.exists():
            print("Already submitted: " + receipt.read_text(), flush=True)
            return
        command = ["sbatch", "--parsable", "scripts/narrative_films.sbatch"]
        result = subprocess.check_output(command, text=True).strip()
        job_id = result.split(";")[0]
        if not job_id.isdigit():
            raise ValueError(f"Unexpected sbatch response: {result}")
        value = {"production_job_id": job_id, "node": "ds001", "smoke_root": str(args.smoke_root),
                 "dispatcher_job_id": os.environ.get("SLURM_JOB_ID"),
                 "smoke_job_id": os.environ.get("CAVA_SMOKE_JOB_ID"),
                 "all_gpu_checks_passed": True}
        save_json(receipt, value)
        print(json.dumps(value, indent=2), flush=True)


if __name__ == "__main__":
    main()
