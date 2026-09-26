# Diagnóstico v1 — la señal de video en la jerarquía multimodal de a2summ_x

> 2026-09-24 · Validación final del modelo v1 (pre-tópicos). Análisis mecánico del código +
> convergencia de evidencia experimental (paper + OOD SegLoop). Conclusión: **el aplastamiento
> de la señal visual es estructural, no un bug** — y motiva el rediseño por tópicos (v2).

## 1. El recorrido de la señal visual en `a2summ_x/model.py`

```
frames (CLIP-pool5 1024-d, FROZEN)
  → ModalityAdapter(Linear 1024→256)                      # video: solo proyección
  → FlexibleCrossModalAlignment(query=video, key=TEXTO)   # video REESCRITO con texto
  → [fusión jerárquica frames→shots→video]
  → ModalityGating(softmax V/A/T)                         # video COMPITE por peso
  → FusedSceneRelevanceHead(blend)                        # un solo score del blend
```

### 1.1 La reescritura por alineación (`fusion/cross_modal_alignment.py`)

En `model.py`, el video es la **query** y el texto el key/value:
`v2t = FlexibleCrossModalAlignment(...)` → `out = LayerNorm(query + attn(text))`.
Mecánicamente: cada shot visual termina siendo `video + Σ_attn(texto)` — la representación
del shot **incorpora el contenido del transcript**. Con features visuales congeladas
(CLIP-pool5, sin fine-tune) y features de texto pre-entrenadas (RoBERTa), el término de texto
aporta varianza mucho más discriminativa para el objetivo F1. **El tensor "video" que llega al
gating ya no es puro video: es video condicionado por transcripción.**

### 1.2 La competencia cero-suma (`heads/modality_gating.py`)

`weights = gate(cat).softmax(-1); fused = Σ weights·stacked`. El softmax hace que las
modalidades **compitan** por un peso que suma 1: si el texto es más predictivo del label F1,
su peso crece y el visual baja — **no hay mecanismo de complementariedad** (el video no puede
"sumar" cuando el texto ya acierta; solo puede perder participación). El paper mide el
resultado: gating texto 0.75–0.89 (SumMe/TVSum).

### 1.3 El head sobre el blend (`heads/score_heads.py`)

`FusedSceneRelevanceHead` lee el blend fundido. Los errores específicos de la señal visual
(p.ej. segmentar mal un corte visual) quedan invisibles si el texto corrige el score en
promedio: el F1 agregado no descompone por-modalidad. El paper lo registró: el efecto del
texto es F1 (+0.033 TVSum, p=0.014) pero **no en ranking** (NDCG ns) — y no existe métrica de
"aporte visual condicionado".

## 2. Convergencia de evidencia (4 fuentes independientes)

| # | Fuente | Evidencia |
|---|---|---|
| 1 | Paper A2Summ-X | gating texto 0.75–0.89; ΔF1 texto +0.033 (p=0.014); control V-JEPA-2 nulo (p=0.82): **mejores features visuales no mueven nada** |
| 2 | GraphVSum en BLiSS (contexto del paper) | rama visual **colapsa** (vid_pred_pos≈0) mientras la de texto aprende (ROUGE-L 44.9) |
| 3 | OOD SegLoop (TVSum/SumMe, 2026-09) | señal visual de frontera **no codifica importancia** (Spearman ρ≈0.04–0.06 vs saltos humanos) |
| 4 | Contenido | streams/talking-heads: 21/24 videos SumMe = 1 solo shot; la diferenciación visual por cortes desaparece justo en el contenido objetivo |

## 3. Diagnóstico: por qué es estructural

1. **Asimetría de pretraining**: RoBERTa (texto) trae millones de horas de señal semántica;
   CLIP-pool5 congelado solo aporta apariencia. Sobre el objetivo F1-importancia, el texto gana
   por construcción.
2. **Granularidad**: el pipeline v1 opera frame/frame-shot (2s). La continuidad semántica de un
   tema que se retoma a los 10 minutos es invisible a esa escala.
3. **Objetivo**: F1 contra importancia crowd premia el acierto agregado; no premia preservar
   la identidad de cada modalidad.
4. **Arquitectura**: alineación reescribe + gating compite + head funde — tres puntos donde el
   texto puede dominar y ninguno donde el video se preserve como señal propia.

## 4. Consecuencia de diseño (v2 — topicagg)

No se "arregla" con más peso al video: se **separa la señal por tópicos antes de fusionar**:

- Agregar por **tópico** usando 4 señales en paralelo: **transcript** (temporizado),
  **texto en pantalla** (OCR — el caso TPU: lo que dice el streamer y lo escrito en pantalla
  son la MISMA señal temática aunque estén separados en el tiempo), **audio** (eventos/voz),
  **video** (frames).
- La agregación por similitud temática **enlaza segmentos no adyacentes** del mismo tópico
  (conecta los dos puntos que v1 no podía conectar sin audio).
- Sobre los grupos temáticos recién se produce la multi-versión por consumidor.

Ver `docs/journey.md` + `topic_aggregator.py`.
