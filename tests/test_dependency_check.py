"""Tests para la verificación de dependencias (Nivel 1 y 2).

Se mockea shutil.which y importlib.import_module igual que test_pacman.py
mockea subprocess.run: no se necesita PyQt6 ni Arch/Linux reales.
"""

import shutil

import pytest

from blip_eraser.utils.dependency_check import (
    BINARY_DEPENDENCIES,
    Dependency,
    PYQT6_MISSING_MESSAGE,
    REQUIRED_BINARIES,
    check_binary_available,
    check_pyqt6_available,
    find_missing_dependencies,
    missing_binary_banner,
)
from blip_eraser.utils import dependency_check as dc


class TestCheckPyQt6Available:
    def test_present_returns_true(self, monkeypatch):
        def fake_import(name):
            return object()

        monkeypatch.setattr(dc.importlib, "import_module", fake_import)
        assert check_pyqt6_available() is True

    def test_absent_returns_false_without_raising(self, monkeypatch):
        def fake_import(name):
            raise ImportError(name)

        monkeypatch.setattr(dc.importlib, "import_module", fake_import)
        assert check_pyqt6_available() is False

    def test_message_suggests_pacman_install(self):
        assert "python-pyqt6" in PYQT6_MISSING_MESSAGE
        assert "sudo pacman -S" in PYQT6_MISSING_MESSAGE


class TestCheckBinaryAvailable:
    def test_found(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
        assert check_binary_available("pacman") is True

    def test_missing(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert check_binary_available("pkexec") is False


class TestFindMissingDependencies:
    def test_all_present_no_warnings(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
        assert find_missing_dependencies() == []

    def test_only_missing_are_reported(self, monkeypatch):
        def fake_which(name):
            return None if name == "pkexec" else f"/usr/bin/{name}"

        monkeypatch.setattr(shutil, "which", fake_which)

        missing = find_missing_dependencies()
        assert [dep.binary for dep in missing] == ["pkexec"]

    def test_missing_pkexec_payload(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None if name == "pkexec" else "/usr/bin/x")

        missing = find_missing_dependencies()
        assert missing[0].binary == "pkexec"
        assert missing[0].install_command == "sudo pacman -S polkit"

    def test_required_binaries_are_defined(self):
        assert {"pacman", "pkexec"} == set(BINARY_DEPENDENCIES)
        assert all(dep.binary in BINARY_DEPENDENCIES for dep in REQUIRED_BINARIES)


class TestDependencyRemediation:
    def test_pacman_is_system_incompatibility_not_command(self):
        pacman = BINARY_DEPENDENCIES["pacman"]
        assert pacman.install_command is None
        assert pacman.incompatible_system_message

    def test_pacman_message_explains_no_arch_and_manual_scan_keeps_working(self):
        pacman = BINARY_DEPENDENCIES["pacman"]
        message = pacman.incompatible_system_message or ""
        assert "basadas en Arch" in message
        assert "escaneo manual" in message
        assert pacman.remediation_suffix() == message

    def test_pkexec_still_uses_install_command(self):
        pkexec = BINARY_DEPENDENCIES["pkexec"]
        assert pkexec.install_command == "sudo pacman -S polkit"
        assert pkexec.incompatible_system_message is None
        assert pkexec.remediation_suffix() == "Instala con: sudo pacman -S polkit"

    def test_fallback_when_no_remediation_defined(self):
        dep = Dependency(binary="ghost", why="no se sabe")
        assert dep.remediation_suffix() == "No hay remedio automático disponible."


class TestMissingBinaryBanner:
    def test_none_missing_empty(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/x")
        assert missing_binary_banner(["pacman", "pkexec"]) == ""

    def test_unknown_binary_no_line(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        assert missing_binary_banner(["no-existe"]) == ""

    def test_missing_pkexec_suggests_command(self, monkeypatch):
        def fake_which(name):
            return None if name == "pkexec" else "/usr/bin/x"

        monkeypatch.setattr(shutil, "which", fake_which)

        banner = missing_binary_banner(["pacman", "pkexec"])
        assert "pkexec no encontrado" in banner
        assert "sudo pacman -S polkit" in banner
        assert "pacman no encontrado" not in banner

    def test_missing_pacman_uses_incompatibility_message(self, monkeypatch):
        def fake_which(name):
            return None if name == "pacman" else "/usr/bin/x"

        monkeypatch.setattr(shutil, "which", fake_which)

        banner = missing_binary_banner(["pacman"])
        assert "pacman no encontrado" in banner
        # No debe sugerir usar pacman para instalar pacman (circular).
        assert "sudo pacman -S pacman" not in banner
        # Debe explicar que el sistema no es compatible y que el escaneo manual sigue activo.
        assert "basadas en Arch" in banner
        assert "escaneo manual" in banner

    def test_both_missing_lists_both(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        banner = missing_binary_banner(["pacman", "pkexec"])
        assert banner.count("no encontrado") == 2