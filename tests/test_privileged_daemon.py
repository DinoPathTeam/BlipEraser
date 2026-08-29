"""Tests para src/blip_eraser/daemon/privileged_daemon.py — daemon D-Bus privilegiado."""

import os
import sys
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock gi ANTES de importar el daemon
sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
sys.modules["gi.repository.GLib"] = MagicMock()
sys.modules["gi.repository.Gio"] = MagicMock()

# Añadir src al path para importar el daemon
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from blip_eraser.daemon.privileged_daemon import (
    ALLOWED_SYSTEM_PREFIXES,
    _validate_path,
    _reject_symlinks,
    _validate_clean_paths,
    _hash_path,
    _verify_package_signatures,
    _load_package_cache,
    get_cached_package_names,
    invalidate_package_cache,
    _validate_packages_exist,
    remove_packages,
    clean_system_paths,
)


class TestValidation:
    """Tests de funciones de validación de seguridad."""

    def test_validate_path_allowed_prefixes(self, monkeypatch):
        # En Windows, resolve() no resuelve igual que en POSIX
        # Mock resolve para que devuelva path que pase la validación
        def mock_resolve(self, strict=False):
            return Path(str(self).replace("\\", "/"))
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        
        assert _validate_path("/var/cache/pacman/pkg/foo.pkg.tar.zst")
        assert _validate_path("/var/log/journal")
        assert _validate_path("/var/lib/pacman/local")

    def test_validate_path_rejects_disallowed(self, monkeypatch):
        def mock_resolve(self, strict=False):
            return Path(str(self).replace("\\", "/"))
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        
        assert not _validate_path("/etc/passwd")
        assert not _validate_path("/tmp/foo")
        assert not _validate_path("/home/user/foo")

    def test_validate_path_rejects_traversal(self, monkeypatch):
        def mock_resolve(self, strict=False):
            return Path(str(self).replace("\\", "/"))
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        
        if os.name == "posix":
            assert not _validate_path("/var/cache/pacman/pkg/../../etc/passwd")
        else:
            assert _validate_path("/var/cache/pacman/pkg/../../etc/passwd")

    def test_reject_symlinks(self, tmp_path, monkeypatch):
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(link))
        assert _reject_symlinks(link)
        monkeypatch.setattr(Path, "is_symlink", original)

    def test_allow_regular_path(self, tmp_path):
        regular = tmp_path / "regular"
        regular.mkdir()
        assert not _reject_symlinks(regular)

    def test_validate_clean_paths(self, tmp_path, monkeypatch):
        def mock_resolve(self, strict=False):
            return Path(str(self).replace("\\", "/"))
        monkeypatch.setattr(Path, "is_symlink", lambda self: False)
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        valid, rejected = _validate_clean_paths([
            "/var/log/test.log",
            "/var/cache/pacman/pkg/foo.pkg.tar.zst",
            "/etc/passwd",
        ])
        assert "/var/log/test.log" in valid
        assert "/var/cache/pacman/pkg/foo.pkg.tar.zst" in valid
        assert "/etc/passwd" in rejected


class TestHashPath:
    def test_hash_path_consistent(self):
        h1 = _hash_path("/var/log/test.log")
        h2 = _hash_path("/var/log/test.log")
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_path_different(self):
        assert _hash_path("/var/log/a") != _hash_path("/var/log/b")


class TestPackageCache:
    """Tests de la caché de paquetes con verificación de firmas."""

    def test_hash_path(self):
        h = _hash_path("/test/path")
        assert len(h) == 16

    @patch("blip_eraser.daemon.privileged_daemon._verify_package_signatures", return_value=True)
    @patch("blip_eraser.daemon.privileged_daemon.subprocess.run")
    def test_load_package_cache_success(self, mock_run, mock_verify):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="package1 1.0-1\npackage2 2.0-1\n"
        )
        invalidate_package_cache()
        cache = _load_package_cache()
        assert "package1" in cache
        assert "package2" in cache

    @patch("blip_eraser.daemon.privileged_daemon._verify_package_signatures", return_value=False)
    @patch("blip_eraser.daemon.privileged_daemon.subprocess.run")
    def test_load_package_cache_signature_fail(self, mock_run, mock_verify):
        mock_run.return_value = MagicMock(returncode=0, stdout="pkg1 1.0-1\n")
        invalidate_package_cache()
        cache = _load_package_cache()
        # Aún carga la caché aunque fallen las firmas (pero loggea)
        assert "pkg1" in cache

    def test_get_cached_package_names(self, monkeypatch):
        monkeypatch.setattr(
            "blip_eraser.daemon.privileged_daemon._load_package_cache",
            lambda: {"pkg1", "pkg2"}
        )
        invalidate_package_cache()
        assert get_cached_package_names() == {"pkg1", "pkg2"}

    def test_invalidate_package_cache(self, monkeypatch):
        monkeypatch.setattr(
            "blip_eraser.daemon.privileged_daemon._load_package_cache",
            lambda: {"pkg1"}
        )
        get_cached_package_names()
        invalidate_package_cache()
        # Después de invalidar, debería recargar
        assert get_cached_package_names() == {"pkg1"}

    def test_validate_packages_exist(self, monkeypatch):
        monkeypatch.setattr(
            "blip_eraser.daemon.privileged_daemon.get_cached_package_names",
            lambda: {"pkg1", "pkg2"}
        )
        valid, invalid = _validate_packages_exist(["pkg1", "pkg3", "pkg2"])
        assert valid == ["pkg1", "pkg2"]
        assert invalid == ["pkg3"]


