"""Tests para utils/permissions.py — aviso único de permisos (settings.json).

Reaprovecha el redireccionamiento de i18n.SETTINGS_FILE a tmp_path para no
tocar la configuración real del usuario.
"""

from blip_eraser.utils import i18n, permissions
from blip_eraser.utils.i18n import set_language
from blip_eraser.utils.permissions import (
    mark_permissions_notice_shown,
    should_show_permissions_notice,
)


def _read_settings() -> dict:
    import json

    return json.loads(i18n.SETTINGS_FILE.read_text(encoding="utf-8"))


class TestPermissionsNoticeFlag:
    def test_shows_when_file_absent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(i18n, "SETTINGS_FILE", tmp_path / "s.json")
        assert should_show_permissions_notice() is True

    def test_shows_when_key_missing(self, tmp_path, monkeypatch):
        f = tmp_path / "s.json"
        f.write_text('{"other": 1}', encoding="utf-8")
        monkeypatch.setattr(i18n, "SETTINGS_FILE", f)
        assert should_show_permissions_notice() is True

    def test_hidden_after_mark(self, tmp_path, monkeypatch):
        f = tmp_path / "s.json"
        monkeypatch.setattr(i18n, "SETTINGS_FILE", f)
        assert should_show_permissions_notice() is True
        mark_permissions_notice_shown()
        assert should_show_permissions_notice() is False

    def test_persists_json_key(self, tmp_path, monkeypatch):
        f = tmp_path / "s.json"
        monkeypatch.setattr(i18n, "SETTINGS_FILE", f)
        mark_permissions_notice_shown()
        data = _read_settings()
        assert data["permissions_notice_shown"] is True

    def test_preserves_language_key(self, tmp_path, monkeypatch):
        f = tmp_path / "s.json"
        monkeypatch.setattr(i18n, "SETTINGS_FILE", f)
        set_language("es")
        mark_permissions_notice_shown()
        data = _read_settings()
        assert data["language"] == "es"
        assert data["permissions_notice_shown"] is True

    def test_set_language_does_not_erase_flag(self, tmp_path, monkeypatch):
        f = tmp_path / "s.json"
        monkeypatch.setattr(i18n, "SETTINGS_FILE", f)
        mark_permissions_notice_shown()
        set_language("en")
        assert should_show_permissions_notice() is False

    def test_corrupt_file_shows_notice(self, tmp_path, monkeypatch):
        f = tmp_path / "s.json"
        f.write_text("no-json", encoding="utf-8")
        monkeypatch.setattr(i18n, "SETTINGS_FILE", f)
        assert should_show_permissions_notice() is True