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
        outcome = remove_paths([Path("/var/log/mensajes"), Path("/var/log/boot")])
        assert outcome.removed == 2
        assert outcome.errors == []
        assert len(calls) == 1  # UNA sola llamada pkexec para el lote
        assert calls[0][:4] == ["pkexec", "rm", "-rf", "--"]
        normalized = {str(p).replace("\\", "/") for p in calls[0][4:]}
        assert normalized == {"/var/log/mensajes", "/var/log/boot"}

    def test_cancelled_auth_is_structured_error(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            return FakeResult(returncode=126, stderr="dismissed")

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)
        outcome = remove_paths([Path("/var/cache/pacman/pkg/foo")])
        assert outcome.removed == 0
        assert outcome.errors[0].code == "cancelled"

    def test_pkexec_missing_structured_error(self, monkeypatch):
        def boom(cmd, **kwargs):
            raise FileNotFoundError("pkexec")

        monkeypatch.setattr(privileges.subprocess, "run", boom)
        outcome = remove_paths([Path("/var/log")])
        assert outcome.errors[0].code == "pkexec_missing"

    def test_mixed_batch_splits_home_and_system(self, monkeypatch, tmp_path):
        calls = []
        home_target = tmp_path / "carpeta"
        home_target.mkdir()

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return FakeResult(returncode=0)

        monkeypatch.setattr(privileges.subprocess, "run", fake_run)
        outcome = remove_paths([tmp_path / "carpeta", Path("/var/log")])
        assert outcome.removed == 2
        assert len(calls) == 1
        assert not home_target.exists()


class TestRemovalError:
    def test_repr_carries_code_and_paths(self):
        err = RemovalError(paths=[Path("/var/log/x")], code="cancelled")
        assert err.code == "cancelled"
        assert err.paths[0].name == "x"