# Figuras de la tesis

Todas las figuras con datos se generan con Python (matplotlib, backend pgf, la misma
tipografía que el documento) y se guardan como PDF vectorial en `images/generadas/`.

| Script | Figuras | Datos |
|---|---|---|
| `fig_flujo.py` | Figura del flujo de CAVA (cap. II) | íconos de `images/iconos/` |
| `fig_mecanismo.py` | M1–M5: fronteras, consenso, matriz de votos, percolación, mapa | caso sintético (`caso_sintetico.py`) pasado por el gestor real |
| `fig_resultados.py` | R0–R10 (cap. IV) | `results/*.json` |

```bash
pip install -e ".[figs]"
python tesis/figuras/generar_todas.py
```

Los íconos y los fotogramas del caso ilustrativo se generan con la herramienta de
imágenes de Codex a partir de los prompts en `prompts/`:

```bash
tesis/figuras/generar_imagenes.sh            # todos los que falten
tesis/figuras/generar_imagenes.sh voz mapa   # solo esos
```

Ninguna imagen generada representa datos: solo íconos y escenas de ejemplo.
