"""EXP-036 F5: prueba de humo sobre el índice real (tras f5_index.py).

Comprueba: conteos del índice vs F1/F2 (66+57 escenas ok), intervalos dentro del film, FTS5 accesible,
los 8 métodos devuelven resultados con intervalo válido, la localización cae dentro de la escena y la
latencia caliente < 2 s. No toca F1/F2 ni escribe nada.

Uso: CAVA_minimo/.venv/bin/python -I exp036/f5/f5_smoke.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f5_search  # noqa: E402
from f5_common import EXP, inter_len, length, load_json  # noqa: E402


def main():
    ix = f5_search.load()
    for mov, n in (("Avengers_Endgame", 66), ("Spider_Man", 57)):
        esc = load_json(EXP / "outputs" / mov / "escenas.json")["scenes"]
        got = [d for d in ix.docs if d["movie"] == mov and d["level"] == "scene"]
        assert len(esc) == n == len(got), (mov, len(esc), len(got))
        assert all(abs(d["t0"] - s["t0"]) < 1e-6 and abs(d["t1"] - s["t1"]) < 1e-6
                   for d, s in zip(got, esc)), mov
    assert ix.con.execute("SELECT count(*) FROM docs").fetchone()[0] == len(ix.docs)
    q = "Thor talks with his mother in Asgard"
    for m in f5_search.METHODS:
        res, dt = ix.search(q, "Avengers_Endgame", ("scene",), m, 3)
        assert res and dt < 2.0, (m, dt)
        for r in res:
            assert all(0 <= a < b for a, b in r["intervals"]), (m, r["intervals"])
        if m == "hybrid_rerank_loc":
            for r in res:
                doc = next(d for d in ix.docs if d["movie"] == r["movie"] and d["unit"] == r["unit"])
                assert abs(inter_len(r["intervals"], doc["spans"]) - length(r["intervals"])) < 1e-6
        print(f"  {m:18s} {dt * 1000:6.0f} ms  top1={res[0]['unit']} {res[0]['t0_hms']}-{res[0]['t1_hms']}")
    res, _ = ix.search(q, "all", ("scene", "topic", "fine"), "hybrid_rerank_loc", 5)
    assert {r["level"] for r in res} <= {"scene", "topic", "fine"}
    print("smoke OK")


if __name__ == "__main__":
    main()
