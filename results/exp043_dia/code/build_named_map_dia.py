"""EXP-043-DIA (exploratorio): demo de Spider-Man con los hablantes de pyannote nombrados.

Entrada: topic_map del run local (no se modifica), turnos pyannote fusionados, nombres curados
(SPEAKER_NAMES, a partir de speaker_names_auto.json), rostros de EXP-042-FID.
Salida: exp036/dia/demo/topic_map_named_dia.json y timeline_dia.html.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

S = Path("/data/tesis-cava/exp036/dia/spider")
F = Path("/data/tesis-cava/exp036/fid")
RUN = Path("/data/tesis-cava/CAVA_minimo/outputs/Spider_Man")
OUT = Path("/data/tesis-cava/exp036/dia/demo")
OUT.mkdir(exist_ok=True)

# Curado sobre speaker_names_auto.json (labios + presencia en pantalla por turno) y spider_compare.json.
SPEAKER_NAMES = {
    "SPEAKER_10": ("Peter Parker", "labios"),
    "SPEAKER_09": ("Mary Jane Watson", "labios + pantalla"),
    "SPEAKER_19": ("Ned", "labios + pantalla"),
    "SPEAKER_06": ("Punisher", "labios + pantalla"),
    "SPEAKER_18": ("Bill Metzger", "labios + pantalla"),
    "SPEAKER_11": ("Yelena", "labios + pantalla"),
    "SPEAKER_07": ("Jean Grey", "labios + pantalla"),
    "SPEAKER_05": ("Detective Jean Wolff", "probable: pantalla ×29, labios 0,39 vs 0,28"),
    "SPEAKER_03": ("Bruce Banner", "labios + pantalla"),
    "SPEAKER_04": ("Sin nombre J", "labios + pantalla"),
    "SPEAKER_02": ("Aunt May", "labios + pantalla"),
    "SPEAKER_08": ("Sara Grey", "labios + pantalla"),
    "SPEAKER_14": ("Peter Parker (Spider-Man, con máscara)", "probable: pantalla ×15,5"),
    "SPEAKER_17": ("Voz sin asignar (S17)", "labios a Peter, pero voz del grupo femenino V1"),
    "SPEAKER_12": ("Voz sin asignar (S12)", "sin rostro; voz del grupo V5"),
    "SPEAKER_13": ("Voz sin asignar (S13)", "sin rostro; voz del grupo V5"),
    "SPEAKER_16": ("Voz mixta (acción / fuera de cuadro)", "sin rostro dominante"),
    "SPEAKER_15": ("Voz sin rostro (S15)", "sin evidencia"),
    "SPEAKER_01": ("Voz sin asignar (S01)", "17 s; labios a Peter sin pantalla"),
    "SPEAKER_00": ("Voz sin rostro (S00)", "sin evidencia"),
}

doc = json.loads((RUN / "topic_map.json").read_text())
units = json.loads((RUN / "work/state.json").read_text())["units"]
turns = json.loads((S / "turns_merged.json").read_text())

names = json.loads((F / "names.json").read_text())
d = np.load(F / "smoke/scan.npz")
starts = np.array([u[0] for u in units])
ui = np.clip(np.searchsorted(starts, d["times"], side="right") - 1, 0, len(units) - 1)
onscreen = defaultdict(Counter)
char_times = defaultdict(set)
for u, t, c in zip(ui, d["times"], d["cid"]):
    if c >= 0:
        n = names[str(int(c))]
        onscreen[int(u)][n] += 1
        char_times[n].add(round(float(t)))

unit_speech = defaultdict(Counter)
for a, b, s in turns:
    i = max(0, int(np.searchsorted(starts, a, side="right")) - 1)
    while i < len(units) and units[i][0] < b:
        o = min(b, units[i][1]) - max(a, units[i][0])
        if o > 0:
            unit_speech[i][SPEAKER_NAMES[s][0]] += o
        i += 1


def speakers(shots):
    c = Counter()
    for u in shots:
        c.update(unit_speech.get(u, {}))
    tot = sum(c.values())
    return [{"name": n, "share": round(k / tot, 3), "speech_s": round(k, 1)} for n, k in c.most_common()] if tot else []


def characters(shots):
    c = Counter()
    for u in shots:
        c.update(onscreen.get(u, {}))
    tot = sum(c.values())
    return [{"name": n, "share": round(k / tot, 3)} for n, k in c.most_common(5)] if tot else []


for level in doc["levels"].values():
    for t in level["topics"]:
        t["speakers_named"] = speakers(t["shots"])
        t["characters_on_screen"] = characters(t["shots"])
doc["speaker_source"] = "pyannote/speaker-diarization-community-1 (turnos), nombres por labios + presencia en pantalla"
doc["speaker_names"] = {s: {"name": n, "evidence": e} for s, (n, e) in SPEAKER_NAMES.items()}
doc["speaker_names_note"] = ("EXP-043-DIA exploratorio sobre EXP-042-FID: sin anotación humana. Los V# originales "
                             "(embedding por unidad) se conservan en el campo 'speakers' de cada tópico.")
(OUT / "topic_map_named_dia.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))


def to_intervals(ts, gap=5.0, pad=1.0):
    ts = sorted(ts)
    if not ts:
        return []
    ivs, cur = [], [ts[0], ts[0]]
    for t in ts[1:]:
        if t - cur[1] <= gap:
            cur[1] = t
        else:
            ivs.append(cur)
            cur = [t, t]
    ivs.append(cur)
    return [[a, b + pad] for a, b in ivs]


by_name = defaultdict(list)
for a, b, s in turns:
    by_name[SPEAKER_NAMES[s][0]].append([round(a, 2), round(b, 2)])
ev = {}
for s, (n, e) in SPEAKER_NAMES.items():
    ev.setdefault(n, []).append(f"{s.replace('SPEAKER_', 'S')}: {e}")
voice_rows = sorted(([n, ivs, " · ".join(ev[n])] for n, ivs in by_name.items()),
                    key=lambda r: (r[0].startswith("Voz"), -sum(b - a for a, b in r[1])))
char_rows = sorted(([n, to_intervals(ts)] for n, ts in char_times.items()), key=lambda r: -sum(b - a for a, b in r[1]))
topics = [{"t0": s[0], "t1": s[1], "label": t.get("topic_label") or t.get("label", ""), "id": t["topic_id"],
           "who": ", ".join(x["name"] for x in t["speakers_named"][:2])}
          for t in doc["levels"]["default"]["topics"] if not t["flags"]["no_topic"] for s in t["spans"]]
data = {"duration": doc["duration_s"], "characters": char_rows, "voices": voice_rows, "topics": topics}

html = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>CAVA · quién habla (diarización)</title>
<style>body{margin:0;background:#0f1117;color:#e8eaf0;font:13px system-ui,sans-serif}
header{padding:12px 16px;border-bottom:1px solid #2a2f3d}h1{font-size:15px;margin:0}.dim{color:#9aa3b5}
.wrap{padding:10px 16px}.row{display:grid;grid-template-columns:280px 1fr;align-items:center;margin:3px 0}
.lab{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px}
.bar{position:relative;height:16px;background:#171a23;border-radius:3px}
.seg{position:absolute;top:0;bottom:0;border-radius:2px;cursor:pointer;min-width:1px}
h2{font-size:12px;color:#7c9cff;margin:14px 0 4px}.axis{display:flex;justify-content:space-between;color:#9aa3b5;font-size:11px;margin-left:280px}
.unk .lab{color:#9aa3b5;font-style:italic}
#tip{position:fixed;pointer-events:none;background:#000d;border:1px solid #2a2f3d;padding:5px 7px;border-radius:5px;display:none;max-width:420px}</style>
</head><body><header><h1>CAVA · quién aparece y quién habla — Spider-Man (145 min)</h1>
<div class="dim">Voces: diarización pyannote (turnos reales, 20 hablantes), nombradas por movimiento de labios y presencia en pantalla. Rostros: ArcFace agrupados y nombrados a mano. Exploratorio, sin anotación humana.</div></header>
<div class="wrap" id="w"></div><div id="tip"></div>
<script>const D=__DATA__;
const hms=t=>{t=Math.floor(t);return Math.floor(t/3600)+":"+String(Math.floor(t%3600/60)).padStart(2,"0")+":"+String(t%60).padStart(2,"0")};
const pal=["#7c9cff","#3ddc97","#ff8a65","#ffd54f","#ba68c8","#4dd0e1","#f06292","#aed581","#90a4ae","#ffb74d","#81d4fa","#e57373","#c5e1a5"];
function row(label,ivs,color,tipf,cls,title){return `<div class="row ${cls||""}"><div class="lab" title="${title||label}">${label}</div><div class="bar">`+
 ivs.map(([a,b],i)=>`<div class="seg" style="left:${100*a/D.duration}%;width:${Math.max(.08,100*(b-a)/D.duration)}%;background:${typeof color==="function"?color(i):color}" data-t="${tipf?tipf(i):label+" · "+hms(a)+"–"+hms(b)}"></div>`).join("")+`</div></div>`}
let h=`<div class="axis">${[0,1,2,3,4,5,6].map(i=>`<span>${hms(i*D.duration/6)}</span>`).join("")}</div>`;
h+=`<h2>Tópicos (mapa CAVA)</h2>`+row("Tópicos",D.topics.map(t=>[t.t0,t.t1]),i=>pal[D.topics[i].id%pal.length],i=>`T${D.topics[i].id} · ${hms(D.topics[i].t0)}–${hms(D.topics[i].t1)} · hablan: ${D.topics[i].who||"—"} · ${D.topics[i].label}`);
h+=`<h2>Quién habla (turnos de diarización)</h2>`+D.voices.map(([n,iv,e],i)=>row(n,iv,n.startsWith("Voz")?"#5a6275":pal[i%pal.length],null,n.startsWith("Voz")?"unk":"",n+" — "+e)).join("");
h+=`<h2>Quién aparece (rostro)</h2>`+D.characters.map(([n,iv],i)=>row(n,iv,pal[(i+3)%pal.length])).join("");
document.getElementById("w").innerHTML=h;const tip=document.getElementById("tip");
document.addEventListener("mousemove",e=>{const s=e.target.closest(".seg");if(!s){tip.style.display="none";return}
tip.style.display="block";tip.textContent=s.dataset.t;tip.style.left=Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8)+"px";tip.style.top=(e.clientY+14)+"px"});
</script></body></html>"""
(OUT / "timeline_dia.html").write_text(html.replace("__DATA__", json.dumps(data, ensure_ascii=False)))

print("salida:", OUT)
named = sum(1 for n, _ in SPEAKER_NAMES.values() if not n.startswith("Voz"))
tt = sum(b - a for a, b, _ in turns)
nt = sum(b - a for a, b, s in turns if not SPEAKER_NAMES[s][0].startswith("Voz"))
print(f"hablantes con nombre: {named}/20 · personajes distintos: "
      f"{len({n for n, _ in SPEAKER_NAMES.values() if not n.startswith('Voz')})} · habla con nombre: {nt / tt:.0%} de {tt:.0f} s")
cnt = Counter(t["speakers_named"][0]["name"] for t in doc["levels"]["default"]["topics"] if t["speakers_named"])
print("tópicos por voz dominante:", dict(cnt.most_common()))
