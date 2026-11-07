"""Tests de utils/updates.py — lógica pura, sin PyQt6 y sin red real.

`check_for_updates()` sí usa la red en producción, así que aquí se
intercepta `urlopen` con respuestas falsas. Ningún test toca la red.
"""

import io
import json

import pytest

from blip_eraser.utils import config, updates
from blip_eraser.utils.updates import UpdateCheckResult, check_for_updates


@pytest.fixture(autouse=True)
def _isolated_prefs(monkeypatch, tmp_path):
    """La caché de 24 h vive en prefs.json: nunca el del usuario real."""
    monkeypatch.setattr(config, "PREFS_FILE", tmp_path / "prefs.json")


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



# ─── Caché de 24 h ────────────────────────────────────────────────────────

class _Net:
    """urlopen falso que cuenta las llamadas."""

    def __init__(self, tag="v1.2.0", fail=False):
        self.tag, self.fail, self.calls = tag, fail, 0

    def __call__(self, *a, **k):
        self.calls += 1
        if self.fail:
            raise OSError("sin red")
        return _fake_response(self.tag)


def test_second_check_within_24h_uses_cache_without_network(monkeypatch):
    net = _Net("v1.2.0")
    monkeypatch.setattr(updates, "urlopen", net)
    first = check_for_updates(current_version="1.0.0", now=1_000.0)
    second = check_for_updates(current_version="1.0.0", now=1_000.0 + 3600)
    assert first == second == UpdateCheckResult(True, "1.2.0")
    assert net.calls == 1


def test_check_after_24h_queries_again(monkeypatch):
    net = _Net("v1.2.0")
    monkeypatch.setattr(updates, "urlopen", net)
    check_for_updates(current_version="1.0.0", now=1_000.0)
    check_for_updates(current_version="1.0.0", now=1_000.0 + updates.CACHE_SECONDS + 1)
    assert net.calls == 2


def test_cache_with_no_update_is_also_remembered(monkeypatch):
    net = _Net("v1.0.0")
    monkeypatch.setattr(updates, "urlopen", net)
    check_for_updates(current_version="1.0.0", now=5.0)
    result = check_for_updates(current_version="1.0.0", now=10.0)
    assert result.has_update is False
    assert net.calls == 1


def test_cache_is_compared_with_the_current_version(monkeypatch):
    """Tras actualizar la app, el 'último' cacheado ya no es novedad."""
    net = _Net("v1.2.0")
    monkeypatch.setattr(updates, "urlopen", net)
    check_for_updates(current_version="1.0.0", now=1.0)
    result = check_for_updates(current_version="1.2.0", now=2.0)
    assert result.has_update is False
    assert net.calls == 1


def test_network_failure_is_not_cached_so_next_launch_retries(monkeypatch):
    net = _Net(fail=True)
    monkeypatch.setattr(updates, "urlopen", net)
    assert check_for_updates(current_version="1.0.0", now=1.0).has_update is False
    net.fail = False
    assert check_for_updates(current_version="1.0.0", now=2.0).has_update is True
    assert net.calls == 2


def test_clock_going_backwards_forces_a_refetch(monkeypatch):
    net = _Net("v1.2.0")
    monkeypatch.setattr(updates, "urlopen", net)
    check_for_updates(current_version="1.0.0", now=1_000_000.0)
    check_for_updates(current_version="1.0.0", now=10.0)  # reloj atrás
    assert net.calls == 2


def test_opt_out_pref_disables_all_network(monkeypatch):
    config.save_prefs({"check_updates": False})
    net = _Net("v9.9.9")
    monkeypatch.setattr(updates, "urlopen", net)
    assert check_for_updates(current_version="1.0.0", now=1.0).has_update is False
    assert net.calls == 0


def test_corrupt_cache_values_do_not_crash(monkeypatch):
    config.save_prefs({"update_checked_at": "ayer", "update_latest": 7})
    net = _Net("v1.2.0")
    monkeypatch.setattr(updates, "urlopen", net)
    assert check_for_updates(current_version="1.0.0", now=1.0).has_update is True
    assert net.calls == 1
