"""EXP-035b: muestra estratificada de unidades BBC para anotación humana ciega (ver pre-registro).

Estratos por episodio según los filtros de EXP-034 sobre todas las unidades:
  c0 W no · c1 W sí, S&W no, I&W no · c2 W sí, S&W sí, I&W no · c3 W sí, S&W no, I&W sí · c4 W, S&W, I&W sí
Se toman 2 / 5 / 3 / 3 / 3 por episodio (todas si hay menos), semilla 0.
→ data/gatebench/exp035b/clips/<clip>.mp3 (nombre opaco, orden aleatorio)
  data/gatebench/exp035b/sample.json (clave privada: clip → episodio, unidad, estrato, peso; NO se publica)
  data/gatebench/exp035b/manifest.json (lo que ve la página: solo clips en orden aleatorio)
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp034_eval import gates  # noqa: E402
from exp034_items import G, all_items  # noqa: E402

TAKE = {"c0": 2, "c1": 5, "c2": 3, "c3": 3, "c4": 3}
OUT = G / "exp035b"


def strata(g):
    w, s, i = g["W"], g["S&W"], g["I&W"]
    return {"c0": ~w, "c1": w & ~s & ~i, "c2": w & s & ~i, "c3": w & ~s & i, "c4": w & s & i}


def main():
    rng = np.random.default_rng(0)
    (OUT / "clips").mkdir(parents=True, exist_ok=True)
    rows = []
    for it in all_items(["bbc"]):
        g, _ = gates(it)
        for c, mask in strata(g).items():
            idx = np.where(mask)[0]
            pick = sorted(rng.choice(idx, min(TAKE[c], len(idx)), replace=False)) if len(idx) else []
            for u in pick:
                rows.append({"ep": it["id"], "unit": int(u), "t0": it["units"][u][0], "t1": it["units"][u][1],
                             "stratum": c, "stratum_size": int(len(idx)), "n_sampled": len(pick), "wav": it["wav"],
                             "gates": {k: bool(g[k][u]) for k in ("W", "A0.3&W", "S&W", "I&W", "P&W")}})
    order = rng.permutation(len(rows))
    for k, j in enumerate(order):
        r = rows[j]
        r["clip"] = f"c{k + 1:03d}_" + hashlib.sha1(f"{r['ep']}{r['unit']}".encode()).hexdigest()[:6]
        r["weight"] = r["stratum_size"] / r["n_sampled"]
        f = OUT / "clips" / f"{r['clip']}.mp3"
        if not f.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(r["t0"]), "-t", str(r["t1"] - r["t0"]), "-i", r["wav"],
                            "-ac", "1", "-b:a", "96k", str(f)], check=True)
    rows = [rows[j] for j in order]
    (OUT / "sample.json").write_text(json.dumps(rows, indent=1))
    (OUT / "manifest.json").write_text(json.dumps([r["clip"] for r in rows]))
    print(f"{len(rows)} clips; por estrato:", {c: sum(r['stratum'] == c for r in rows) for c in TAKE})


if __name__ == "__main__":
    main()
