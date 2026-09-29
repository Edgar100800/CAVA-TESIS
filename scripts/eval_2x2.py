"""EXP-014: análisis del 2×2 resúmenes (old/new) × razonador (7b/14b).

Evalúa cada celda con `eval_chapter.py --logit` (mismo instrumento que
EXP-013b) y calcula, por conjunto (desarrollo / replicación):
  criterio 1  por celda: ΔAP beat(celda − SegLoop) pareado
  criterio 2  efectos principales pareados por película:
              razonador = media(14b) − media(7b) sobre los dos niveles de resumen
              resúmenes = media(new) − media(old) sobre los dos razonadores
Solo usa películas con las cuatro celdas completas.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

CELLS = {"old_7b": "data/vjudge_chapter_logit", "new_7b": "data/chap2x2/new_7b",
         "old_14b": "data/chap2x2/old_14b", "new_14b": "data/chap2x2/new_14b"}
SETS = {"desarrollo": "scripts/exp011_step2_films.txt",
        "replicacion": "scripts/exp011_replication_films.txt"}


def ms(d):
    d = np.asarray(d, float)
    return {"mean": round(float(d.mean()), 4), "se": round(float(d.std(ddof=1) / np.sqrt(len(d))), 4),
            "n": len(d), "z": round(float(d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))), 2)}


def main():
    report = {}
    for set_name, films in SETS.items():
        per = {}
        for cell, d in CELLS.items():
            out = Path(f"results/exp014_{cell}_{set_name}.json")
            subprocess.run([sys.executable, "scripts/eval_chapter.py", "--films-file", films,
                            "--logit", d, "--out", str(out)], check=True,
                           stdout=subprocess.DEVNULL)
            per[cell] = json.loads(out.read_text())["per_film"]
        films_ok = sorted(set.intersection(*(set(v) for v in per.values())))
        ap = {c: np.array([per[c][t]["ap_beat_chapter"] for t in films_ok]) for c in CELLS}
        seg = np.array([per["old_7b"][t]["ap_beat_segloop"] for t in films_ok])
        rep = {"n_films": len(films_ok),
               "ap_beat_mean": {c: round(float(v.mean()), 4) for c, v in ap.items()}
               | {"segloop": round(float(seg.mean()), 4)},
               "cell_vs_segloop": {c: ms(v - seg) for c, v in ap.items()},
               "effect_reasoner_14b_minus_7b": ms((ap["old_14b"] + ap["new_14b"]) / 2
                                                  - (ap["old_7b"] + ap["new_7b"]) / 2),
               "effect_summaries_new_minus_old": ms((ap["new_7b"] + ap["new_14b"]) / 2
                                                    - (ap["old_7b"] + ap["old_14b"]) / 2)}
        report[set_name] = rep
        print(f"== {set_name} ({len(films_ok)} películas)")
        print(f"   AP beat: {rep['ap_beat_mean']}")
        for c, v in rep["cell_vs_segloop"].items():
            print(f"   {c} − SegLoop: {v}")
        print(f"   efecto razonador (14b−7b): {rep['effect_reasoner_14b_minus_7b']}")
        print(f"   efecto resúmenes (new−old): {rep['effect_summaries_new_minus_old']}")
    Path("results/exp014_2x2.json").write_text(json.dumps(report, indent=1))
    print("[out] results/exp014_2x2.json")


if __name__ == "__main__":
    main()
