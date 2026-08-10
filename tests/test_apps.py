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


class TestAppKinds:
    def test_classifies_kinds_and_sizes(self, monkeypatch):
        monkeypatch.setattr(
            apps, "list_explicit_packages", lambda: [("firefox", "1.0")]
        )
        monkeypatch.setattr(
            apps, "list_dependency_packages", lambda: [("libfoo", "2.0")]
        )
        monkeypatch.setattr(
            apps,
            "scan_manual_entries",
            lambda paths, ignore: [Path("/x/MyApp.AppImage")],
        )
        monkeypatch.setattr(apps, "get_scan_paths", lambda: ["/x"])
        monkeypatch.setattr(
            apps,
            "pacman_installed_info",
            lambda: {
                "firefox": {"size": 1024, "date": "2024-01-01"},
                "libfoo": {"size": 2048, "date": "2024-02-02"},
            },
        )

        result = apps.list_installed_apps()
        by_name = {a.name: a for a in result}

        assert by_name["firefox"].kind == "app"
        assert by_name["firefox"].source == "pacman"
        assert by_name["firefox"].size_bytes == 1024
        assert by_name["firefox"].install_date == "2024-01-01"

        assert by_name["libfoo"].kind == "dependency"
        assert by_name["libfoo"].source == "pacman"
        assert by_name["libfoo"].size_bytes == 2048
        assert by_name["libfoo"].install_date == "2024-02-02"

        assert by_name["MyApp.AppImage"].kind == "folder"
        assert by_name["MyApp.AppImage"].source == "manual"

    def test_dependency_duplicate_with_explicit_skipped(self, monkeypatch):
        monkeypatch.setattr(
            apps, "list_explicit_packages", lambda: [("firefox", "1.0")]
        )
        monkeypatch.setattr(
            apps, "list_dependency_packages", lambda: [("Firefox", "2.0")]
        )
        monkeypatch.setattr(apps, "scan_manual_entries", lambda paths, ignore: [])
        monkeypatch.setattr(apps, "get_scan_paths", lambda: ["/x"])

        result = apps.list_installed_apps()
        assert len(result) == 1
        assert result[0].kind == "app"

    def test_kind_label_keys(self):
        assert apps.kind_label_key("app") == "kind_app"
        assert apps.kind_label_key("dependency") == "kind_dependency"
        assert apps.kind_label_key("folder") == "kind_folder"
        assert apps.kind_label_key("desconocido") == "kind_folder"


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