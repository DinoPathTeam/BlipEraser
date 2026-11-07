"""Apertura estricta de rutas en el daemon (sin seguir symlinks en NINGÚN tramo).

`O_NOFOLLOW` solo protege el último componente; un symlink intermedio
cambiado entre la validación y la apertura se seguiría. `_open_dir_nofollow`
recorre la ruta componente a componente con O_NOFOLLOW (equivalente a
openat2 + RESOLVE_NO_SYMLINKS, sin ctypes ni syscalls nuevas).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# El daemon importa gi al cargarse: se simula antes (igual que
# test_privileged_daemon.py). setdefault respeta un mock ya instalado.
for _mod in ("gi", "gi.repository", "gi.repository.GLib", "gi.repository.Gio"):
    sys.modules.setdefault(_mod, MagicMock())

import blip_eraser.daemon.privileged_daemon as d  # noqa: E402


@pytest.fixture(autouse=True)
def _root_at_tmp(monkeypatch, tmp_path):
    """La allowlist apunta a tmp_path (el prefijo real sería /var/log, etc.)."""
    monkeypatch.setattr(d, "_validate_path_str", lambda p: True)
    monkeypatch.setattr(d, "ALLOWED_SYSTEM_PREFIXES", (str(tmp_path),))


def test_opens_real_nested_directory(tmp_path: Path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    fd = d._open_dir_nofollow(tmp_path / "a" / "b")
    try:
        assert os.fstat(fd).st_ino == (tmp_path / "a" / "b").stat().st_ino
    finally:
        os.close(fd)


def test_intermediate_symlink_is_refused(tmp_path: Path):
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    with pytest.raises(OSError):
        d._open_dir_nofollow(tmp_path / "link" / "sub")


def test_final_symlink_is_refused(tmp_path: Path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(OSError):
        d._open_dir_nofollow(tmp_path / "link")


@pytest.mark.parametrize("bad", ["relativa/ruta", "{t}/../etc", "{t}/./x", "{t}//x", ""])
def test_non_canonical_paths_are_refused(bad: str, tmp_path: Path):
    with pytest.raises(OSError):
        d._open_dir_nofollow(Path(bad.format(t=tmp_path)) if bad else Path(""))


def test_path_outside_allowlist_is_refused(tmp_path: Path):
    other = tmp_path.parent
    with pytest.raises(OSError):
        d._open_dir_nofollow(other)


def test_allowlist_prefix_itself_can_be_opened(tmp_path: Path):
    fd = d._open_dir_nofollow(tmp_path)
    os.close(fd)


def test_longest_prefix_wins(monkeypatch, tmp_path: Path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    monkeypatch.setattr(
        d, "ALLOWED_SYSTEM_PREFIXES", (str(tmp_path), str(tmp_path / "a"))
    )
    fd = d._open_dir_nofollow(tmp_path / "a" / "b")
    os.close(fd)


def test_rm_refuses_path_through_intermediate_symlink(tmp_path: Path):
    real = tmp_path / "real"
    (real / "sub").mkdir(parents=True)
    victim = real / "sub" / "victima.txt"
    victim.write_text("no tocar")
    (tmp_path / "link").symlink_to(real, target_is_directory=True)
    ok, err = d._rm_rf_atomic(tmp_path / "link" / "sub" / "victima.txt")
    assert not ok
    assert victim.read_text() == "no tocar"
