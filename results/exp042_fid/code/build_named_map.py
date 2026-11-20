"""EXP-042-FID: topic_map con voces y personajes nombrados + línea de tiempo HTML.

Entrada: topic_map del run local (no se modifica), voice_per_unit.npy, v6_split.json,
scan.npz + names.json. Salida en exp036/fid/demo/.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

W = Path("/data/tesis-cava/exp036/fid")
RUN = Path("/data/tesis-cava/CAVA_minimo/outputs/Spider_Man")
OUT = W / "demo"
OUT.mkdir(exist_ok=True)

VOICE_NAMES = {
    "V1": ("Mary Jane Watson", "confirmada"), "V2": ("Yelena", "probable"),
    "V3": ("Peter Parker", "confirmada"), "V4": ("Peter Parker (Spider-Man, con máscara)", "probable"),
    "V5": ("Ned", "confirmada"), "V6a": ("Punisher", "confirmada tras dividir V6"),
    "V6b": ("Bill Metzger", "confirmada tras dividir V6"),
    "V7": ("Voz sin asignar", "sin evidencia"), "V8": ("Voz fuera de cuadro", "sin rostro"),
}

doc = json.loads((RUN / "topic_map.json").read_text())
state = json.loads((RUN / "work/state.json").read_text())
units = state["units"]
vid = np.load(W / "smoke/voice_per_unit.npy")
split = json.loads((W / "smoke/v6_split.json").read_text())["V6_split"]
vlab = [f"V{int(v)}" if v >= 0 else None for v in vid]
for g, tag in (("1", "V6a"), ("2", "V6b")):
    for u in split[g]:
        vlab[u] = tag

names = json.loads((W / "names.json").read_text())
d = np.load(W / "smoke/scan.npz")
starts = np.array([u[0] for u in units])
ui = np.clip(np.searchsorted(starts, d["times"], side="right") - 1, 0, len(units) - 1)
onscreen = defaultdict(Counter)
char_times = defaultdict(set)
for u, t, c in zip(ui, d["times"], d["cid"]):
    if c >= 0:
        n = names[str(int(c))]
        onscreen[int(u)][n] += 1
        char_times[n].add(round(float(t)))


def speakers(shots):
    c = Counter(vlab[u] for u in shots if vlab[u])
    tot = sum(c.values())
    return [{"id": v, "name": VOICE_NAMES[v][0], "share": round(k / tot, 3)} for v, k in c.most_common()]


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
doc["voice_names"] = {v: {"name": n, "evidence": e} for v, (n, e) in VOICE_NAMES.items()}
doc["voice_names_note"] = ("EXP-042-FID exploratorio: nombres por co-presencia de rostro + movimiento "
                           "de labios; sin anotación humana. V6 dividido en V6a/V6b (ward k=2).")
(OUT / "topic_map_named.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1))


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


char_rows = sorted(((n, to_intervals(ts)) for n, ts in char_times.items()),
                   key=lambda r: -sum(b - a for a, b in r[1]))
voice_ts = defaultdict(list)
for u, v in enumerate(vlab):
    if v:
        voice_ts[v].append(units[u][0])
voice_rows = [(f"{v} · {VOICE_NAMES[v][0]}", to_intervals(voice_ts[v], gap=5.0, pad=5.0))
              for v in VOICE_NAMES if voice_ts.get(v)]
topics = [{"t0": s[0], "t1": s[1], "label": t.get("topic_label") or t.get("label", ""), "id": t["topic_id"]}
          for t in doc["levels"]["default"]["topics"] if not t["flags"]["no_topic"] for s in t["spans"]]
data = {"duration": doc["duration_s"], "characters": char_rows, "voices": voice_rows, "topics": topics}

html = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>CAVA · personajes y voces</title>
<style>body{margin:0;background:#0f1117;color:#e8eaf0;font:13px system-ui,sans-serif}
header{padding:12px 16px;border-bottom:1px solid #2a2f3d}h1{font-size:15px;margin:0}.dim{color:#9aa3b5}
.wrap{padding:10px 16px}.row{display:grid;grid-template-columns:260px 1fr;align-items:center;margin:3px 0}
.lab{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;padding-right:8px}
.bar{position:relative;height:16px;background:#171a23;border-radius:3px}
.seg{position:absolute;top:0;bottom:0;border-radius:2px;cursor:pointer}
h2{font-size:12px;color:#7c9cff;margin:14px 0 4px}.axis{display:flex;justify-content:space-between;color:#9aa3b5;font-size:11px;margin-left:260px}
#tip{position:fixed;pointer-events:none;background:#000d;border:1px solid #2a2f3d;padding:5px 7px;border-radius:5px;display:none;max-width:380px}</style>
</head><body><header><h1>CAVA · personajes en pantalla y voces nombradas</h1>
<div class="dim">EXP-042-FID (exploratorio): rostros ArcFace agrupados + voces WavLM, nombradas por co-presencia y movimiento de labios. Sin anotación humana.</div></header>
<div class="wrap" id="w"></div><div id="tip"></div>
<script>const D=__DATA__;
const hms=t=>{t=Math.floor(t);return Math.floor(t/3600)+":"+String(Math.floor(t%3600/60)).padStart(2,"0")+":"+String(t%60).padStart(2,"0")};
const pal=["#7c9cff","#3ddc97","#ff8a65","#ffd54f","#ba68c8","#4dd0e1","#f06292","#aed581","#90a4ae"];
function row(label,ivs,color,tipf){return `<div class="row"><div class="lab" title="${label}">${label}</div><div class="bar">`+
 ivs.map(([a,b],i)=>`<div class="seg" style="left:${100*a/D.duration}%;width:${Math.max(.15,100*(b-a)/D.duration)}%;background:${typeof color==="function"?color(i):color}" data-t="${tipf?tipf(i):label+" · "+hms(a)+"–"+hms(b)}"></div>`).join("")+`</div></div>`}
let h=`<div class="axis">${[0,1,2,3,4,5,6].map(i=>`<span>${hms(i*D.duration/6)}</span>`).join("")}</div>`;
h+=`<h2>Tópicos (mapa CAVA)</h2>`+row("Tópicos",D.topics.map(t=>[t.t0,t.t1]),i=>pal[D.topics[i].id%pal.length],i=>`T${D.topics[i].id} · ${hms(D.topics[i].t0)}–${hms(D.topics[i].t1)} · ${D.topics[i].label}`);
h+=`<h2>Voces</h2>`+D.voices.map(([n,iv],i)=>row(n,iv,pal[i%pal.length])).join("");
h+=`<h2>Personajes en pantalla (rostro)</h2>`+D.characters.map(([n,iv],i)=>row(n,iv,pal[(i+3)%pal.length])).join("");
document.getElementById("w").innerHTML=h;const tip=document.getElementById("tip");
document.addEventListener("mousemove",e=>{const s=e.target.closest(".seg");if(!s){tip.style.display="none";return}
tip.style.display="block";tip.textContent=s.dataset.t;tip.style.left=Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8)+"px";tip.style.top=(e.clientY+14)+"px"});
</script></body></html>"""
(OUT / "timeline.html").write_text(html.replace("__DATA__", json.dumps(data, ensure_ascii=False)))

print("topic_map_named.json y timeline.html en", OUT)
cnt = Counter(t["speakers_named"][0]["name"] for t in doc["levels"]["default"]["topics"] if t["speakers_named"])
print("tópicos por voz dominante:", dict(cnt.most_common()))
for t in doc["levels"]["default"]["topics"][:5]:
    print(f"T{t['topic_id']}: voz={[s['name'] for s in t['speakers_named'][:2]]} pantalla={[c['name'] for c in t['characters_on_screen'][:3]]} | {(t.get('topic_label') or '')[:70]}")
