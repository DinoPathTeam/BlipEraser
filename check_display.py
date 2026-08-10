"""
Diagnóstico de pantalla para BlipEraser.

Uso:
    python check_display.py

Requiere PyQt6 instalado (el mismo que usa BlipEraser).
No modifica nada, no requiere permisos: solo lee la geometría
que el sistema operativo ya le reporta a cualquier aplicación Qt.
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt


def main() -> int:
    app = QApplication(sys.argv)

    screens = app.screens()
    if not screens:
        print("No se detectó ninguna pantalla (¿estás en un entorno sin display?).")
        return 1

    print(f"Pantallas detectadas: {len(screens)}\n")

    for i, screen in enumerate(screens):
        geometry = screen.geometry()
        avail = screen.availableGeometry()
        dpi = screen.logicalDotsPerInch()
        physical_dpi = screen.physicalDotsPerInch()
        ratio = screen.devicePixelRatio()
        refresh = screen.refreshRate()
        name = screen.name()

        print(f"--- Pantalla {i} ({name}) ---")
        print(f"  Resolución (lógica):   {geometry.width()} x {geometry.height()}")
        print(f"  Área disponible:       {avail.width()} x {avail.height()} (sin barras/paneles)")
        print(f"  DPI lógico:            {dpi:.1f}")
        print(f"  DPI físico:            {physical_dpi:.1f}")
        print(f"  Factor de escala:      {ratio}x")
        print(f"  Tasa de refresco:      {refresh:.1f} Hz")
        print()

        if ratio != 1.0:
            print(f"  -> Este monitor usa escalado ({ratio}x). "
                  f"Si algo se ve mal, es la pista principal.\n")
        else:
            print(f"  -> Escala 1:1 (100%), no debería haber problemas de tamaño.\n")

    primary = app.primaryScreen()
    print(f"Pantalla primaria: {primary.name()}")
    print(f"AA_EnableHighDpiScaling activo por defecto en Qt6: sí (siempre encendido, no es opcional)")

    return 0


if __name__ == "__main__":
    sys.exit(main())