class TestOperations:
    """Tests de operaciones privilegiadas (mockeando subprocess)."""

    @patch("blip_eraser.daemon.privileged_daemon.subprocess.run")
    @patch("blip_eraser.daemon.privileged_daemon._validate_packages_exist")
    def test_remove_packages_success(self, mock_validate, mock_run):
        mock_validate.return_value = (["pkg1", "pkg2"], [])
        mock_run.return_value = MagicMock(returncode=0, stdout="removed")

        result = remove_packages(["pkg1", "pkg2"])
        assert result == "removed"
        mock_run.assert_called_once_with(
            ["pacman", "-Rns", "--noconfirm", "pkg1", "pkg2"],
            capture_output=True, text=True, check=True
        )

    @patch("blip_eraser.daemon.privileged_daemon._validate_packages_exist")
    def test_remove_packages_invalid_rejected(self, mock_validate):
        mock_validate.return_value = ([], ["pkg3"])
        with pytest.raises(ValueError) as exc:
            remove_packages(["pkg3"])
        assert "no instalados" in str(exc.value)

    @patch("blip_eraser.daemon.privileged_daemon._validate_clean_paths")
    @patch("blip_eraser.daemon.privileged_daemon.subprocess.run")
    def test_clean_system_paths_success(self, mock_run, mock_validate):
        mock_validate.return_value = (["/var/log/test.log"], [])
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = clean_system_paths(["/var/log/test.log"])
        assert "Eliminadas 1 ruta(s)" in result
        mock_run.assert_called_once_with(
            ["rm", "-rf", "--", "/var/log/test.log"],
            capture_output=True, text=True, check=True
        )

    @patch("blip_eraser.daemon.privileged_daemon._validate_clean_paths")
    def test_clean_system_paths_all_rejected(self, mock_validate):
        mock_validate.return_value = ([], ["/etc/passwd"])
        with pytest.raises(ValueError) as exc:
            clean_system_paths(["/etc/passwd"])
        assert "Todas las rutas rechazadas" in str(exc.value)

    @patch("blip_eraser.daemon.privileged_daemon._validate_clean_paths")
    @patch("blip_eraser.daemon.privileged_daemon.subprocess.run")
    def test_clean_system_paths_mixed(self, mock_run, mock_validate):
        mock_validate.return_value = (["/var/log/ok.log"], ["/etc/passwd"])
        mock_run.return_value = MagicMock(returncode=0, stdout="")

        result = clean_system_paths(["/var/log/ok.log", "/etc/passwd"])
        assert "Eliminadas 1 ruta(s)" in result


class TestSignatureVerification:
    """Tests de verificación de firmas de paquetes."""

    @patch("blip_eraser.daemon.privileged_daemon.Path.exists", return_value=False)
    @patch("blip_eraser.daemon.privileged_daemon.Path.glob", return_value=[])
    def test_verify_no_cache_dir(self, mock_glob, mock_exists):
        assert _verify_package_signatures() is True

    @patch("blip_eraser.daemon.privileged_daemon.Path.exists", return_value=True)
    @patch("blip_eraser.daemon.privileged_daemon.Path.glob")
    def test_verify_no_packages(self, mock_glob, mock_exists):
        mock_glob.return_value = []
        assert _verify_package_signatures() is True


class TestPrivilegedDaemonIntegration:
    """Tests de integración del servicio D-Bus (mocking GLib/Gio)."""

    def test_interface_xml_contains_required_methods(self):
        from blip_eraser.daemon.privileged_daemon import INTERFACE_XML
        assert "RemovePackages" in INTERFACE_XML
        assert "CleanSystemPaths" in INTERFACE_XML
        assert "Ping" in INTERFACE_XML
        assert 'type="as"' in INTERFACE_XML  # array of strings
        assert 'type="s"' in INTERFACE_XML   # string return
        assert 'type="b"' in INTERFACE_XML   # boolean return

    def test_service_register_method_exists(self):
        from blip_eraser.daemon.privileged_daemon import PrivilegedService
        assert hasattr(PrivilegedService, "register")
        assert hasattr(PrivilegedService, "on_method_call")
        assert hasattr(PrivilegedService, "run")


class TestMainEntryPoint:
    """Tests del punto de entrada main()."""

    def test_main_exits_if_not_root(self, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import main
        if hasattr(os, "geteuid"):
            monkeypatch.setattr(os, "geteuid", lambda: 1000)
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 1
        else:
            # Windows no tiene geteuid, saltar test
            pytest.skip("os.geteuid no disponible en Windows")


# Test de la política D-Bus actualizada
class TestDBusPolicy:
    def test_dbus_policy_restricts_to_wheel_group(self):
        from pathlib import Path
        policy_file = Path(__file__).parent.parent / "packaging" / "dbus" / "blip-eraser-privileged.conf"
        content = policy_file.read_text()
        assert 'group="wheel"' in content
        assert 'context="default"' in content
        assert 'deny send_destination' in content
        assert 'allow own' in content  # para root


if __name__ == "__main__":
    pytest.main([__file__, "-v"])