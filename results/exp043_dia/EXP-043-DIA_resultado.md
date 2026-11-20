### Resultado EXP-043-DIA (2026-11-20; lab .54/.55/.56/.61, 43,5 h de audio en 45 min de GPU, RTF 0,017)

Referencia C reproducida con el código del producto sobre las cachés de EXP-028:
ARI sin detector 0,6344 (EXP-028: 0,6345, 228 archivos).

| criterio (VoxConverse test, 232) | C | P | diferencia | ¿cumple? |
|---|---|---|---|---|
| 1. ARI | 0,661 | **0,938** | +0,279 ± 0,020, z 13,8 | **sí** |
| 2. \|K_eff − K_true\| | 1,11 | **0,25** | C − P = +0,866 ± 0,097, z 9,0 | **sí** |
| 3. K_true = 1 (n = 25): K_eff = 1 | 0,72 | 0,80 | +0,08 ± 0,10, z 0,8 | **no** |

Secundarias: DER (collar 0,25 s, con solapamientos) P 8,4 % frente a C 20,4 %; JER 29,2 % frente a 66,7 %.

**Comprobación previa a la adopción, AMI fresh3 (40 reuniones; protocolo de `exp028_secondary.py`):**
ARI C 0,728 → P 0,975 (+0,247 ± 0,044, z 5,7). No inferior (y superior). Referencia: la caché da
0,728 frente a 0,731 de EXP-028 (x-vectors recalculados entonces; caché en float16).

**Lectura pre-declarada:** 1 y 2 se cumplen y AMI es no inferior → P cumple las condiciones para
reemplazar a C como identidad (V#) en los perfiles film y meeting. 3 no se cumple → el "un solo
hablante" sigue abierto; no se mide docmix/domix y el perfil documentary no cambia.

**Límite principal (declarado en el pre-registro):** VoxConverse y AMI están en el entrenamiento de
pyannote; la magnitud de la ventaja puede estar inflada. La única evidencia fuera de su entrenamiento
es Spider-Man (exploratoria, sin GT): P separa voces que C juntaba por tipo de voz (V1 = Mary Jane +
Jean Grey + Aunt May + Sara Grey; V2 = Yelena + Det. Jean Wolff; V6b = Bill Metzger + Bruce Banner),
cada una alineada con un rostro distinto en pantalla y en labios (`spider_compare.json`).

**Adopción:** no aplicada todavía. `tfm-v1.0` y los estímulos de EXP-041-L quedan congelados con C;
la integración de P en `topicagg` queda pendiente de decisión.
