"""Tests para utils/config.py (preferencias persistentes, sin PyQt6)."""

import json

import pytest

from blip_eraser.utils import config


@pytest.fixture(autouse=True)
def isolated_prefs(tmp_path, monkeypatch):
    """Cada test usa su propio archivo de preferencias."""
    monkeypatch.setattr(config, "PREFS_FILE", tmp_path / "prefs.json")
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)


class TestLoadPrefs:
    def test_defaults_when_no_file(self):
        prefs = config.load_prefs()
        assert prefs["theme"] == "red"
        assert prefs["font"] == "system"
        assert isinstance(prefs["scan_paths"], list)
        assert prefs["scan_paths"]

    def test_merges_saved_over_defaults(self):
        config.save_prefs({"theme": "green", "scan_paths": ["/x"]})
        prefs = config.load_prefs()
        assert prefs["theme"] == "green"
        assert prefs["scan_paths"] == ["/x"]
        assert prefs["font"] == "system"  # el resto sigue siendo por defecto

    def test_corrupt_file_falls_back_to_defaults(self, tmp_path):
        config.PREFS_FILE.write_text("{not json", encoding="utf-8")
        assert config.load_prefs()["theme"] == "red"

    def test_non_dict_json_falls_back_to_defaults(self, tmp_path):
        config.PREFS_FILE.write_text("[1,2,3]", encoding="utf-8")
        assert config.load_prefs()["theme"] == "red"


class TestSavePrefs:
    def test_write_roundtrip(self):
        config.save_prefs({"theme": "green", "font": "montserrat"})
        data = json.loads(config.PREFS_FILE.read_text(encoding="utf-8"))
        assert data["theme"] == "green"
        assert data["font"] == "montserrat"

    def test_patch_merges_without_losing_keys(self):
        config.save_prefs({"theme": "red"})
        config.save_prefs({"font": "lato"})
        prefs = config.load_prefs()
        assert prefs["theme"] == "red"
        assert prefs["font"] == "lato"

    def test_save_error_does_not_raise(self, monkeypatch, tmp_path):
        class FailingFile:
            parent = tmp_path

            def read_text(self, *a, **k):
                raise FileNotFoundError

            def write_text(self, *a, **k):
                raise OSError("disco lleno")

        monkeypatch.setattr(config, "PREFS_FILE", FailingFile())
        config.save_prefs({"theme": "purple"})  # no debe lanzar


class TestScanPaths:
    def test_get_returns_defaults(self):
        assert config.get_scan_paths() == config.PREFS_DEFAULTS["scan_paths"]

    def test_set_and_get(self):
        config.set_scan_paths(["/a", "/b"])
        assert config.get_scan_paths() == ["/a", "/b"]

    def test_set_returns_list_copy(self):
        config.set_scan_paths(["/a"])
        result = config.get_scan_paths()
        result.append("mutado")
        assert config.get_scan_paths() == ["/a"]


class TestScanIgnore:
    def test_get_returns_defaults(self):
        assert config.get_scan_ignore() == config.PREFS_DEFAULTS["scan_ignore"]

    def test_set_and_get(self):
        config.set_scan_ignore(["cache", "tmp"])
        assert config.get_scan_ignore() == ["cache", "tmp"]

    def test_set_returns_list_copy(self):
        config.set_scan_ignore(["cache"])
        result = config.get_scan_ignore()
        result.append("mutado")
        assert config.get_scan_ignore() == ["cache"]