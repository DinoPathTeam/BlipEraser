"""Tests para utils/privileges.py — decisión y ejecución con daemon D-Bus + fallback pkexec.

Sin PyQt6, sin borrados reales de sistema: se mockea la API privilegiada y se usan
rutas temporales para la parte de $HOME.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blip_eraser.utils import privileges
from blip_eraser.utils.privileges import (
    RemovalError,
    needs_elevation,
    remove_paths,
    get_privileged_api,
)
from blip_eraser.utils.dbus_client import OperationResult, DBusError, reset_privileged_api


@dataclass
class FakeResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class TestNeedsElevation:
    def test_home_paths_do_not_require_elevation(self, tmp_path):
        assert not needs_elevation(tmp_path / "some" / "folder")

    def test_expanduser_home_not_elevated(self):
        assert not needs_elevation(Path("~/.cache").expanduser())

    def test_var_cache_pacman_requires_elevation(self):
        assert needs_elevation(Path("/var/cache/pacman/pkg"))

    def test_var_log_requires_elevation(self):
        assert needs_elevation(Path("/var/log"))

    def test_system_prefix_not_present_is_not_elevated(self):
        # /tmp no está en los prefijos de sistema: no se asume privilegio.
        assert not needs_elevation(Path("/tmp/cualquier-cosa"))

    def test_custom_home_respected(self, tmp_path):
        home = tmp_path / "home"
        assert needs_elevation(Path("/var/cache"), home=home)
        assert not needs_elevation(home / "data")


class TestRemovePathsHome:
    def test_removes_home_files_directly(self, tmp_path):
        target = tmp_path / "app"
        target.mkdir()
        (target / "data.bin").write_bytes(b"x")
        outcome = remove_paths([target])
        assert outcome.removed == 1
        assert outcome.errors == []
        assert not target.exists()

    def test_missing_home_path_is_failure(self, tmp_path):
        outcome = remove_paths([tmp_path / "no-existe"])
        assert outcome.removed == 0
        assert len(outcome.errors) == 1
        assert outcome.errors[0].code == "failed"

    def test_home_denylist_rejected(self, tmp_path):
        # .ssh está en denylist - usar home real para que relative_to funcione
        target = Path.home() / ".ssh" / "test_blip_eraser"
        target.mkdir(parents=True, exist_ok=True)
        (target / "id_rsa").write_bytes(b"x")
        try:
            outcome = remove_paths([target])
            assert outcome.removed == 0
            assert len(outcome.errors) == 1
            assert outcome.errors[0].code == "validation_failed"
            assert outcome.errors[0].detail == "path_in_home_denylist"
        finally:
            # Limpiar
            import shutil
            shutil.rmtree(target.parent, ignore_errors=True)


class TestRemovePathsSystem:
    def _mock_api_success(self, monkeypatch):
        """Mock de API que simula éxito en operación de sistema."""
        def mock_clean(paths):
            return OperationResult(success=True, output="ok", used_daemon=False)
        mock_api = MagicMock()
        mock_api.clean_system_paths = mock_clean
        monkeypatch.setattr(privileges, "get_privileged_api", lambda: mock_api)

    def _mock_api_failure(self, monkeypatch, code="EXECUTION_FAILED", message="failed"):
        """Mock de API que simula fallo."""
        def mock_clean(paths):
            return OperationResult(
                success=False,
                error=DBusError(code, message),
                used_daemon=False
            )
        mock_api = MagicMock()
        mock_api.clean_system_paths = mock_clean
        monkeypatch.setattr(privileges, "get_privileged_api", lambda: mock_api)

    def test_success_via_api(self, monkeypatch):
        self._mock_api_success(monkeypatch)
        outcome = remove_paths([Path("/var/log/journal"), Path("/var/log/pacman.log")])
        assert outcome.removed == 2
        assert outcome.errors == []

    def test_cancelled_is_structured_error(self, monkeypatch):
        self._mock_api_failure(monkeypatch, "CANCELLED", "Autenticación cancelada")
        outcome = remove_paths([Path("/var/cache/pacman/pkg/foo.pkg.tar.zst")])
        assert outcome.removed == 0
        assert outcome.errors[0].code == "cancelled"

    def test_pkexec_missing_structured_error(self, monkeypatch):
        self._mock_api_failure(monkeypatch, "COMMAND_NOT_FOUND", "pkexec not found")
        outcome = remove_paths([Path("/var/lib/pacman/local")])
        assert outcome.errors[0].code == "pkexec_missing"

    def test_mixed_batch_splits_home_and_system(self, monkeypatch, tmp_path):
        self._mock_api_success(monkeypatch)
        home_target = tmp_path / "carpeta"
        home_target.mkdir()
        outcome = remove_paths([tmp_path / "carpeta", Path("/var/log/test.log")])
        assert outcome.removed == 2
        assert not home_target.exists()

    def test_rejects_path_not_in_allowlist(self, monkeypatch):
        # La validación ocurre ANTES de llamar a la API
        outcome = remove_paths([Path("/etc/passwd")])
        assert outcome.removed == 0
        assert len(outcome.errors) == 1
        assert outcome.errors[0].code == "validation_failed"
        assert outcome.errors[0].detail == "path_not_in_allowlist"

    def test_rejects_symlink(self, monkeypatch, tmp_path):
        """Test que la validación rechaza symlinks."""
        # Mock _reject_symlinks para simular detección de symlink
        original_reject = privileges._reject_symlinks
        monkeypatch.setattr(privileges, "_reject_symlinks", lambda p: True)

        outcome = remove_paths([Path("/var/log/fake_link")])
        assert outcome.removed == 0
        assert len(outcome.errors) == 1
        assert outcome.errors[0].code == "validation_failed"
        assert outcome.errors[0].detail == "symlink_detected"

        # Restaurar
        monkeypatch.setattr(privileges, "_reject_symlinks", original_reject)

    def test_rejects_all_invalid_paths(self, monkeypatch):
        """Todas las rutas inválidas -> rejected_all audit log."""
        outcome = remove_paths([Path("/etc/passwd"), Path("/tmp/foo")])
        assert outcome.removed == 0
        assert len(outcome.errors) == 2


class TestRemovalError:
    def test_repr_carries_code_and_paths(self):
        err = RemovalError(paths=[Path("/var/log/x")], code="cancelled")
        assert err.code == "cancelled"
        assert err.paths[0].name == "x"


class TestPrivilegedAPIIntegration:
    """Tests de integración con la API real (fallback pkexec mockado)."""

    def test_remove_packages_uses_api(self, monkeypatch):
        """Verifica que uninstall_packages usa la API privilegiada."""
        from blip_eraser.utils import pacman

        mock_remove = MagicMock(return_value=OperationResult(success=True, output="removed", used_daemon=False))

        mock_api = MagicMock()
        mock_api.remove_packages = mock_remove
        monkeypatch.setattr(pacman, "get_privileged_api", lambda: mock_api)

        # Mock validación de paquetes
        monkeypatch.setattr(pacman, "_validate_packages_exist", lambda pkgs: (pkgs, []))

        result = pacman.uninstall_packages(["foo", "bar"])
        assert result == "removed"
        mock_remove.assert_called_once_with(["foo", "bar"], noconfirm=True)

    def test_uninstall_packages_rejects_invalid(self, monkeypatch):
        from blip_eraser.utils import pacman

        monkeypatch.setattr(pacman, "_validate_packages_exist", lambda pkgs: ([], pkgs))

        with pytest.raises(ValueError) as exc:
            pacman.uninstall_packages(["invalid"])
        assert "rechazados" in str(exc.value)