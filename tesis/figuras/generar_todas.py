"""Regenera todas las figuras de la tesis en images/generadas/.

Uso (desde la raíz del repositorio, con el extra [figs] instalado):
    python tesis/figuras/generar_todas.py
Los íconos y las ilustraciones se generan aparte con generar_imagenes.sh (Codex).
"""
import fig_flujo
import fig_mecanismo
import fig_resultados

if __name__ == "__main__":
    fig_flujo.main()
    fig_mecanismo.main()
    fig_resultados.main()
