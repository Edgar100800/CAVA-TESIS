"""Capa de contenido de referencia por película (EXP-019): quién aparece, quién
habla y qué dice, por shot. Es GT de validación, nunca señal de CAVA.

Fuentes MovieNet:
  meta/<tt>.json       cast: id IMDb -> nombre del personaje (alias)
  annotation/<tt>.json cast por shot (pid) -> quién aparece en pantalla
  script/<tt>.script   bloques HABLANTE + diálogo (sin tiempos)
  subtitle/<tt>.srt    los mismos diálogos con tiempos
Alineación guion↔subtítulos: contención idf de cada cue en cada línea del guion
(qué fracción ponderada de las palabras del cue está en la línea; un cue suele
ser un fragmento de la línea) y un camino MONÓTONO de máxima suma (programación
dinámica) donde varios cues consecutivos pueden caer en la misma línea y solo
cuentan pares con contención ≥ --min-sim. Cada cue alineado hereda el hablante;
cada shot recibe los cues que lo solapan. Tabs expandidos y palabras cortadas
con guion al final de línea re-unidas.

Salida: data/movienet_content_gt/<tt>.json
  characters: {char_id: {"name", "aliases"}}
  shots: [{"on_screen": [char_id], "speakers": [char_id], "lines": [str]}]
  stats: cobertura de alineación, hablantes sin mapear
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrative_interpreter import parse_srt  # noqa: E402

MN = Path("/home/edgar.chambilla/Tesis/SegLoop/data/movienet")
SPEAKER = re.compile(r"^\s{10,}([A-Z][A-Z0-9 .'\-]{1,40}?)\s*(\(.*\))?\s*$")
STOP = {"the", "and", "you", "that", "for", "are", "was", "with", "this", "have", "not", "but",
        "what", "your", "all", "can", "just", "don", "get", "out", "know", "there", "him", "her"}
TITLES = {"mr", "mrs", "ms", "miss", "dr", "det", "lt", "sgt", "capt", "captain", "agent",
          "officer", "sir", "lord", "lady", "uncle", "aunt", "auntie", "father", "mother"}


def tokens(text):
    return [w for w in re.findall(r"[a-z']+", text.lower()) if len(w) > 2 and w not in STOP]


def aliases(character):
    """'L.B. 'Jeff' Jefferies' -> {'jeff', 'jefferies'}; títulos fuera."""
    out = set(re.findall(r"['\"]([A-Za-z]+)['\"]", character))
    words = [w for w in re.findall(r"[A-Za-z]+", character) if len(w) > 2]
    words = [w for w in words if w.lower() not in TITLES]
    if words:
        out |= {words[0], words[-1]}
    return {a.lower() for a in out if len(a) > 2}


def parse_script(path):
    lines, spk, buf = [], None, []
    for raw in Path(path).read_text(errors="ignore").expandtabs(8).splitlines():
        m = SPEAKER.match(raw)
        if m and not raw.strip().endswith(":"):
            if spk and buf:
                lines.append((spk, " ".join(buf)))
            spk, buf = m.group(1).strip(), []
        elif raw.strip() == "":
            if spk and buf:
                lines.append((spk, " ".join(buf)))
                spk, buf = None, []
        elif spk is not None and raw.startswith(" " * 8):
            t = raw.strip()
            if buf and buf[-1].endswith("-") and not buf[-1].endswith("--"):
                buf[-1] = buf[-1][:-1] + t       # palabra cortada al final de línea
            else:
                buf.append(t)
        else:
            if spk and buf:
                lines.append((spk, " ".join(buf)))
            spk, buf = None, []
    if spk and buf:
        lines.append((spk, " ".join(buf)))
    return lines


def tfidf_matrix(docs, vocab):
    idx = {w: i for i, w in enumerate(vocab)}
    df = np.zeros(len(vocab))
    toks = [tokens(d) for d in docs]
    for t in toks:
        for w in set(t):
            if w in idx:
                df[idx[w]] += 1
    return toks, idx, df


def align(script_lines, cues, min_sim):
    """Camino monótono de máxima suma de (contención − min_sim); varios cues
    consecutivos pueden asignarse a la misma línea del guion."""
    sdocs = [t for _, t in script_lines]
    cdocs = [t for _, _, t in cues]
    if not sdocs or not cdocs:
        return {}, None
    vocab = sorted({w for d in sdocs + cdocs for w in tokens(d)})
    idx = {w: i for i, w in enumerate(vocab)}
    n_docs = len(sdocs) + len(cdocs)
    df = np.zeros(len(vocab))
    for d in sdocs + cdocs:
        for w in set(tokens(d)):
            df[idx[w]] += 1
    idf = np.log((1 + n_docs) / (1 + df)) + 1
    L = np.zeros((len(sdocs), len(vocab)), bool)
    for r, d in enumerate(sdocs):
        L[r, [idx[w] for w in set(tokens(d))]] = True
    C = np.zeros((len(cdocs), len(vocab)), np.float32)
    for r, d in enumerate(cdocs):
        for w in set(tokens(d)):
            C[r, idx[w]] = idf[idx[w]]
    mass = C.sum(1)
    S = (L.astype(np.float32) @ C.T) / np.maximum(mass, 1e-8)[None, :]   # contención [lines, cues]
    S[:, mass == 0] = 0.0
    G = np.where(S >= min_sim, S - min_sim, -np.inf)
    n, m = S.shape
    D = np.zeros((n + 1, m + 1), np.float32)
    back = np.zeros((n + 1, m + 1), np.int8)   # 0 diag-match, 3 misma línea, 1 arriba, 2 izquierda
    for i in range(1, n + 1):
        gi = G[i - 1]
        Di, Dp, bi = D[i], D[i - 1], back[i]
        for j in range(1, m + 1):
            g = gi[j - 1]
            best, code = Dp[j], 1
            if Di[j - 1] > best:
                best, code = Di[j - 1], 2
            if g > -np.inf:
                if Dp[j - 1] + g > best:
                    best, code = Dp[j - 1] + g, 0
                if bi[j - 1] in (0, 3) and Di[j - 1] + g > best:
                    best, code = Di[j - 1] + g, 3
            Di[j], bi[j] = best, code
    pairs, i, j = {}, n, m
    while i > 0 and j > 0:
        b = back[i, j]
        if b in (0, 3):
            pairs[j - 1] = i - 1
            if b == 0:
                i -= 1
            j -= 1
        elif b == 1:
            i -= 1
        else:
            j -= 1
    return pairs, S


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--films-file", required=True)
    ap.add_argument("--corpus", default="data/movienet_topics")
    ap.add_argument("--min-sim", type=float, default=0.5)
    ap.add_argument("--out", default="data/movienet_content_gt")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for tt in Path(args.films_file).read_text().split():
        meta = json.loads((MN / "meta" / f"{tt}.json").read_text())
        ann = json.loads((MN / "annotation" / f"{tt}.json").read_text())
        corp = json.loads((Path(args.corpus) / f"{tt}.json").read_text())
        st, n = corp["shot_times"], corp["n_shots"]
        chars = {}
        for c in meta.get("cast") or []:
            if c.get("id") and c.get("character"):
                chars[c["id"]] = {"name": c["character"], "aliases": sorted(aliases(c["character"]))}
        # hablantes del guion -> personaje por alias (preferencia: orden del cast)
        lines = parse_script(MN / "script" / f"{tt}.script")
        spk_map, unmapped = {}, {}
        for spk, _ in lines:
            if spk in spk_map or spk in unmapped:
                continue
            toks = {w for w in re.findall(r"[a-z]+", spk.lower()) if w not in TITLES and len(w) > 2}
            hit = next((cid for cid, c in chars.items() if toks & set(c["aliases"])), None)
            (spk_map.__setitem__(spk, hit) if hit else unmapped.__setitem__(spk, 0))
        for spk, _ in lines:
            if spk in unmapped:
                unmapped[spk] += 1
        cues = parse_srt(MN / "subtitle" / f"{tt}.srt")
        pairs, S = align(lines, cues, args.min_sim)
        shots = [{"on_screen": set(), "speakers": set(), "lines": []} for _ in range(n)]
        for c in ann.get("cast") or []:
            if c.get("pid") in chars and c["shot_idx"] < n:
                shots[c["shot_idx"]]["on_screen"].add(c["pid"])
        starts = np.array([a for a, b in st])
        for j, i in pairs.items():
            a, b, text = cues[j]
            spk = spk_map.get(lines[i][0])
            k0 = max(0, int(np.searchsorted(starts, a, side="right")) - 1)
            for k in range(k0, n):
                if st[k][0] >= b:
                    break
                if st[k][1] > a:
                    if spk:
                        shots[k]["speakers"].add(spk)
                    shots[k]["lines"].append(lines[i][1])
        doc = {"video_id": tt, "characters": chars,
               "speaker_map": {s: c for s, c in spk_map.items()},
               "shots": [{"on_screen": sorted(s["on_screen"]), "speakers": sorted(s["speakers"]),
                          "lines": list(dict.fromkeys(s["lines"]))} for s in shots],
               "stats": {"script_lines": len(lines), "cues": len(cues),
                         "cues_aligned": len(pairs), "cue_coverage": round(len(pairs) / max(1, len(cues)), 3),
                         "script_lines_mapped_speaker": round(sum(1 for s, _ in lines if s in spk_map)
                                                              / max(1, len(lines)), 3),
                         "unmapped_speakers_top": sorted(unmapped.items(), key=lambda x: -x[1])[:8]}}
        (out / f"{tt}.json").write_text(json.dumps(doc, ensure_ascii=False))
        s = doc["stats"]
        print(f"[contentgt] {tt}: líneas {s['script_lines']} cues {s['cues']} alineados "
              f"{s['cue_coverage']:.0%} hablante mapeado {s['script_lines_mapped_speaker']:.0%}", flush=True)


if __name__ == "__main__":
    main()
