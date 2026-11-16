# EXP-041-L — paquete operativo del A/B corto

**Enmienda:** `EXP-041-L_enmienda.md` (fechada 2026-11-16, antes de recolectar).
**Diseño:** 2 pares + control (T capítulos, H highlights 240 s, control CAVA/CAVA).
**Fuera:** par S, bloques B/E, N=60 (ver enmienda §1 y §7).

## Archivos

| Archivo | Función |
|---|---|
| `EXP-041-L_enmienda.md` | Pre-registro corto: hipótesis, MDE, análisis, desviaciones |
| `ab_form.html` | Formulario: registro, consentimiento, filtro, 3 elecciones, pregunta abierta, export CSV |
| `ab_timeline.html` | Visor ciego A/B: línea de tiempo con capítulos (T) o videos de 240 s (H) |
| `../../scripts/exp041_stimuli.py` | Genera CAVA y U desde la corrida congelada (`data/cava_runs_e041/`) |
| `../../scripts/ab_analysis.py` | Wilson + binomial + bootstrap clusterizado → tabla markdown |

## Cómo servirlo

Desde la raíz del repo (los clips viven en `data/`, que no se publica):

```bash
python3 -m http.server 8000
# abrir http://localhost:8000/reports/exp041/ab_form.html
```

El formulario asigna la secuencia (1–4) por el número del código de participante y
contrabalancea el lado de CAVA. El CSV acumulado se descarga con el botón.

## Estados

- `data/cava_runs_e041/cava/`: capítulos + `version_highlights240_0.mp4` + `viewer.json`.
- `data/cava_runs_e041/u/`: ídem para la base sin estructura.
- `data/cava_runs_e041/stimuli.json`: recuento y presupuestos.

## Reglas

- No revelar qué sistema es A o B hasta el debrief.
- El video de H debe verse completo (240 s) antes de responder.
- El par de control espera «Iguales»; se reporta su tasa como control de atención.
