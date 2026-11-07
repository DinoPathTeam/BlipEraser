"""Al cerrar la app principal la bandeja queda en segundo plano."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtCore")

from PyQt6.QtCore import QLockFile, QProcess  # noqa: E402

from blip_eraser.tray import launcher  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "lock_path", lambda: str(tmp_path / "tray.lock"))
    monkeypatch.setattr(launcher, "FLATPAK_INFO", None, raising=False)
    import blip_eraser.utils.host_cmd as host_cmd

    monkeypatch.setattr(host_cmd, "FLATPAK_INFO", tmp_path / "no-flatpak-info")


@pytest.fixture()
def spawned(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        QProcess, "startDetached", staticmethod(lambda prog, args: calls.append((prog, args)) or True)
    )
    return calls


def test_keep_running_is_on_by_default_and_can_be_disabled():
    assert launcher.keep_running_enabled({})
    assert launcher.keep_running_enabled({launcher.PREF_KEEP_RUNNING: True})
    assert not launcher.keep_running_enabled({launcher.PREF_KEEP_RUNNING: False})


def test_launches_the_tray_when_none_is_running(spawned):
    assert launcher.ensure_tray_running({}) is True
    assert spawned[0][1] == ["-m", "blip_eraser.tray"]


def test_does_not_launch_a_second_tray(spawned):
    lock = QLockFile(launcher.lock_path())
    assert lock.tryLock(0)  # simula la bandeja activa
    try:
        assert launcher.tray_is_running()
        assert launcher.ensure_tray_running({}) is False
        assert spawned == []
    finally:
        lock.unlock()
    assert not launcher.tray_is_running()


def test_respects_the_users_choice(spawned):
    assert launcher.ensure_tray_running({launcher.PREF_KEEP_RUNNING: False}) is False
    assert spawned == []


def test_never_inside_flatpak(spawned, tmp_path, monkeypatch):
    import blip_eraser.utils.host_cmd as host_cmd

    info = tmp_path / "flatpak-info"
    info.write_text("x")
    monkeypatch.setattr(host_cmd, "FLATPAK_INFO", info)
    assert launcher.ensure_tray_running({}) is False
    assert spawned == []


def test_failed_launch_reports_false(monkeypatch):
    monkeypatch.setattr(QProcess, "startDetached", staticmethod(lambda *a: False))
    assert launcher.ensure_tray_running({}) is False
