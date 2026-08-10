"""Tests para utils/apps.py (apps instaladas y salud, sin PyQt6)."""

from pathlib import Path

from blip_eraser.utils import apps


class TestListInstalledApps:
    def test_combines_pacman_and_manual(self, monkeypatch):
        monkeypatch.setattr(
            apps,
            "list_explicit_packages",
            lambda: [("firefox", "1.0"), ("spotify", "2.0")],
        )
        monkeypatch.setattr(
            apps,
            "scan_manual_entries",
            lambda paths, ignore: [Path("/x/MyApp.AppImage"), Path("/x/LooseFolder")],
        )
        monkeypatch.setattr(apps, "get_scan_paths", lambda: ["/x"])

        result = apps.list_installed_apps()
        names = [a.name for a in result]
        assert names == ["firefox", "spotify", "MyApp.AppImage", "LooseFolder"]
        assert result[0].source == "pacman"
        assert result[2].source == "manual"

    def test_manual_duplicates_are_skipped(self, monkeypatch):
        monkeypatch.setattr(
            apps,
            "list_explicit_packages",
            lambda: [("firefox", "1.0")],
        )
        monkeypatch.setattr(
            apps,
            "scan_manual_entries",
            lambda paths, ignore: [Path("/x/Firefox")],  # mismo nombre en minúsculas
        )
        monkeypatch.setattr(apps, "get_scan_paths", lambda: ["/x"])

        result = apps.list_installed_apps()
        assert len(result) == 1
        assert result[0].source == "pacman"

    def test_pacman_missing_only_manual(self, monkeypatch):
        monkeypatch.setattr(
            apps, "list_explicit_packages", lambda: (_ for _ in ()).throw(FileNotFoundError())
        )
        monkeypatch.setattr(
            apps,
            "scan_manual_entries",
            lambda paths, ignore: [Path("/x/OnlyMe.AppImage")],
        )
        monkeypatch.setattr(apps, "get_scan_paths", lambda: ["/x"])

        result = apps.list_installed_apps()
        assert [a.name for a in result] == ["OnlyMe.AppImage"]
        assert result[0].source == "manual"

    def test_pacman_error_does_not_raise(self, monkeypatch):
        monkeypatch.setattr(
            apps, "list_explicit_packages", lambda: (_ for _ in ()).throw(OSError())
        )
        monkeypatch.setattr(apps, "scan_manual_entries", lambda paths, ignore: [])
        monkeypatch.setattr(apps, "get_scan_paths", lambda: ["/x"])
        assert apps.list_installed_apps() == []

    def test_manual_scan_respects_custom_ignore(self, monkeypatch, tmp_path):
        base = tmp_path / "scan"
        (base / "keep").mkdir(parents=True)
        (base / "junk").mkdir()
        monkeypatch.setattr(apps, "list_explicit_packages", lambda: [])
        monkeypatch.setattr(apps, "get_scan_paths", lambda: [str(base)])
        monkeypatch.setattr(apps, "get_scan_ignore", lambda: ["junk"])

        result = apps.list_installed_apps()
        assert [a.name for a in result] == ["keep"]


class TestHealthScore:
    def test_all_three_sources(self):
        assert apps.health_score(20, 30, 40) == 100 - 30

    def test_partial_sources(self):
        assert apps.health_score(10, None, 30) == 100 - 20
        assert apps.health_score(None, None, 80) == 20

    def test_no_sources_returns_none(self):
        assert apps.health_score(None, None, None) is None

    def test_clamped_to_range(self):
        assert 0 <= apps.health_score(100, 100, 100) <= 100
        assert apps.health_score(0, 0, 0) == 100
        assert apps.health_score(100, None, None) == 0