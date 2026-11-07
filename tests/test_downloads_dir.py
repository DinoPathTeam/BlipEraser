"""La carpeta Descargas se resuelve por XDG, no por el idioma."""

from blip_eraser.utils import file_utils
from blip_eraser.utils.file_utils import default_scan_paths, xdg_downloads_path


def _dirs(tmp_path, text):
    f = tmp_path / "user-dirs.dirs"
    f.write_text(text, encoding="utf-8")
    return f


def test_spanish_locale(tmp_path):
    f = _dirs(tmp_path, 'XDG_DOWNLOAD_DIR="$HOME/Descargas"\n')
    assert xdg_downloads_path(f) == "~/Descargas"


def test_english_locale(tmp_path):
    f = _dirs(tmp_path, 'XDG_DESKTOP_DIR="$HOME/Desktop"\nXDG_DOWNLOAD_DIR="$HOME/Downloads"\n')
    assert xdg_downloads_path(f) == "~/Downloads"


def test_absolute_path_kept(tmp_path):
    f = _dirs(tmp_path, 'XDG_DOWNLOAD_DIR="/mnt/data/Dl"\n')
    assert xdg_downloads_path(f) == "/mnt/data/Dl"


def test_comments_and_garbage_ignored(tmp_path):
    f = _dirs(tmp_path, '# XDG_DOWNLOAD_DIR="$HOME/Nope"\nbasura\nXDG_DOWNLOAD_DIR="$HOME/Bajadas"\n')
    assert xdg_downloads_path(f) == "~/Bajadas"


def test_missing_file_falls_back(tmp_path):
    assert xdg_downloads_path(tmp_path / "nope") == "~/Downloads"


def test_unsafe_values_fall_back(tmp_path):
    # $HOME/.. o rutas relativas no se aceptan como carpeta de escaneo
    for bad in ('"$HOME/../etc"', '"relativa"', '""', '"$HOME"'):
        f = _dirs(tmp_path, f"XDG_DOWNLOAD_DIR={bad}\n")
        assert xdg_downloads_path(f) == "~/Downloads", bad


def test_default_scan_paths_use_resolved_downloads(monkeypatch):
    monkeypatch.setattr(file_utils, "xdg_downloads_path", lambda *a, **k: "~/Bajadas")
    assert default_scan_paths() == ("~/Games", "~/Bajadas", "~/Applications")


def test_config_default_matches_file_utils():
    from blip_eraser.utils.config import PREFS_DEFAULTS
    assert tuple(PREFS_DEFAULTS["scan_paths"]) == file_utils.DEFAULT_SCAN_PATHS
