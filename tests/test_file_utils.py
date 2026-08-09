"""Tests para la lógica pura de escaneo y tamaños (sin PyQt6 ni pacman)."""

from pathlib import Path

import pytest

from blip_eraser.utils.file_utils import (
    DEFAULT_SCAN_PATHS,
    delete_path,
    get_dir_size,
    human_size,
    path_size_for_display,
    scan_manual_entries,
)


class TestHumanSize:
    def test_bytes(self):
        assert human_size(512) == "512.0 B"

    def test_kilobytes(self):
        assert human_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert human_size(5 * 1024**2) == "5.0 MB"

    def test_gigabytes(self):
        assert human_size(3 * 1024**3) == "3.0 GB"

    def test_zero(self):
        assert human_size(0) == "0.0 B"


class TestGetDirSize:
    def test_empty_dir(self, tmp_path):
        assert get_dir_size(tmp_path) == 0

    def test_nested_files(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"x" * 100)
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_bytes(b"y" * 50)
        assert get_dir_size(tmp_path) == 150

    def test_nonexistent_dir(self, tmp_path):
        assert get_dir_size(tmp_path / "missing") == 0


class TestScanManualEntries:
    def test_finds_dirs_and_appimages(self, tmp_path):
        base = tmp_path / "scan"
        (base / "MyApp").mkdir(parents=True)
        (base / "HydraLauncher").mkdir()
        (base / "notes.txt").write_text("no es un candidato")
        appimage = base / "Some.AppImage"
        appimage.write_bytes(b"x")

        result = scan_manual_entries([str(base)])
        names = {p.name for p in result}
        assert "MyApp" in names
        assert "HydraLauncher" in names
        assert "Some.AppImage" in names
        assert "notes.txt" not in names

    def test_ignores_system_names(self, tmp_path):
        base = tmp_path / "scan"
        (base / "applications").mkdir(parents=True)
        (base / "icons").mkdir()
        (base / "mime").mkdir()
        (base / "RealApp").mkdir()
        result = scan_manual_entries([str(base)])
        assert {p.name for p in result} == {"RealApp"}

    def test_case_insensitive_ignore(self, tmp_path):
        base = tmp_path / "scan"
        (base / "Applications").mkdir(parents=True)
        (base / "Game").mkdir()
        result = scan_manual_entries([str(base)])
        assert {p.name for p in result} == {"Game"}

    def test_skips_missing_base(self, tmp_path):
        result = scan_manual_entries([str(tmp_path / "no-existe")])
        assert result == []

    def test_multiple_bases(self, tmp_path):
        p1 = tmp_path / "one"
        p2 = tmp_path / "two"
        (p1 / "AppA").mkdir(parents=True)
        (p2 / "AppB").mkdir(parents=True)
        result = scan_manual_entries([str(p1), str(p2)])
        assert {p.name for p in result} == {"AppA", "AppB"}

    def test_default_paths_include_home(self):
        assert "~/.local/share" in tuple(DEFAULT_SCAN_PATHS)


class TestPathSizeForDisplay:
    def test_dir_sums(self, tmp_path):
        (tmp_path / "f.txt").write_bytes(b"z" * 42)
        assert path_size_for_display(tmp_path) == 42

    def test_file_reports_stat(self, tmp_path):
        f = tmp_path / "app.bin"
        f.write_bytes(b"q" * 10)
        assert path_size_for_display(f) == 10

    def test_missing(self, tmp_path):
        assert path_size_for_display(tmp_path / "no-existe") == 0


class TestDeletePath:
    def test_removes_file(self, tmp_path):
        f = tmp_path / "a.txt"
        f.write_text("hi")
        delete_path(f)
        assert not f.exists()

    def test_removes_directory_tree(self, tmp_path):
        d = tmp_path / "app"
        d.mkdir()
        (d / "inner").mkdir()
        (d / "inner" / "f.bin").write_bytes(b"x")
        delete_path(d)
        assert not d.exists()

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(OSError):
            delete_path(tmp_path / "missing")