"""Tests de utils/host_cmd.py — lógica pura, sin Flatpak real.

Se simula el sandbox parcheando `is_flatpak` y `subprocess.run`:
ningún test necesita Flatpak instalado.
"""

import shutil
from pathlib import Path
from unittest.mock import MagicMock

from blip_eraser.utils import host_cmd
from blip_eraser.utils.host_cmd import expanduser, host_shell, host_which


def _sandbox(monkeypatch, home="/home/user"):
    monkeypatch.setattr(host_cmd, "is_flatpak", lambda: True)
    monkeypatch.setattr(host_cmd, "_host_home", home)


def test_host_cmd_passthrough_outside_flatpak(monkeypatch):
    monkeypatch.setattr(host_cmd, "is_flatpak", lambda: False)
    assert host_cmd.host_cmd(["pacman", "-Q"]) == ["pacman", "-Q"]


def test_host_cmd_prefixes_inside_flatpak(monkeypatch):
    _sandbox(monkeypatch)
    assert host_cmd.host_cmd(["pacman", "-Q"]) == [
        "flatpak-spawn", "--host", "pacman", "-Q",
    ]


def test_host_shell_passthrough_outside_flatpak(monkeypatch):
    monkeypatch.setattr(host_cmd, "is_flatpak", lambda: False)
    assert host_shell("a | b") == "a | b"


def test_host_shell_wraps_inside_flatpak(monkeypatch):
    _sandbox(monkeypatch)
    assert host_shell("a | b") == ["flatpak-spawn", "--host", "sh", "-c", "a | b"]


def test_host_which_passthrough_outside_flatpak(monkeypatch):
    monkeypatch.setattr(host_cmd, "is_flatpak", lambda: False)
    assert host_which("sh") == shutil.which("sh")


def test_host_which_queries_host_inside_flatpak(monkeypatch):
    _sandbox(monkeypatch)
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = "/usr/bin/pacman\n"
    monkeypatch.setattr(host_cmd.subprocess, "run", lambda *a, **k: fake)
    assert host_which("pacman") == "/usr/bin/pacman"


def test_expanduser_uses_host_home_inside_flatpak(monkeypatch):
    _sandbox(monkeypatch, home="/home/user")
    assert expanduser("~/Games") == Path("/home/user/Games")


def test_expanduser_passthrough_outside_flatpak(monkeypatch):
    monkeypatch.setattr(host_cmd, "is_flatpak", lambda: False)
    assert expanduser("~/Games") == Path("~/Games").expanduser()
