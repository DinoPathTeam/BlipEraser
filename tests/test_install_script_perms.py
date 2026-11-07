"""El instalador del daemon no debe dejar código escribible por terceros.

El daemon corre como root desde /usr/lib/blip-eraser: si el repo de origen
tuviera permisos laxos o symlinks, el despliegue heredaría un vector de
escalada. Se ejecuta el script real en modo DESTDIR (sin tocar el sistema).
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None, reason="requiere bash"
)


def _clone_repo(dst: Path) -> Path:
    for name in ("scripts", "src", "packaging"):
        shutil.copytree(
            REPO / name,
            dst / name,
            ignore=shutil.ignore_patterns("__pycache__", "assets"),
        )
    return dst


def _run(repo: Path, dest: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, DESTDIR=str(dest))
    return subprocess.run(
        ["bash", str(repo / "scripts" / "install-daemon.sh")],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        # umask 0: el peor caso (root con umask laxa); el script no debe
        # depender del umask del invocador.
        preexec_fn=lambda: os.umask(0),
    )


def _loose(path: Path) -> list[str]:
    bad = []
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            p = Path(root) / name
            if p.is_symlink():
                bad.append(f"symlink: {p}")
                continue
            if p.stat().st_mode & (stat.S_IWGRP | stat.S_IWOTH):
                bad.append(f"writable: {p}")
    return bad


def test_loose_source_modes_are_normalised(tmp_path: Path):
    repo = _clone_repo(tmp_path / "repo")
    victim = repo / "src" / "blip_eraser" / "utils" / "validation.py"
    victim.chmod(0o666)
    (repo / "src" / "blip_eraser" / "utils").chmod(0o777)
    dest = tmp_path / "dest"
    r = _run(repo, dest)
    assert r.returncode == 0, r.stderr + r.stdout
    libdir = dest / "usr" / "lib" / "blip-eraser"
    assert libdir.is_dir()
    assert _loose(libdir) == []
    entry = libdir / "blip-eraser-privileged"
    assert stat.S_IMODE(entry.stat().st_mode) == 0o755
    assert stat.S_IMODE((libdir / "blip_eraser").stat().st_mode) == 0o755


def test_symlinks_in_source_are_rejected(tmp_path: Path):
    repo = _clone_repo(tmp_path / "repo")
    outside = tmp_path / "evil.py"
    outside.write_text("print('pwned')\n")
    (repo / "src" / "blip_eraser" / "evil.py").symlink_to(outside)
    dest = tmp_path / "dest"
    r = _run(repo, dest)
    assert r.returncode != 0
    assert "symlink" in (r.stderr + r.stdout).lower()
