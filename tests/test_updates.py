"""Tests de utils/updates.py — lógica pura, sin PyQt6 y sin red.

El stub de check_for_updates() no debe tocar la red ni el sistema, y debe
devolver siempre "sin actualización" para que el splash avance de forma
determinista.
"""

import socket

from blip_eraser.utils.updates import UpdateCheckResult, check_for_updates


def test_check_for_updates_returns_no_update():
    result = check_for_updates()
    assert isinstance(result, UpdateCheckResult)
    assert result.has_update is False
    assert result.latest_version is None


def test_check_for_updates_frozen_dataclass_defaults():
    assert UpdateCheckResult(has_update=False, latest_version=None) == UpdateCheckResult(
        has_update=False
    )


def test_check_for_updates_makes_no_network_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("check_for_updates() no debe usar la red")

    monkeypatch.setattr(socket, "socket", forbidden)
    result = check_for_updates()
    assert result.has_update is False