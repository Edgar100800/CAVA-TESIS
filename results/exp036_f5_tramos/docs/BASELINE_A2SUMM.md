# Baseline externo — A2Summ (TVSum / SumMe)

**Fecha:** 2026-11-16
**Origen:** repo público `boheumd/A2Summ` (CVPR 2023, "Align and Attend: Multimodal Summarization
with Dual Contrastive Losses"), features preprocesadas de Google Drive (GoogleNet pool5 + RoBERTa)
y checkpoints oficiales. Copia de trabajo: `/data/tesis-cava/baselines/A2Summ`.

## 1. Puesta en marcha

- Repo clonado en `baselines/A2Summ`; datos TVSum/SumMe en `baselines/data/`.
- Checkpoints oficiales (tar de 191 MB, contiene TVSum y SumMe) en `saved_model/{TVSum,SumMe}/`.
- Dos parches de compatibilidad (ortools ≥ 9 cambió la API de knapsack):
  `helpers/vsumm_helper.py` — import y `init/solve/best_solution_contains`.
- `config.py`: `--seed` ahora permite override (antes lo pisaba el hiperparámetro del dataset).
- Entorno: `thesis-venv` (torch 2.11+cu128); deps añadidas: `h5py pyyaml scipy ortools tqdm
  tensorboard rouge-score gdown`.

## 2. Reproducción (checkpoints oficiales, 5-fold)

| dataset | F1 medido | F1 del paper | Δ |
|---|---:|---:|---:|
| TVSum | **0.6316** | 0.634 | −0.002 |
| SumMe | **0.5490** | 0.550 | −0.001 |

Tiempo: ~30 s por dataset en GPU (inferencia sola; los features ya están extraídos).

## 3. Protocolo Otani (2019): aleatorio, uniforme y correlaciones de rango

`metrics_vsumm.py` (100 repeticiones para aleatorio, knapsack al 15 %, métrica avg para TVSum y
max para SumMe, igual que el repo). τ = Kendall, ρ = Spearman entre la importancia predicha por
el modelo y `gtscore`.

| dataset | modelo F1 | aleatorio F1 | uniforme F1 | τ | ρ |
|---|---:|---:|---:|---:|---:|
| TVSum | 0.6300 | 0.5664 | 0.5880 | 0.2505 | 0.3582 |
| SumMe | 0.5490 | 0.4028 | 0.4320 | 0.0960 | 0.1316 |

Lectura: en TVSum el F1 de un resumen aleatorio (0.566) queda a 6.5 pp del modelo (0.630),
consistente con la crítica de Otani et al. (CVPR 2019): el F1 de keyshots está dominado por la
segmentación y el presupuesto, no por la calidad del ranking. Por eso se reportan τ y ρ.

## 4. Entrenamiento propio (desde cero, hiperparámetros oficiales, 300 ép./fold)

| run | máquina | seed | estado |
|---|---|---|---|
| TVSum | .56 (local) | 666 | en curso |
| TVSum | .61 | 2 | en curso |
| TVSum | .55 | 3 | en curso |
| SumMe | .54 | 666 | en curso |
| SumMe | .56 (local, tras TVSum) | 2 | en cola |
| SumMe | .61 (tras TVSum) | 3 | en cola |

`python train.py --dataset {TVSum,SumMe} --data_root data --model_dir logs \
  --suffix scratch_s<seed> --seed <seed> --num_workers 4`

Salidas: `logs/<dataset>_scratch_s<seed>/{log.txt,args.yml,checkpoint/}`.
ETA por run: ~1.5 h (5 folds × ~17 min).

## 5. Reproducción de los comandos

```bash
cd /data/tesis-cava/baselines/A2Summ
P=/data/tesis-cava/thesis-venv/bin/python
# test con checkpoints oficiales
$P train.py --dataset TVSum --data_root ../data --test --checkpoint saved_model/TVSum --model_dir logs
$P train.py --dataset SumMe --data_root ../data --test --checkpoint saved_model/SumMe --model_dir logs
# métricas Otani
$P metrics_vsumm.py --dataset TVSum --data_root ../data --checkpoint saved_model/TVSum \
   --out metrics/TVSum_official.json --device cpu --reps 100
$P metrics_vsumm.py --dataset SumMe --data_root ../data --checkpoint saved_model/SumMe \
   --out metrics/SumMe_official.json --device cpu --reps 100
```

## 6. Notas para el manuscrito

- No comparar directamente CAVA con A2Summ: tareas distintas (selección de keyshots vs
  descripciones verificables + localización por consulta). A2Summ ancla el protocolo y la
  infraestructura en un benchmark estándar.
- Los F1 entre artículos no son estrictamente comparables (splits distintos); las filas propias
  usan los splits de A2Summ.
- El texto de A2Summ en TVSum/SumMe son captions automáticas del dataset, no transcripciones:
  no es equivalente a la modalidad ASR/VJudge de CAVA.
