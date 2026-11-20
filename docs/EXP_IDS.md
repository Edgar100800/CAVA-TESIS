# Identificadores de experimentos — correspondencia canónica

> Creado 2026-11-16 para resolver la colisión de numeración **EXP-036**.
> Regla: el manuscrito usa **nombres descriptivos**; los IDs EXP viven en el repo y en el anexo.

| ID canónico | Alias anteriores | Ruta principal | Tema | Sección del manuscrito |
|---|---|---|---|---|
| EXP-036V | EXP-036 (segunda voz) | `results/exp036v_segunda_voz.json`, `logs/exp036v_segunda_voz.log`, `scripts/exp036_tau.py` | Detector de "¿hay una segunda voz con soporte propio?" (umbral `single_k1` / falsos `k2`) | OE1 / H1 (señal acústica de hablante) |
| EXP-036-F5 | EXP-036 (escenas verificables), F0–F5 | `results/exp036_f5_tramos/` | Protocolo F0–F5: briefs verificables, índice y búsqueda, piloto y cobertura completa de tramos | OE2 (agregación y continuidad de tópicos) |
| EXP-035 | — | `docs/` y `results/` del repo; paquete `EXP035_036_texto_*` | Catálogo de escenas y panel de personajes (texto libre) | OE2 / antecedente |
| EXP-042-FID | — | `results/exp042_fid/` | Identidades por rostro (InsightFace) + voces V1–V8 nombradas por co-presencia y labios; exploratorio, sin gold | OE1/OE3 (demo, nota de método; no resultado) |

## Notas

- La renumeración se hizo el **2026-11-16**; cualquier referencia externa a "EXP-036" anterior a esa fecha debe
  leerse según el tema (voz vs escenas verificables).
- Los manifiestos de hashes de F5 (`results/exp036_f5_tramos/state/full_index_hashes.txt`) no referencian
  `results/exp036.json`; la renumeración no invalida ningún hash.
- En el manuscrito: usar "Experimento de tramos verificables" y "Detector de segunda voz", no los números.
