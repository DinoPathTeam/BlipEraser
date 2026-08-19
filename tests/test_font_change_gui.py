"""Tests GUI del cambio de fuente en caliente desde Ajustes.

Regresión: cambiar la fuente en Ajustes con la app abierta (señal
font_changed) no aplicaba el cambio — el texto seguía con la fuente
anterior. La causa: _apply_appearance repulía con app.style() en vez de
widget.style(), dejando la caché de fuente resuelta por la QSS intacta.

Estos tests cubren la cadena real: SettingsPage.font_changed -> 
renderer._on_font_changed -> save_prefs -> _apply_appearance, verificando
tanto QApplication.font().family() como la fuente efectiva de widgets.
Requieren PyQt6; se reportan como *skipped* en entornos sin él y corren
en CachyOS.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtGui = pytest.importorskip("PyQt6.QtGui")


@pytest.fixture(scope="module", autouse=True)
def diag_redirect(tmp_path_factory):
    """Mantiene la bitácora forense fuera de la ruta real durante los tests."""
    import blip_eraser.utils.log as log_mod

    original = log_mod.DIAG_LOG_PATH
    log_mod.DIAG_LOG_PATH = tmp_path_factory.mktemp("diag") / "diagnostics.log"
    yield
    log_mod.DIAG_LOG_PATH = original


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


_KEEP_ALIVE: list = []


def _wait_scans_done(app, window, timeout_ms=15000):
    """Bombea el event loop hasta que los escaneos de fondo terminen.

    Overview/Desinstalador/Limpiador lanzan hilos daemon al construirse. Si
    la ventana (y sus hilos) sobrevive al módulo, un hilo aún vivo puede
    seguir llamando funciones reales (p. ej. scan_cleanup) e interferir con
    los monkeypatch de módulos de test posteriores. Esperamos a que todas
    las páginas dejen de escanear antes de devolver el control.
    """
    import time

    pages = list(window._pages.values())
    sections = []
    for p in pages:
        if hasattr(p, "recommended"):
            sections.append(p.recommended)
        if hasattr(p, "manual"):
            sections.append(p.manual)

    def scanning() -> bool:
        for obj in pages + sections:
            if getattr(obj, "_scanning", False):
                return True
        return False

    deadline = time.monotonic() + timeout_ms / 1000
    while scanning() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()


@pytest.fixture(scope="module")
def window(app, tmp_path_factory):
    """MainWindow completa con prefs redirigidos a un tmp.

    El scope es de módulo (una sola ventana para todos los tests) y se
    mantiene una referencia fuerte a nivel de módulo (_KEEP_ALIVE) para que
    la ventana NO se recoja con el GC mientras las páginas de
    Overview/Desinstalador/Limpiador siguen ejecutando sus escaneos en
    segundo plano: destruir la ventana (y con ella los _ScanBridge) mientras
    esos hilos emiten provocaba un crash (exit 0xC0000409).

    Antes de devolver el control esperamos a que esos escaneos terminen
    (_wait_scans_done), para que ningún hilo siga vivo cuando corran otros
    módulos de test. El log es un singleton global y OverviewPage se
    suscribe a él sin darse de baja nunca; para que la suscripción de ESTA
    ventana no notifique a módulos de test posteriores (cuyos widgets ya no
    existen), se limpia la lista de listeners justo después de construirla.
    """
    import blip_eraser.utils.config as config_mod
    from blip_eraser.renderer import MainWindow
    from blip_eraser.utils.log import log as log_buffer

    prefs_file = tmp_path_factory.mktemp("prefs") / "prefs.json"
    config_mod.PREFS_FILE = prefs_file
    w = MainWindow()
    w.show()
    app.processEvents()
    _wait_scans_done(app, w)
    log_buffer._listeners.clear()
    _KEEP_ALIVE.append(w)
    return w


class TestFontChangeViaSignal:
    def test_font_changed_signal_applies_to_app_font(self, app, window):
        """Cambiar la fuente vía la señal font_changed actualiza
        QApplication.font().family()."""
        settings = window._tools.settings
        combo = settings.font_combo

        combo.setCurrentIndex(
            next(i for i in range(combo.count()) if combo.itemData(i) == "roboto")
        )
        app.processEvents()

        assert app.font().family() == "Roboto"

    def test_font_changed_signal_applies_to_widgets(self, app, window):
        """La fuente efectiva de un widget de una página (visible u oculta)
        refleja el cambio — no solo app.font()."""
        from PyQt6.QtWidgets import QLabel

        settings = window._tools.settings
        combo = settings.font_combo

        combo.setCurrentIndex(
            next(i for i in range(combo.count()) if combo.itemData(i) == "roboto")
        )
        app.processEvents()

        for key, page in window._pages.items():
            label = page.findChild(QLabel)
            assert label is not None, f"página {key} sin QLabel"
            assert label.font().family() == "Roboto", (
                f"página {key}: widget sin la fuente nueva "
                f"(label={label.font().family()!r}, app={app.font().family()!r})"
            )

    def test_second_font_change_follows(self, app, window):
        """Un segundo cambio seguido también se aplica (la caché de la QSS
        no puede quedar con la fuente anterior)."""
        settings = window._tools.settings
        combo = settings.font_combo

        combo.setCurrentIndex(
            next(i for i in range(combo.count()) if combo.itemData(i) == "roboto")
        )
        app.processEvents()
        assert app.font().family() == "Roboto"

        combo.setCurrentIndex(
            next(i for i in range(combo.count()) if combo.itemData(i) == "lato")
        )
        app.processEvents()
        assert app.font().family() == "Lato"

    def test_font_change_persisted_to_prefs(self, app, window):
        """_on_font_changed persiste el nuevo font en prefs.json."""
        import json

        import blip_eraser.utils.config as config_mod

        settings = window._tools.settings
        combo = settings.font_combo

        combo.setCurrentIndex(
            next(i for i in range(combo.count()) if combo.itemData(i) == "montserrat")
        )
        app.processEvents()

        prefs = json.loads(config_mod.PREFS_FILE.read_text(encoding="utf-8"))
        assert prefs["font"] == "montserrat"