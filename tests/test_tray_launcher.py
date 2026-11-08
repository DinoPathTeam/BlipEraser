"""Al cerrar la app principal la bandeja queda en segundo plano."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtCore")

from PyQt6.QtCore import QProcess  # noqa: E402

from blip_eraser.tray import launcher  # noqa: E402


@pytest.fixture(autouse=True)
def _tmp_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "lock_path", lambda: str(tmp_path / "tray.lock"))
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
    lock = launcher.TrayLock()
    assert lock.try_lock(0)  # simula la bandeja activa
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


def _fake_flatpak(tmp_path, monkeypatch):
    import blip_eraser.utils.host_cmd as host_cmd

    info = tmp_path / "flatpak-info"
    info.write_text("x")
    monkeypatch.setattr(host_cmd, "FLATPAK_INFO", info)


def test_inside_flatpak_the_tray_starts_as_an_independent_host_instance(spawned, tmp_path, monkeypatch):
    _fake_flatpak(tmp_path, monkeypatch)
    assert launcher.ensure_tray_running({}) is True
    prog, args = spawned[0]
    assert prog == "flatpak-spawn"
    assert args == [
        "--host", "setsid", "-f", "flatpak", "run",
        "--command=blip-eraser-tray", "io.github.DinoPathTeam.BlipEraser",
    ]  # fmt: skip


def test_inside_flatpak_it_respects_the_users_choice(spawned, tmp_path, monkeypatch):
    _fake_flatpak(tmp_path, monkeypatch)
    assert launcher.ensure_tray_running({launcher.PREF_KEEP_RUNNING: False}) is False
    assert spawned == []


def test_inside_flatpak_the_lock_is_shared_between_instances(tmp_path, monkeypatch):
    _fake_flatpak(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.undo()  # quita el lock_path de prueba del fixture autouse
    _fake_flatpak(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    expected = tmp_path / "app" / "io.github.DinoPathTeam.BlipEraser" / launcher.LOCK_NAME
    assert launcher.lock_path() == str(expected)


def test_lock_is_exclusive_and_released(tmp_path):
    a, b = launcher.TrayLock(), launcher.TrayLock()
    assert a.try_lock(0)
    assert not b.try_lock(0)
    a.unlock()
    assert b.try_lock(0)
    b.unlock()


def test_failed_launch_reports_false(monkeypatch):
    monkeypatch.setattr(QProcess, "startDetached", staticmethod(lambda *a: False))
    assert launcher.ensure_tray_running({}) is False
