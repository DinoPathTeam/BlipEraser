"""Punto de entrada de BlipEraser.

Flujo:
  1. Nivel 1 (dependency_check): si falta PyQt6 se avisa por consola y
     se sale con código distinto de cero, porque sin PyQt6 no hay GUI.
     Por eso el import de PyQt6 se hace AQUÍ, una vez verificado.
  2. Idioma: si no hay preferencia guardada, el primer arranque pregunta
     (Español / English); si el usuario cierra sin elegir, se detecta del
     sistema. El resultado se guarda con set_language() ANTES de construir
     cualquier widget, para que todo se genere ya en el idioma correcto.
  3. Ventana principal (renderer.MainWindow): menú "Idioma" para cambiar
     en caliente (retranslate) y aviso en segundo plano si faltan binarios.
"""

import sys

from blip_eraser.utils.dependency_check import (
    PYQT6_MISSING_MESSAGE,
    check_pyqt6_available,
)
from blip_eraser.utils.i18n import (
    load_saved_language,
    set_language,
    tr,
)
from blip_eraser.utils.ui_text import (
    resolve_initial_language,
    should_ask_for_language,
)

EXIT_PYQT6_MISSING = 2

__all__ = ["main"]


def _prompt_initial_language() -> str | None:
    """Diálogo de primer arranque con dos botones directos.

    Devuelve "es"/"en" según el botón pulsado, o None si el usuario
    cierra el diálogo sin elegir (la X).
    """
    from PyQt6.QtWidgets import QMessageBox

    box = QMessageBox()
    box.setWindowTitle(tr("language_first_run_title"))
    box.setText(tr("language_first_run_text"))
    es_button = box.addButton(
        tr("lang_name_es"), QMessageBox.ButtonRole.AcceptRole
    )
    en_button = box.addButton(
        tr("lang_name_en"), QMessageBox.ButtonRole.AcceptRole
    )
    box.exec()

    clicked = box.clickedButton()
    if clicked is es_button:
        return "es"
    if clicked is en_button:
        return "en"
    return None


def main() -> int:
    """Entry point. Devuelve el código de salida de la app."""
    if not check_pyqt6_available():
        print(PYQT6_MISSING_MESSAGE, file=sys.stderr)
        return EXIT_PYQT6_MISSING

    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    saved = load_saved_language()
    if should_ask_for_language(saved):
        set_language(resolve_initial_language(_prompt_initial_language()))
    else:
        set_language(saved)

    from blip_eraser.renderer import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())