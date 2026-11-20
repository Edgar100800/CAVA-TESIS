## EXP-043-DIA · Diarización de punta a punta (pyannote) frente a la identidad CAVA por unidades de 5 s (pre-registro)
- **Fecha:** 2026-11-20 (registrado antes de ejecutar pyannote sobre cualquier
  archivo de VoxConverse, AMI o los conjuntos docmix/domix)
- **Motivación:**
  - La identidad CAVA (EXP-028/029) etiqueta bloques de 5 s: no hay turnos con
    inicio y fin, ni solapamientos. En Spider-Man (EXP-042-FID) V6 mezcló a dos
    personajes y V7/V8 quedaron sin rostro.
  - EXP-039 declaró como siguiente candidato la segmentación con conteo local
    (pyannote). No se corrió por ser un modelo de acceso restringido.
- **Lo único que cambia:** el método de identidad. Candidato **P** =
  `pyannote/speaker-diarization-community-1` (snapshot 3533c8cf, con
  segmentation-3.0 e66f3d3b; pyannote.audio 4.1.1), parámetros
  por defecto, sin ajuste, sin número de hablantes dado. Referencia **C** = producto
  CAVA (WavLM-base-plus-sv por unidad de 5 s + detector EXP-029 + ward + BIC).
- **Datos:** VoxConverse test (232 archivos, RTTM v0.3). Sin desarrollo: P no
  tiene nada que ajustar.
- **Riesgo declarado (contaminación):** los modelos de pyannote se entrenaron con
  una mezcla que incluye VoxConverse (al menos dev) y AMI. C se entrenó en
  VoxCeleb. La ventaja de P en VoxConverse puede estar inflada; se reporta como
  límite y no se generaliza a películas sin más evidencia.
- **Protocolo primario (idéntico a EXP-028, para comparar con C):**
  - unidades de 5 s; hablante dominante GT ≥ 60 % del habla y ≥ 1,5 s; filtro de
    habla con VAD oráculo (≥ 50 % de la unidad), el mismo para P y C;
  - etiqueta de P en una unidad = hablante de P con más tiempo en esa unidad;
  - C = las cachés de EXP-028/029 ya calculadas (`xvec/`), sin recalcular.
- **Criterios (test, SE pareado por archivo):**
  1. ARI(P) − ARI(C) > 2 SE;
  2. |K_eff − K_true|(C) − |K_eff − K_true|(P) > 2 SE;
  3. archivos con K_true = 1: tasa de K_eff = 1 de P − de C > 2 SE
     (modo de fallo de EXP-028/029).
- **Lectura pre-declarada:**
  - 1 y 2 se cumplen: P reemplaza a C como identidad (V#) en los perfiles film y
    meeting, tras comprobar no inferioridad en AMI fresh3 (ARI, margen −0,02);
  - 3 se cumple: P resuelve el "un solo hablante"; se mide entonces docmix/domix
    conf (protocolo EXP-039) antes de tocar el perfil documentary;
  - 1 no: la identidad por bloques de 5 s se mantiene; P queda como trabajo futuro.
- **Secundarias (sin criterio):**
  - DER estándar (collar 0,25 s, con solapamientos) de P de punta a punta, y de C
    convertido a segmentos (unidad × VAD oráculo); JER;
  - desglose por número de hablantes y por fracción de habla solapada;
  - tiempo de cómputo por hora de audio.
- **Exploratorio, fuera de criterios:** P sobre Spider-Man (EXP-042-FID):
  correspondencia con V1–V8, si separa Punisher/Bill Metzger, y hablante activo
  por labios sobre turnos de P en vez de unidades de 5 s.
- **Cómputo:** 4 GPUs RTX PRO 4000 (lab .54, .55, .56, .61), venv aparte
  `dia-venv` (pyannote.audio 4.1.1, torch 2.15 cu132); 232 archivos en 4 shards.
