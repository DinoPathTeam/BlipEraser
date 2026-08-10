"""Tests para la lógica de pacman/pkexec (subprocess mockeado, sin pacman real)."""

import subprocess

import pytest

from blip_eraser.utils import pacman


class FakeResult:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestListExplicitPackages:
    def test_parses_output(self, monkeypatch):
        output = "firefox 130.0-1\nkitty  0.36.4-1\n\nvim 9.1.0000-1\n"
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
            assert kwargs["check"] is True
            return FakeResult(stdout=output)

        monkeypatch.setattr(pacman.subprocess, "run", fake_run)

        assert pacman.list_explicit_packages() == [
            ("firefox", "130.0-1"),
            ("kitty", "0.36.4-1"),
            ("vim", "9.1.0000-1"),
        ]
        assert calls == [["pacman", "-Qe"]]

    def test_version_optional(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            return FakeResult(stdout="foo\nbar 1.0\n")

        monkeypatch.setattr(pacman.subprocess, "run", fake_run)
        assert pacman.list_explicit_packages() == [("foo", ""), ("bar", "1.0")]

    def test_raises_on_failure(self, monkeypatch):
        def boom(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)

        monkeypatch.setattr(pacman.subprocess, "run", boom)
        with pytest.raises(subprocess.CalledProcessError):
            pacman.list_explicit_packages()


class TestListDependencyPackages:
    def test_uses_Qd_flag(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return FakeResult(stdout="libfoo 1.2-1\ndefault-lib 3.0-1\n")

        monkeypatch.setattr(pacman.subprocess, "run", fake_run)

        assert pacman.list_dependency_packages() == [
            ("libfoo", "1.2-1"),
            ("default-lib", "3.0-1"),
        ]
        assert calls == [["pacman", "-Qd"]]


class TestUninstallPackages:
    def test_builds_command_with_noconfirm(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return FakeResult(stdout="ok")

        monkeypatch.setattr(pacman.subprocess, "run", fake_run)

        pacman.uninstall_packages(["firefox", "vim"])
        cmd, kwargs = calls[0]
        assert cmd == ["pkexec", "pacman", "-Rns", "--noconfirm", "firefox", "vim"]
        assert kwargs == {"capture_output": True, "text": True, "check": True}

    def test_without_noconfirm(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return FakeResult()

        monkeypatch.setattr(pacman.subprocess, "run", fake_run)
        pacman.uninstall_packages(["x"], noconfirm=False)
        assert calls[0] == ["pkexec", "pacman", "-Rns", "x"]

    def test_propagates_errors(self, monkeypatch):
        def boom(cmd, **kwargs):
            raise subprocess.CalledProcessError(126, cmd)

        monkeypatch.setattr(pacman.subprocess, "run", boom)
        with pytest.raises(subprocess.CalledProcessError):
            pacman.uninstall_packages(["sudo"])