"""Tests para utils/scan.py (escaneo y tamaños de pacman, sin PyQt6)."""

import pytest

from blip_eraser.utils import scan


class TestOrphanPackages:
    def test_returns_names_only(self, monkeypatch):
        monkeypatch.setattr(
            scan,
            "_run",
            lambda cmd, timeout=8: "orphan-pkg 1.0-1\nother-pkg 2.0-1\n",
        )
        assert scan.orphan_packages() == ["orphan-pkg", "other-pkg"]

    def test_empty_output_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8: "")
        assert scan.orphan_packages() == []

    def test_ignores_blank_lines(self, monkeypatch):
        monkeypatch.setattr(
            scan,
            "_run",
            lambda cmd, timeout=8: "pkg-a 1.0\n\n\npkg-b 2.0\n",
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
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8: output)

        info = scan.pacman_installed_info()
        assert info["firefox"]["size"] == int(round(543.21 * 1024**2))
        assert "11 Jun 2024" in info["firefox"]["date"]
        assert info["libfoo"]["size"] == 10 * 1024**2
        assert "12 Jun 2024" in info["libfoo"]["date"]

    def test_missing_fields_default_to_zero_empty(self, monkeypatch):
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8: "Name : pkg\n")
        assert scan.pacman_installed_info() == {"pkg": {"size": 0, "date": ""}}

    def test_empty_output_returns_empty_dict(self, monkeypatch):
        monkeypatch.setattr(scan, "_run", lambda cmd, timeout=8: "")
        assert scan.pacman_installed_info() == {}

    def test_sizes_wraps_info(self, monkeypatch):
        info = {"a": {"size": 10, "date": "x"}, "b": {"size": 20, "date": ""}}
        monkeypatch.setattr(scan, "pacman_installed_info", lambda: info)
        assert scan.pacman_installed_sizes() == {"a": 10, "b": 20}