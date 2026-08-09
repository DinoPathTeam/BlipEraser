"""Punto de entrada de BlipEraser.

Flujo:
  1. Nivel 1 (dependency_check): si falta PyQt6 se avisa por consola y
     se sale con código distinto de cero, porque sin PyQt6 no hay GUI.
     Por eso el import de PyQt6 se hace AQUÍ, una vez verificado.
  2. Idioma: si no hay preferencia guardada, el primer arranque pregunta
     (Español / English); si el usuario cierra sin elegir, se detecta del
     sistema. El resultado se guarda con set_language() ANTES de construir
     cualquier widget, para que todo se genere ya en el idioma correcto.
  3. Ventana principal: menú "Idioma" para cambiar en caliente
     (retranslate) y aviso en segundo plano si faltan binarios externos.
"""

import sys

from blip_eraser.utils.dependency_check import (
    PYQT6_MISSING_MESSAGE,
    check_pyqt6_available,
)
from blip_eraser.utils.i18n import (
    SUPPORTED_LANGUAGES,
    get_current_language,
    load_saved_language,
    set_language,
    tr,
)
from blip_eraser.utils.ui_text import (
    localized_missing_lines,
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


def _build_main_window_class():
    """Importa PyQt6 (ya verificado) y define la ventana principal."""
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QAction, QActionGroup
    from PyQt6.QtWidgets import QMainWindow, QMenu, QMessageBox, QTabWidget

    from blip_eraser.tabs import ManualScanTab, PacmanTab

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.resize(700, 500)

            self.tabs = QTabWidget()
            self.tabs.addTab(PacmanTab(), tr("tab_packages"))
            self.tabs.addTab(ManualScanTab(), tr("tab_manual_scan"))
            self.setCentralWidget(self.tabs)

            self._language_actions: dict[str, QAction] = {}
            self._build_language_menu()
            self.retranslate()

            # Nivel 2: se agenda tras arrancar el event loop, así no
            # bloquea la creación de la ventana ni el resto de pestañas.
            QTimer.singleShot(0, self._warn_missing_binaries)

        def _build_language_menu(self):
            group = QActionGroup(self)
            group.setExclusive(True)
            for code in SUPPORTED_LANGUAGES:
                action = QAction(tr(f"lang_name_{code}"), self)
                action.setCheckable(True)
                action.setChecked(code == get_current_language())
                action.triggered.connect(
                    lambda _checked=False, lang=code: self._switch_language(lang)
                )
                group.addAction(action)
                self._language_actions[code] = action

            self.language_menu = QMenu(tr("menu_label"), self)
            for action in self._language_actions.values():
                self.language_menu.addAction(action)
            self.menuBar().addMenu(self.language_menu)

        def _switch_language(self, code: str):
            set_language(code)
            for lang, action in self._language_actions.items():
                action.setChecked(lang == code)
            self.retranslate()

        def retranslate(self):
            """Refresca todo el texto estático sin reiniciar la app."""
            self.setWindowTitle(tr("window_title"))
            self.language_menu.setTitle(tr("menu_label"))
            self.tabs.setTabText(0, tr("tab_packages"))
            self.tabs.setTabText(1, tr("tab_manual_scan"))
            for i in range(self.tabs.count()):
                widget = self.tabs.widget(i)
                if hasattr(widget, "retranslate"):
                    widget.retranslate()

        def _warn_missing_binaries(self):
            """Avisa (sin instalar nada) si falta algún binario externo."""
            lines = localized_missing_lines(["pacman", "pkexec"])
            if not lines:
                return
            QMessageBox.warning(
                self,
                tr("missing_deps_title"),
                tr("missing_deps_intro").format(lines="\n\n".join(lines)),
            )

    return MainWindow


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

    MainWindow = _build_main_window_class()
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())