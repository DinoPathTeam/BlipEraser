"""Punto de entrada de BlipEraser.

Flujo:
  1. Nivel 1 (dependency_check): si falta PyQt6 se avisa por consola y
     se sale con código distinto de cero, porque sin PyQt6 no hay GUI.
     Por eso el import de PyQt6 se hace AQUÍ, una vez verificado.
  2. Idioma: si no hay preferencia guardada, el primer arranque pregunta
     (Español / English); si el usuario cierra sin elegir, se detecta del
     sistema. El resultado se guarda con set_language() ANTES de construir
     cualquier widget, para que todo se genere ya en el idioma correcto.
  3. Splash (widgets.splash_screen): logo + mensajes de progreso que
     StartupWorker (QThread) va emitiendo mientras prepara el arranque
     (actualizaciones, permisos, dependencias y un escaneo de referencia).
  4. Al terminar el worker se construye la ventana principal
     (renderer.MainWindow), se muestra y se cierra el splash. El aviso de
     binarios faltantes y el diálogo de permisos se muestran igual que
     antes, con los resultados calculados durante el splash (sin duplicar
     el trabajo).
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


def _warn_missing_dependencies(window, lines: list[str]) -> None:
    """Aviso de binarios faltantes, ya calculados durante el splash."""
    if not lines:
        return
    from PyQt6.QtWidgets import QMessageBox

    QMessageBox.warning(
        window,
        tr("missing_deps_title"),
        tr("missing_deps_intro").format(lines="\n\n".join(lines)),
    )


def main() -> int:
    """Entry point. Devuelve el código de salida de la app."""
    if not check_pyqt6_available():
        print(PYQT6_MISSING_MESSAGE, file=sys.stderr)
        return EXIT_PYQT6_MISSING

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer

    app = QApplication(sys.argv)

    saved = load_saved_language()
    if should_ask_for_language(saved):
        set_language(resolve_initial_language(_prompt_initial_language()))
    else:
        set_language(saved)

    from blip_eraser.renderer import MainWindow
    from blip_eraser.widgets.permissions_dialog import show_permissions_dialog
    from blip_eraser.widgets.splash_screen import SplashScreen, StartupWorker

    splash = SplashScreen()
    splash.show()

    worker = StartupWorker()
    cancel_requested = {"value": False}

    def _on_splash_closed() -> None:
        # El usuario cerró el splash a mitad: se pide al worker parar en el
        # siguiente paso y se sale limpiamente cuando termine.
        cancel_requested["value"] = True
        worker.requestInterruption()

    def _on_worker_finished() -> None:
        if cancel_requested["value"]:
            app.quit()
            return

        window = MainWindow()
        window.show()
        # Ocultar (no cerrar) el splash: hide() no dispara closeEvent, así
        # que `closed` solo se emite cuando el USUARIO lo cierra a mitad, no
        # en el cierre programático del camino de éxito.
        splash.hide()

        # Refresco completo de apariencia tras el primer pintado: los iconos
        # del sidebar (QIcon.fromTheme) y la fuente configurada pueden no
        # resolverse si se aplican antes de que el QIconLoader esté listo.
        QTimer.singleShot(0, window.refresh_appearance)

        # Aviso de binarios faltantes, calculado durante el splash (no se
        # duplica el chequeo). Se muestra tras el primer pintado.
        if worker.missing_lines:
            QTimer.singleShot(
                0, lambda: _warn_missing_dependencies(window, worker.missing_lines)
            )

        # Aviso único de "Permisos de BlipEraser": solo la primera ejecución.
        if worker.show_permissions_notice:
            QTimer.singleShot(0, lambda: show_permissions_dialog(window))

    splash.closed.connect(_on_splash_closed)
    worker.message.connect(splash.set_message)
    worker.finished.connect(_on_worker_finished)
    worker.start()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())