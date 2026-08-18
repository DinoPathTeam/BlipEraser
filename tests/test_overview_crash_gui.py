"""Tests GUI del fix del crash al cerrar la app durante un escaneo.

Regresión de CachyOS: `RuntimeError: wrapped C/C++ object of type
QVBoxLayout has been deleted` al llegar el resultado de un escaneo después
de que la ventana/página ya fue destruida en C++ (cierre de app con hilo
daemon vivo). El hilo mantiene viva la referencia al bound method de la
página, así que el wrapper Python sobrevive, pero Qt ya eliminó el layout
y sus widgets; tocar cualquiera de ellos lanza RuntimeError.

Verificaciones:
  - Resultado de escaneo que llega tras destruir la página: se descarta en
    silencio (BackgroundScanMixin._widget_is_alive), sin RuntimeError.
  - Control positivo: widget vivo + token correcto -> sí procesa.
  - Control negativo: widget vivo + token obsoleto -> descarta.
  - El panel de log se des-suscribe del buffer global al destruirse, para
    que un `log_buffer.add()` posterior no notifique a un widget muerto.

Requieren PyQt6; se reportan como *skipped* en entornos sin él.
"""

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets")
QtCore = pytest.importorskip("PyQt6.QtCore")

from pathlib import Path

from PyQt6 import sip

import blip_eraser.pages.overview_page as overview_mod
import blip_eraser.utils.log as log_mod


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance


@pytest.fixture(scope="module")
def prefs_tmp(tmp_path_factory):
    import blip_eraser.utils.config as config_mod

    prefs_file = tmp_path_factory.mktemp("prefs") / "prefs.json"
    config_mod.PREFS_FILE = prefs_file
    return prefs_file


_CLEANUP = {
    "junk_bytes": 1024,
    "pacman_cache_bytes": 2048,
    "logs_bytes": 512,
    "orphan_count": 3,
}


def _destroy_in_cpp(app, page):
    """Destruye el QObject C++ subyacente de la página.

    `deleteLater()` encola DeferredDelete; hay que forzar el envío para que
    el C++ desaparezca de verdad (sip.isdeleted -> True), igual que ocurre
    al cerrar la app en producción.
    """
    page.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    assert sip.isdeleted(page)


class TestOverviewScanResultAfterWidgetDeath:
    def _page(self, app, monkeypatch):
        """OverviewPage sin SCAN NOW inicial (evita threads de fondo)."""
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        page._apps = []
        return page

    def test_result_arriving_after_destroy_is_discarded(self, app, prefs_tmp, monkeypatch):
        """Resultado que llega tras destruir la página: descarte silencioso.

        Simula el bug de CachyOS: un escaneo termina (o el usuario cierra la
        app) cuando la página ya no existe en C++ -> el mixin lo descarta sin
        tocar widgets, y NO se lanza RuntimeError.
        """
        page = self._page(app, monkeypatch)
        page._scan_token = 1
        page._scanning = True
        page._scan_on_result = page._on_scan_done
        for btn in page._scan_buttons:
            btn.setEnabled(False)

        calls = {"on_result": 0}
        page._scan_on_result = lambda result: calls.__setitem__(
            "on_result", calls["on_result"] + 1
        )

        _destroy_in_cpp(app, page)

        # Entrega el resultado del "hilo" al slot del mixin.
        page._on_scan_result_ready((1, {"apps": [], "cleanup": dict(_CLEANUP)}))
        assert calls["on_result"] == 0

    def test_failed_after_destroy_is_discarded(self, app, prefs_tmp, monkeypatch):
        """Worker que falla tras destruir la página tampoco revienta."""
        page = self._page(app, monkeypatch)
        page._scan_token = 2
        page._scanning = True
        _destroy_in_cpp(app, page)

        page._on_scan_failed("boom")
        # Sin RuntimeError: la guarda de vida del mixin lo descartó.

    def test_live_widget_positive_control(self, app, prefs_tmp, monkeypatch):
        """Widget vivo + token correcto -> el resultado sí se procesa."""
        page = self._page(app, monkeypatch)
        page._scan_token = 7
        page._scanning = True
        calls = {"on_result": 0}
        page._scan_on_result = lambda result: calls.__setitem__(
            "on_result", calls["on_result"] + 1
        )
        for btn in page._scan_buttons:
            btn.setEnabled(False)

        page._on_scan_result_ready((7, {"apps": [], "cleanup": dict(_CLEANUP)}))
        assert calls["on_result"] == 1
        assert page._scanning is False
        assert all(btn.isEnabled() for btn in page._scan_buttons)

    def test_stale_token_ignored_when_alive(self, app, prefs_tmp, monkeypatch):
        """Widget vivo pero token obsoleto -> descarta sin tocar botones."""
        page = self._page(app, monkeypatch)
        page._scan_token = 9
        page._scanning = True
        calls = {"on_result": 0}
        page._scan_on_result = lambda result: calls.__setitem__(
            "on_result", calls["on_result"] + 1
        )

        page._on_scan_result_ready((8, "obsoleto"))
        assert calls["on_result"] == 0
        assert page._scanning is True  # el escaneo nuevo sigue en curso


class TestLogListenerUnsubscribesOnDeath:
    def test_notify_after_overview_destroy_does_not_crash(self, app, prefs_tmp, monkeypatch):
        """Un add() posterior al log no notifica a la página muerta (su guard
        la descarta), así que nunca lanza RuntimeError por widgets borrados."""
        monkeypatch.setattr(overview_mod.OverviewPage, "_scan", lambda self: None)
        page = overview_mod.OverviewPage()
        _destroy_in_cpp(app, page)

        # El guard interno (_widget_is_alive) descarta la notificación.
        log_mod.log.add("prueba tras destruccion")
        # Sin RuntimeError.

    def test_notify_after_log_panel_destroy_does_not_crash(self, app, prefs_tmp):
        from blip_eraser.widgets.log_panel import LogPanel

        panel = LogPanel()
        _destroy_in_cpp(app, panel)
        log_mod.log.add("prueba panel muerto")
        # Sin RuntimeError.

    def test_buffer_discards_dead_listener(self, app, prefs_tmp):
        """Red genérica: un listener que falla con RuntimeError se quita del
        buffer y no bloquea a los demás (cubre cualquier widget sin guard)."""
        buffer = log_mod.LogBuffer()
        dead = {"calls": 0}
        alive = {"calls": 0}

        def dead_listener(entries):
            dead["calls"] += 1
            if dead["calls"] > 1:
                # Fallo solo en notificaciones posteriores (subscribe() llama
                # al listener de inmediato, y eso no debe contar como fallo).
                raise RuntimeError("wrapped C/C++ object has been deleted")

        def alive_listener(entries):
            alive["calls"] += 1

        buffer.subscribe(dead_listener)
        buffer.subscribe(alive_listener)
        buffer.add("x")

        assert dead["calls"] == 2  # 1 de subscribe + 1 de add
        assert alive["calls"] == 2  # subscribe + add: los demás sí reciben
        assert dead_listener not in buffer._listeners  # el muerto se descarta
        assert alive_listener in buffer._listeners

        buffer.add("y")
        assert alive["calls"] == 3  # sigue notificando
        assert dead["calls"] == 2  # el muerto ya no se llama