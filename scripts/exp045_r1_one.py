import sys, json
sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[1] + "/scripts")
import check_v11_nonregression as C
from pathlib import Path
name, work = sys.argv[2], Path(sys.argv[3])
frozen = C.FROZEN / "outputs" / name
out = C.run_cached(C.FROZEN / "videos" / f"{name}.mp4", frozen, work / name, "film", "v1.0")
print(json.dumps({k: v["semantic_diff"] for k, v in C.compare_contract_outputs(frozen, out).items()}), flush=True)
