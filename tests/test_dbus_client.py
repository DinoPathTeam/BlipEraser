"""Tests para utils/dbus_client.py — cliente D-Bus con fallback pkexec.

Sin daemon real: mockeamos la conexión D-Bus y subprocess.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blip_eraser.utils.dbus_client import (
    DBusError,
    DaemonUnavailable,
    ValidationFailed,
    ExecutionFailed,
    CommandNotFound,
    PrivilegedClient,
    PrivilegedAPI,
    OperationResult,
    get_privileged_api,
    reset_privileged_api,
    _run_pkexec_rm,
    _run_pkexec_pacman,
    _validate_path_pkexec,
    _reject_symlinks_pkexec,
)


class TestValidatePathPkexec:
    def test_allows_allowed_prefixes(self):
        assert _validate_path_pkexec(Path("/var/cache/pacman/pkg/foo.pkg.tar.zst"))
        assert _validate_path_pkexec(Path("/var/log/journal"))
        assert _validate_path_pkexec(Path("/var/lib/pacman/local"))

    def test_rejects_disallowed_prefixes(self):
        assert not _validate_path_pkexec(Path("/etc/passwd"))
        assert not _validate_path_pkexec(Path("/tmp/foo"))
        assert not _validate_path_pkexec(Path("/home/user/foo"))

    def test_rejects_path_traversal(self):
        # En POSIX, resolve() seguiría symlinks y detectaría el traversal.
        # En Windows solo hacemos string check, que NO detecta ../../
        # porque el string SÍ empieza con el prefijo permitido.
        if os.name == "posix":
            assert not _validate_path_pkexec(Path("/var/cache/pacman/pkg/../../etc/passwd"))
        else:
            # En Windows esto es comportamiento esperado (limitación string check)
            # La validación real con resolve() está en privileges.py (solo POSIX)
            assert _validate_path_pkexec(Path("/var/cache/pacman/pkg/../../etc/passwd"))


class TestRejectSymlinksPkexec:
    def test_rejects_symlink(self, tmp_path, monkeypatch):
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        # No crear symlink real (requiere admin en Windows), mockear is_symlink
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(link))
        assert _reject_symlinks_pkexec(link)
        monkeypatch.setattr(Path, "is_symlink", original)

    def test_allows_regular_path(self, tmp_path):
        regular = tmp_path / "regular"
        regular.mkdir()
        assert not _reject_symlinks_pkexec(regular)


class TestRunPkexecRm:
    def test_success(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            assert cmd[:4] == ["pkexec", "rm", "-rf", "--"]
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = ""
            mock.stderr = ""
            return mock

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        result = _run_pkexec_rm([Path("/var/log/test.log")])
        assert "Eliminadas 1 ruta(s)" in result

    def test_cancelled(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 126
            mock.stderr = "dismissed"
            return mock

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        with pytest.raises(DBusError) as exc:
            _run_pkexec_rm([Path("/var/log/test.log")])
        assert exc.value.code == "CANCELLED"

    def test_failed(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 1
            mock.stderr = "permission denied"
            return mock

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        with pytest.raises(DBusError) as exc:
            _run_pkexec_rm([Path("/var/log/test.log")])
        assert exc.value.code == "EXECUTION_FAILED"

    def test_command_not_found(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError("pkexec")

        # Parchear en el módulo donde se usa
        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        with pytest.raises(DBusError) as exc:
            _run_pkexec_rm([Path("/var/log/test.log")])
        assert exc.value.code == "COMMAND_NOT_FOUND"


class TestRunPkexecPacman:
    def test_success(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            assert cmd[:4] == ["pkexec", "pacman", "-Rns", "--noconfirm"]
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = "removed"
            mock.stderr = ""
            return mock

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        result = _run_pkexec_pacman(["foo", "bar"])
        assert result == "removed"

    def test_command_not_found(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError("pkexec")

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        with pytest.raises(DBusError) as exc:
            _run_pkexec_pacman(["foo"])
        assert exc.value.code == "COMMAND_NOT_FOUND"

    def test_failed(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 1
            mock.stderr = "error"
            # Con check=True, subprocess.run lanza CalledProcessError
            raise subprocess.CalledProcessError(1, cmd, stderr="error")

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        with pytest.raises(DBusError) as exc:
            _run_pkexec_pacman(["foo"])
        assert exc.value.code == "EXECUTION_FAILED"


class TestPrivilegedClient:
    def test_init_without_gi(self, monkeypatch):
        # Simular que gi no está disponible
        monkeypatch.setitem(sys.modules, "gi", None)
        client = PrivilegedClient()
        assert not client._ensure_gi()

    def test_is_available_without_gi(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "gi", None)
        client = PrivilegedClient()
        assert not client.is_available()


class TestPrivilegedAPI:
    def test_remove_packages_empty(self):
        api = PrivilegedAPI(prefer_daemon=False)
        result = api.remove_packages([])
        assert result.success
        assert result.output == ""

    def test_clean_system_paths_empty(self):
        api = PrivilegedAPI(prefer_daemon=False)
        result = api.clean_system_paths([])
        assert result.success
        assert result.output == ""

    def test_remove_packages_fallback_success(self, monkeypatch):
        api = PrivilegedAPI(prefer_daemon=False)

        def fake_run(cmd, **kwargs):
            return MagicMock(returncode=0, stdout="removed", stderr="")

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        result = api.remove_packages(["foo", "bar"])
        assert result.success
        assert not result.used_daemon
        assert result.output == "removed"

    def test_remove_packages_fallback_cancelled(self, monkeypatch):
        api = PrivilegedAPI(prefer_daemon=False)

        def fake_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 126
            mock.stderr = "dismissed"
            raise subprocess.CalledProcessError(126, cmd, stderr="dismissed")

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        result = api.remove_packages(["foo"])
        assert not result.success
        assert result.error.code == "CANCELLED"

    def test_clean_system_paths_fallback_validates(self, monkeypatch):
        api = PrivilegedAPI(prefer_daemon=False)

        # Mock symlink detection
        monkeypatch.setattr(
            "blip_eraser.utils.dbus_client._reject_symlinks_pkexec", lambda p: True
        )

        result = api.clean_system_paths([Path("/var/log/test.log")])
        assert not result.success
        assert result.error.code == "VALIDATION_FAILED"
        assert "Symlink detectado" in result.error.message

    def test_clean_system_paths_fallback_rejects_disallowed(self):
        api = PrivilegedAPI(prefer_daemon=False)
        result = api.clean_system_paths([Path("/etc/passwd")])
        assert not result.success
        assert result.error.code == "VALIDATION_FAILED"
        assert "Ruta no permitida" in result.error.message

    def test_clean_system_paths_fallback_success(self, monkeypatch):
        api = PrivilegedAPI(prefer_daemon=False)

        def fake_run(cmd, **kwargs):
            return MagicMock(returncode=0, stdout="", stderr="")

        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        result = api.clean_system_paths([Path("/var/log/test.log")])
        assert result.success
        assert not result.used_daemon


class TestGetPrivilegedApi:
    def test_singleton(self):
        reset_privileged_api()
        api1 = get_privileged_api()
        api2 = get_privileged_api()
        assert api1 is api2
        reset_privileged_api()

    def test_default_prefer_daemon_is_false(self):
        """El daemon está deshabilitado por defecto hasta que esté listo con polkit."""
        reset_privileged_api()
        api = get_privileged_api()
        assert api._client is None  # prefer_daemon=False por defecto
        reset_privileged_api()


class TestDaemonFailureFallback:
    """Tests de defensa en profundidad: si el daemon falla inesperadamente,
    la operación debe caer a pkexec sin crashear la app."""

    def test_clean_system_paths_daemon_raises_unexpected_exception_falls_back_to_pkexec(
        self, monkeypatch
    ):
        """Simula: is_available() reporta True pero la llamada real lanza NameError.
        
        Debe caer a pkexec sin propagar la excepción ni crashear.
        """
        reset_privileged_api()
        api = PrivilegedAPI(prefer_daemon=True)  # Forzar uso de daemon para test
        
        # Mock: is_available() devuelve True (daemon "disponible")
        def mock_is_available(self):
            return True
        monkeypatch.setattr(PrivilegedClient, "is_available", mock_is_available)
        
        # Mock: clean_system_paths del cliente lanza NameError (simula bug real)
        def mock_clean_system_paths(self, paths):
            raise NameError("name 'GLib' is not defined")
        monkeypatch.setattr(PrivilegedClient, "clean_system_paths", mock_clean_system_paths)
        
        # Mock: pkexec rm funciona
        def fake_run(cmd, **kwargs):
            return MagicMock(returncode=0, stdout="Eliminadas 1 ruta(s)", stderr="")
        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        
        # La operación NO debe crashear, debe caer a pkexec
        result = api.clean_system_paths([Path("/var/log/test.log")])
        
        assert result.success
        assert not result.used_daemon
        assert "Eliminadas 1 ruta(s)" in result.output
        reset_privileged_api()

    def test_remove_packages_daemon_raises_unexpected_exception_falls_back_to_pkexec(
        self, monkeypatch
    ):
        """Simula: is_available() reporta True pero la llamada real lanza excepción genérica.
        
        Debe caer a pkexec sin propagar la excepción ni crashear.
        """
        reset_privileged_api()
        api = PrivilegedAPI(prefer_daemon=True)  # Forzar uso de daemon para test
        
        # Mock: is_available() devuelve True (daemon "disponible")
        def mock_is_available(self):
            return True
        monkeypatch.setattr(PrivilegedClient, "is_available", mock_is_available)
        
        # Mock: remove_packages del cliente lanza RuntimeError (bug inesperado)
        def mock_remove_packages(self, packages):
            raise RuntimeError("Daemon internal error")
        monkeypatch.setattr(PrivilegedClient, "remove_packages", mock_remove_packages)
        
        # Mock: pkexec pacman funciona
        def fake_run(cmd, **kwargs):
            return MagicMock(returncode=0, stdout="removed", stderr="")
        monkeypatch.setattr("blip_eraser.utils.dbus_client.subprocess.run", fake_run)
        
        # La operación NO debe crashear, debe caer a pkexec
        result = api.remove_packages(["foo", "bar"])
        
        assert result.success
        assert not result.used_daemon
        assert result.output == "removed"
        reset_privileged_api()

    def test_is_available_pings_daemon_with_timeout(self, monkeypatch):
        """is_available() debe hacer health-check real (Ping con timeout)."""
        reset_privileged_api()
        client = PrivilegedClient()
        
        # Mock: proxy creation succeeds but Ping fails (daemon no responde)
        mock_proxy = MagicMock()
        mock_proxy.call_sync.side_effect = Exception("Timeout")
        
        def mock_get_proxy(self):
            return mock_proxy
        monkeypatch.setattr(PrivilegedClient, "_get_proxy", mock_get_proxy)
        
        # Debe devolver False (no disponible) sin crashear
        assert not client.is_available()
        reset_privileged_api()


