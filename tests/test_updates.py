"""Tests de utils/updates.py — lógica pura, sin PyQt6 y sin red real.

`check_for_updates()` sí usa la red en producción, así que aquí se
intercepta `urlopen` con respuestas falsas. Ningún test toca la red.
"""

import io
import json

from blip_eraser.utils import updates
from blip_eraser.utils.updates import UpdateCheckResult, check_for_updates


def _fake_response(tag):
    payload = json.dumps({"tag_name": tag}).encode()
    resp = io.BytesIO(payload)
    resp.__enter__ = lambda s: s
    resp.__exit__ = lambda s, *a: False
    return resp


def test_check_for_updates_returns_no_update(monkeypatch):
    monkeypatch.setattr(updates, "urlopen", lambda *a, **k: _fake_response("v1.0.0"))
    result = check_for_updates(current_version="1.0.0")
    assert isinstance(result, UpdateCheckResult)
    assert result.has_update is False
    assert result.latest_version is None


def test_check_for_updates_frozen_dataclass_defaults():
    assert UpdateCheckResult(has_update=False, latest_version=None) == UpdateCheckResult(
        has_update=False
    )


def test_check_for_updates_detects_newer_release(monkeypatch):
    monkeypatch.setattr(updates, "urlopen", lambda *a, **k: _fake_response("v1.2.0"))
    result = check_for_updates(current_version="1.0.0")
    assert result == UpdateCheckResult(has_update=True, latest_version="1.2.0")


def test_check_for_updates_network_error_is_fail_closed(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr(updates, "urlopen", boom)
    result = check_for_updates(current_version="1.0.0")
    assert result.has_update is False
