"""Tests para utils/privileges.py — decisión y ejecución con pkexec.

Sin PyQt6, sin borrados reales de sistema: se mockea subprocess.run y se usan
rutas temporales para la parte de $HOME.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from blip_eraser.utils import privileges
from blip_eraser.utils.privileges import (
    RemovalError,
    needs_elevation,
    remove_paths,
)


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


class TestRemovePathsSystem:
    def test_builds_single_pkexec_batch(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return FakeResult(returncode=0)

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)
        # Usar rutas que están en ALLOWED_SYSTEM_PREFIXES
        outcome = remove_paths([Path("/var/log/journal"), Path("/var/log/pacman.log")])
        assert outcome.removed == 2
        assert outcome.errors == []
        assert len(calls) == 1  # UNA sola llamada pkexec para el lote
        assert calls[0][:4] == ["pkexec", "rm", "-rf", "--"]
        normalized = {str(p).replace("\\", "/") for p in calls[0][4:]}
        assert normalized == {"/var/log/journal", "/var/log/pacman.log"}

    def test_cancelled_auth_is_structured_error(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            if cmd[0] == "pkexec":
                return FakeResult(returncode=126, stderr="dismissed")
            return FakeResult()

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)
        outcome = remove_paths([Path("/var/cache/pacman/pkg/foo.pkg.tar.zst")])
        assert outcome.removed == 0
        assert outcome.errors[0].code == "cancelled"

    def test_pkexec_missing_structured_error(self, monkeypatch):
        def boom(cmd, **kwargs):
            if cmd[0] == "pkexec":
                raise FileNotFoundError("pkexec")
            return FakeResult()

        monkeypatch.setattr(privileges.subprocess, "run", boom)
        outcome = remove_paths([Path("/var/lib/pacman/local")])
        assert outcome.errors[0].code == "pkexec_missing"

    def test_mixed_batch_splits_home_and_system(self, monkeypatch, tmp_path):
        calls = []
        home_target = tmp_path / "carpeta"
        home_target.mkdir()

        def fake_run(cmd, **kwargs):
            if cmd[0] == "pkexec":
                calls.append(cmd)
                return FakeResult(returncode=0)
            return FakeResult()

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)
        outcome = remove_paths([tmp_path / "carpeta", Path("/var/log/test.log")])
        assert outcome.removed == 2
        assert len(calls) == 1
        assert not home_target.exists()

    def test_rejects_path_not_in_allowlist(self, monkeypatch):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return FakeResult(returncode=0)

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)
        # /etc/passwd no está en la allowlist
        outcome = remove_paths([Path("/etc/passwd")])
        assert outcome.removed == 0
        assert len(outcome.errors) == 1
        assert outcome.errors[0].code == "validation_failed"
        assert outcome.errors[0].detail == "path_not_in_allowlist"
        assert len(calls) == 0  # No se debe llamar a pkexec

    def test_rejects_symlink(self, monkeypatch, tmp_path):
        """Test que la validación rechaza symlinks.

        En Windows no se pueden crear symlinks sin privilegios, así que
        mockeamos _reject_symlinks para simular la detección.
        """
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return FakeResult(returncode=0)

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)

        # Mock _reject_symlinks para simular detección de symlink
        original_reject = privileges._reject_symlinks
        monkeypatch.setattr(privileges, "_reject_symlinks", lambda p: True)

        outcome = remove_paths([Path("/var/log/fake_link")])
        assert outcome.removed == 0
        assert len(outcome.errors) == 1
        assert outcome.errors[0].code == "validation_failed"
        assert outcome.errors[0].detail == "symlink_detected"
        assert len(calls) == 0  # No se debe llamar a pkexec

        # Restaurar
        monkeypatch.setattr(privileges, "_reject_symlinks", original_reject)


class TestRemovalError:
    def test_repr_carries_code_and_paths(self):
        err = RemovalError(paths=[Path("/var/log/x")], code="cancelled")
        assert err.code == "cancelled"
        assert err.paths[0].name == "x"