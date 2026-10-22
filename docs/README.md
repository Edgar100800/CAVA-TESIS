# docs/ — política

Esta carpeta contiene **únicamente lo necesario para implementar y operar CAVA**:

| Archivo | Rol |
|---|---|
| `integration-cava.md` | Diseño de integración SegLoop+VJudge ▸ analizador (contrato, fases A–E) |
| `granularity-plan.md` | Plan activo: afinado de granularidad temática (quant+qual) |
| `progress.md` | Estado por módulo (implementado / validado), contenido y anotaciones disponibles, stack a congelar para el A/B |

**No va aquí:**

- Reportes de avance, presentaciones o HTMLs (viven en los repos de origen).
- ADRs históricos y bitácoras de campaña (viven en `~/Tesis/SegLoop/docs/`).
- Copias de lectura de otros repos — se referencian por ruta, no se duplican.

**Regla:** un doc entra a esta carpeta solo si alguien lo consultaría para
construir o correr el sistema. Todo lo demás es archivo histórico y queda en
su repo de origen.
