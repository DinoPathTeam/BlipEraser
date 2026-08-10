"""Tests para utils/scan.py (escaneo y tamaños de pacman, sin PyQt6)."""

import pytest

from blip_eraser.utils import scan


class TestOrphanPackages:
    def test_returns_names_only(self, monkeypatch):
        monkeypatch.setattr(
            scan,
            "_run",
            lambda cmd, timeout=8, env=None: "orphan-pkg 1.0-1\nother-pkg 2.0-1\n",
        )
        assert scan.orphan_packages() == ["orphan-pkg", "other-pkg"]

    def test_empty_output_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8, env=None: "")
        assert scan.orphan_packages() == []

    def test_ignores_blank_lines(self, monkeypatch):
        monkeypatch.setattr(
            scan,
            "_run",
            lambda cmd, timeout=8, env=None: "pkg-a 1.0\n\n\npkg-b 2.0\n",
        )
        assert scan.orphan_packages() == ["pkg-a", "pkg-b"]


class TestParsePacmanSize:
    def test_bytes(self):
        assert scan.parse_pacman_size("Installed Size : 512 B") == 512

    def test_kib(self):
        assert scan.parse_pacman_size("Installed Size : 2.00 KiB") == 2 * 1024

    def test_mib(self):
        assert scan.parse_pacman_size("Installed Size : 543.21 MiB") == int(
            round(543.21 * 1024**2)
        )

    def test_gib(self):
        assert scan.parse_pacman_size("Installed Size : 1.5 GiB") == int(
            round(1.5 * 1024**3)
        )

    def test_tib(self):
        assert scan.parse_pacman_size("Installed Size : 1 TiB") == 1024**4

    def test_lowercase_unit(self):
        assert scan.parse_pacman_size("Installed Size : 3 kib") == 3 * 1024

    def test_no_match_returns_none(self):
        assert scan.parse_pacman_size("nonsense") is None

    def test_unknown_unit_returns_none(self):
        assert scan.parse_pacman_size("Installed Size : 10 XYZ") is None

    def test_empty_returns_none(self):
        assert scan.parse_pacman_size("") is None


class TestPacmanInstalledInfo:
    def test_parses_size_and_date_per_package(self, monkeypatch):
        output = (
            "Name            : firefox\n"
            "Version         : 130.0-1\n"
            "Install Date    : Tue 11 Jun 2024 08:15:00 AM UTC\n"
            "Installed Size  : 543.21 MiB\n"
            "\n"
            "Name            : libfoo\n"
            "Version         : 1.2-1\n"
            "Install Date    : Wed 12 Jun 2024 10:00:00 AM UTC\n"
            "Installed Size  : 10.00 MiB\n"
        )
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8, env=None: output)

        info = scan.pacman_installed_info()
        assert info["firefox"]["size"] == int(round(543.21 * 1024**2))
        assert info["firefox"]["date"] == "2024-06-11"
        assert info["libfoo"]["size"] == 10 * 1024**2
        assert info["libfoo"]["date"] == "2024-06-12"

    def test_missing_fields_default_to_zero_empty(self, monkeypatch):
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8, env=None: "Name : pkg\n")
        assert scan.pacman_installed_info() == {"pkg": {"size": 0, "date": ""}}

    def test_empty_output_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8, env=None: "")
        assert scan.pacman_installed_info() == {}

    def test_sizes_wraps_info(self, monkeypatch):
        info = {"a": {"size": 10, "date": "x"}, "b": {"size": 20, "date": ""}}
        monkeypatch.setattr(scan, "pacman_installed_info", lambda: info)
        assert scan.pacman_installed_sizes() == {"a": 10, "b": 20}

    def test_forces_c_locale_env(self, monkeypatch):
        captured = {}

        def fake_run(cmd, timeout=8, env=None):
            captured["env"] = env
            return ""

        monkeypatch.setattr(scan, "_run", fake_run)
        scan.pacman_installed_info()
        assert captured["env"]["LANG"] == "C"
        assert captured["env"]["LC_ALL"] == "C"


class TestNormalizePacmanDate:
    def test_english_c_locale_format_am(self):
        assert (
            scan.normalize_pacman_date("Tue 11 Jun 2024 08:15:00 AM UTC")
            == "2024-06-11"
        )

    def test_english_c_locale_format_pm(self):
        assert (
            scan.normalize_pacman_date("Wed 12 Jun 2024 10:00:00 PM UTC")
            == "2024-06-12"
        )

    def test_unparseable_falls_back_to_raw(self):
        raw = "lun 11 jun 2024 08:15:00 a. m. UTC"
        assert scan.normalize_pacman_date(raw) == raw

    def test_garbage_falls_back_to_raw(self):
        raw = "not a date at all"
        assert scan.normalize_pacman_date(raw) == raw

    def test_empty_stays_empty(self):
        assert scan.normalize_pacman_date("") == ""