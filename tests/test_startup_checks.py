"""Comprobaciones de arranque: reales, fuera del hilo de la interfaz y sin duplicar.

Antes, `main()` ejecutaba las comprobaciones del daemon de forma síncrona
ANTES del splash (hasta 6 subprocesos de 5 s, con cada comando repetido), y
el StartupWorker emitía pasos decorativos en inglés sin calcular nada.
"""

from __future__ import annotations

import inspect
import subprocess
from unittest.mock import MagicMock

import pytest

from blip_eraser.utils import dependency_check as dc


@pytest.fixture(autouse=True)
def _fresh_cache():
    dc.invalidate_daemon_deps_cache()
    yield
    dc.invalidate_daemon_deps_cache()


# ─── Dependencias del daemon: una sola ejecución por comando ──────────────

def test_identical_check_commands_run_once(monkeypatch):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    assert dc.check_daemon_dependencies() == []
    assert len(calls) == len(dc.DAEMON_DEPENDENCIES)  # antes: el doble


def test_distinct_active_command_still_runs(monkeypatch):
    dep = dc.DaemonDependency(
        name="x", check_cmd="true", install_cmd="", check_active_cmd="systemctl is-active x"
    )
    monkeypatch.setattr(dc, "DAEMON_DEPENDENCIES", (dep,))
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return MagicMock(returncode=0 if len(calls) == 1 else 3)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    assert dc.check_daemon_dependencies() == [dep]  # instalado pero inactivo
    assert len(calls) == 2


def test_timeout_counts_as_missing(monkeypatch):
    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 5)

    monkeypatch.setattr(dc.subprocess, "run", fake_run)
    assert len(dc.check_daemon_dependencies()) == len(dc.DAEMON_DEPENDENCIES)


def test_gst_libav_is_not_a_daemon_dependency():
    names = " ".join(d.name.lower() for d in dc.DAEMON_DEPENDENCIES)
    assert "gst" not in names and "libav" not in names
    assert "gobject" in names and "dbus" in names


# ─── main(): nada bloqueante antes del splash ─────────────────────────────

def test_main_does_no_daemon_check_before_the_splash():
    from blip_eraser import main as main_mod

    src = inspect.getsource(main_mod.main)
    splash = src.index("SplashScreen()")
    for needle in ("check_daemon_dependencies", "_offer_daemon_deps"):
        idx = src.find(needle)
        assert idx == -1 or idx > splash, f"{needle} corre antes del splash"
    assert not hasattr(main_mod, "_check_and_install_daemon_deps")


def test_offer_daemon_deps_with_nothing_missing_is_a_noop():
    from blip_eraser.main import _offer_daemon_deps

    assert _offer_daemon_deps(None, []) == (False, [])


def test_offer_daemon_deps_declined_installs_nothing(monkeypatch):
    pytest.importorskip("PyQt6.QtWidgets")
    import PyQt6.QtWidgets as qtw

    import blip_eraser.utils.phase2_installer as p2
    from blip_eraser.main import _offer_daemon_deps

    class FakeBox:
        class Icon:
            Question = 0

        class ButtonRole:
            AcceptRole = 0
            RejectRole = 1

        def __init__(self, *a, **k):
            self._yes = object()

        def setWindowTitle(self, *_): ...
        def setText(self, *_): ...
        def setIcon(self, *_): ...

        def addButton(self, label, role):
            return self._yes if label == tr("daemon_deps_install") else object()

        def exec(self): ...

        def clickedButton(self):
            return object()  # ni "Instalar" ni nada conocido

    installed = []
    monkeypatch.setattr(qtw, "QMessageBox", FakeBox)
    monkeypatch.setattr(p2, "install_daemon_dependency", lambda d: installed.append(d) or (True, ""))
    dep = dc.DAEMON_DEPENDENCIES[0]
    assert _offer_daemon_deps(None, [dep]) == (False, [])
    assert installed == []


# ─── StartupWorker: pasos reales y traducidos ─────────────────────────────

pytest.importorskip("PyQt6.QtWidgets")

from blip_eraser.utils.i18n import set_language, tr  # noqa: E402
from blip_eraser.widgets import splash_screen as ss  # noqa: E402


def _run_worker(monkeypatch, missing_lines=None, daemon_missing=None, boom=False):
    monkeypatch.setattr(
        ss, "localized_missing_lines", (lambda names: (_ for _ in ()).throw(RuntimeError("x"))) if boom else (lambda names: missing_lines or [])
    )
    monkeypatch.setattr(
        ss, "check_daemon_dependencies", lambda: daemon_missing or []
    )
    worker = ss.StartupWorker()
    messages: list[str] = []
    worker.message.connect(messages.append)
    worker.run()  # síncrono: sin hilo real en el test
    return worker, messages


def test_worker_messages_are_translated_and_match_real_steps(monkeypatch):
    for lang in ("es", "en"):
        set_language(lang)
        _, messages = _run_worker(monkeypatch)
        assert messages == [tr("splash_check_dependencies"), tr("splash_check_daemon")]
    set_language("es")


def test_worker_reports_missing_binaries_and_daemon_deps(monkeypatch):
    dep = dc.DAEMON_DEPENDENCIES[0]
    worker, _ = _run_worker(monkeypatch, missing_lines=["• pkexec: falta"], daemon_missing=[dep])
    assert worker.missing_lines == ["• pkexec: falta"]
    assert worker.missing_daemon_deps == [dep]


def test_worker_survives_a_failing_check(monkeypatch):
    worker, messages = _run_worker(monkeypatch, boom=True)
    assert worker.missing_lines == []
    assert len(messages) == 2  # el arranque continúa


def test_worker_has_no_artificial_delay():
    src = inspect.getsource(ss.StartupWorker.run)
    assert "msleep" not in src
