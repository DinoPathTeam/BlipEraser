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


