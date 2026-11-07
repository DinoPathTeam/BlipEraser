"""Tests para src/blip_eraser/daemon/privileged_daemon.py — daemon D-Bus privilegiado."""

import os
import sys
import threading
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
    validate_path_str as _validate_path_str,
    reject_symlinks_atomic as _reject_symlinks_atomic,
    validate_path_resolved as _validate_path_resolved,
    _validate_clean_paths,
    _hash_path,
    clean_system_paths,
)


class TestValidation:
    """Tests de funciones de validación de seguridad."""

    def test_validate_path_str_allowed_prefixes(self):
        assert _validate_path_str("/var/cache/pacman/pkg/foo.pkg.tar.zst")
        assert _validate_path_str("/var/log/journal")

    def test_validate_path_str_rejects_libpacman(self):
        # S2: /var/lib/pacman fuera de la allowlist (nadie lo limpia).
        assert not _validate_path_str("/var/lib/pacman/local")
        assert not _validate_path_str("/var/lib/pacman")

    def test_validate_path_str_rejects_disallowed(self):
        assert not _validate_path_str("/etc/passwd")
        assert not _validate_path_str("/tmp/foo")
        assert not _validate_path_str("/home/user/foo")

    def test_reject_symlinks_atomic(self, tmp_path, monkeypatch):
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(link))
        assert _reject_symlinks_atomic(link)
        monkeypatch.setattr(Path, "is_symlink", original)

    def test_allow_regular_path_atomic(self, tmp_path):
        regular = tmp_path / "regular"
        regular.mkdir()
        assert not _reject_symlinks_atomic(regular)

    def test_validate_path_resolved(self, monkeypatch):
        def mock_resolve(self, strict=False):
            return Path(str(self).replace("\\", "/"))
        monkeypatch.setattr(Path, "resolve", mock_resolve)
        
        assert _validate_path_resolved(Path("/var/log/test.log"))
        assert _validate_path_resolved(Path("/var/cache/pacman/pkg/foo.pkg.tar.zst"))
        assert not _validate_path_resolved(Path("/etc/passwd"))

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


class TestAuditLogging:
    def test_audit_fallback_writes_stderr_and_file(self, monkeypatch, tmp_path, capsys):
        import blip_eraser.daemon.privileged_daemon as daemon

        monkeypatch.setattr(daemon, "_journal_available", False)
        monkeypatch.setattr(daemon, "AUDIT_LOG_PATH", tmp_path / "daemon.log")

        daemon._audit_log("test_event", "path=/var/log/test.log")

        assert "AUDIT action=test_event" in capsys.readouterr().err
        assert "AUDIT action=test_event" in (tmp_path / "daemon.log").read_text()


class TestHashPathLength:
    def test_hash_path(self):
        assert len(_hash_path("/test/path")) == 16


class TestOperations:
    """Tests de operaciones privilegiadas (mockeando subprocess)."""

    @patch("blip_eraser.daemon.privileged_daemon._validate_clean_paths")
    @patch("blip_eraser.daemon.privileged_daemon._rm_rf_atomic")
    def test_clean_system_paths_success(self, mock_rm, mock_validate):
        mock_validate.return_value = (["/var/log/test.log"], [])
        mock_rm.return_value = (True, "")

        result = clean_system_paths(["/var/log/test.log"])
        assert "Eliminadas 1 ruta(s)" in result
        mock_rm.assert_called_once()

    @patch("blip_eraser.daemon.privileged_daemon._validate_clean_paths")
    def test_clean_system_paths_all_rejected(self, mock_validate):
        mock_validate.return_value = ([], ["/etc/passwd"])
        with pytest.raises(ValueError) as exc:
            clean_system_paths(["/etc/passwd"])
        assert "Todas las rutas rechazadas" in str(exc.value)

    @patch("blip_eraser.daemon.privileged_daemon._validate_clean_paths")
    @patch("blip_eraser.daemon.privileged_daemon._rm_rf_atomic")
    def test_clean_system_paths_mixed(self, mock_rm, mock_validate):
        mock_validate.return_value = (["/var/log/ok.log"], ["/etc/passwd"])
        mock_rm.return_value = (True, "")

        result = clean_system_paths(["/var/log/ok.log", "/etc/passwd"])
        assert "Eliminadas 1 ruta(s)" in result


class TestPrivilegedDaemonIntegration:
    """Tests de integración del servicio D-Bus (mocking GLib/Gio)."""

    def test_interface_xml_contains_required_methods(self):
        from blip_eraser.daemon.privileged_daemon import INTERFACE_XML
        # El daemon solo limpia rutas: la desinstalación va por pkexec pacman.
        assert "RemovePackages" not in INTERFACE_XML
        assert "CleanSystemPaths" in INTERFACE_XML
        assert "Ping" in INTERFACE_XML
        assert 'type="as"' in INTERFACE_XML
        assert 'type="s"' in INTERFACE_XML
        assert 'type="b"' in INTERFACE_XML

    def test_service_class_has_required_methods(self):
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
            # main() devuelve código (sys.exit solo en __main__): 1 = no root.
            assert main() == 1
        else:
            pytest.skip("os.geteuid no disponible en Windows")


class TestDBusPolicy:
    def test_dbus_policy_restricts_to_wheel_group(self):
        from pathlib import Path
        policy_file = Path(__file__).parent.parent / "packaging" / "dbus" / "blip-eraser-privileged.conf"
        content = policy_file.read_text()
        assert 'group="wheel"' in content
        assert 'context="default"' in content
        assert 'deny send_destination' in content
        assert 'allow own' in content

    def test_systemd_unit_captures_unbuffered_audit_output(self):
        service_file = (
            Path(__file__).parent.parent
            / "packaging"
            / "systemd"
            / "blip-eraser-privileged.service"
        )
        content = service_file.read_text(encoding="utf-8")
        assert "StandardOutput=journal" in content
        assert "StandardError=journal" in content
        assert "Environment=PYTHONUNBUFFERED=1" in content
        assert "/var/log/blip-eraser" in content


class TestAtomicRemoval:
    """Tests específicos para la eliminación atómica (TOCTOU protection)."""

    def test_rm_rf_atomic_exists(self):
        from blip_eraser.daemon.privileged_daemon import _rm_rf_atomic
        assert callable(_rm_rf_atomic)

    def test_rm_rf_dir_atomic_exists(self):
        from blip_eraser.daemon.privileged_daemon import _rm_rf_dir_atomic
        assert callable(_rm_rf_dir_atomic)

    def _allow_all(self, monkeypatch):
        import blip_eraser.daemon.privileged_daemon as daemon_mod
        monkeypatch.setattr(daemon_mod, "_validate_path_str", lambda p: True)

    def test_removes_file_keeps_sibling(self, tmp_path, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _rm_rf_atomic
        self._allow_all(monkeypatch)
        target = tmp_path / "borrar.txt"
        sibling = tmp_path / "quedar.txt"
        target.write_text("x")
        sibling.write_text("y")
        ok, err = _rm_rf_atomic(target)
        assert ok, err
        assert not target.exists()
        assert sibling.read_text() == "y"

    def test_removes_tree_keeps_parent_and_sibling(self, tmp_path, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _rm_rf_atomic
        self._allow_all(monkeypatch)
        target = tmp_path / "target"
        (target / "sub" / "deep").mkdir(parents=True)
        (target / "sub" / "deep" / "f.bin").write_bytes(b"0" * 100)
        (target / "top.txt").write_text("t")
        sibling = tmp_path / "hermano"
        sibling.mkdir()
        (sibling / "s.txt").write_text("s")
        ok, err = _rm_rf_atomic(target)
        assert ok, err
        assert not target.exists()
        # El padre y el hermano quedan intactos (regresión P5: antes se
        # listaba el padre y se borraban los hermanos).
        assert tmp_path.exists()
        assert (sibling / "s.txt").read_text() == "s"

    def test_symlinks_removed_as_links_target_untouched(self, tmp_path, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _rm_rf_atomic
        self._allow_all(monkeypatch)
        outside = tmp_path / "fuera"
        outside.mkdir()
        secret = outside / "secreto.txt"
        secret.write_text("no tocar")
        target = tmp_path / "target"
        target.mkdir()
        (target / "link_file").symlink_to(secret)
        (target / "link_dir").symlink_to(outside, target_is_directory=True)
        ok, err = _rm_rf_atomic(target)
        assert ok, err
        assert not target.exists()
        assert secret.read_text() == "no tocar"

    def test_top_level_symlink_rejected(self, tmp_path, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _rm_rf_atomic
        self._allow_all(monkeypatch)
        real = tmp_path / "real.txt"
        real.write_text("r")
        link = tmp_path / "enlace"
        link.symlink_to(real)
        ok, err = _rm_rf_atomic(link)
        assert not ok
        assert real.read_text() == "r"
        assert link.is_symlink()


class TestActiveGraphicalSession:
    """_check_active_graphical_session camina sesiones (show-user no da Type)."""

    def _fake(self, monkeypatch, user_out, sess_out):

        def fake_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "show-user" in cmd:
                mock.stdout = user_out
            else:
                mock.stdout = sess_out
            return mock

        monkeypatch.setattr(
            "blip_eraser.daemon.privileged_daemon.subprocess.run", fake_run
        )
        import blip_eraser.daemon.privileged_daemon as daemon_mod
        daemon_mod._ACTIVE_SESSION_CACHE.clear()

    def test_wayland_active(self, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _check_active_graphical_session
        self._fake(monkeypatch, "Sessions=2\n", "Type=wayland\nState=active\n")
        assert _check_active_graphical_session(1000) is True

    def test_no_graphical_session(self, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _check_active_graphical_session
        self._fake(monkeypatch, "Sessions=5\n", "Type=tty\nState=active\n")
        assert _check_active_graphical_session(1000) is False

    def test_no_sessions(self, monkeypatch):
        from blip_eraser.daemon.privileged_daemon import _check_active_graphical_session
        self._fake(monkeypatch, "Sessions=\n", "")
        assert _check_active_graphical_session(1000) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestRateLimit:
    """Cuota por sender para métodos destructivos (Ping exento por diseño)."""

    def test_allows_under_quota(self):
        from blip_eraser.daemon.privileged_daemon import _check_rate_limit
        assert _check_rate_limit("test-sender-cuota-ok") is True

    def test_blocks_over_quota(self):
        from blip_eraser.daemon import privileged_daemon as daemon_mod
        sender = "test-sender-cuota-llena"
        daemon_mod._rate_limit_hits.pop(sender, None)
        for _ in range(daemon_mod._RATE_LIMIT_MAX):
            assert daemon_mod._check_rate_limit(sender) is True
        assert daemon_mod._check_rate_limit(sender) is False
        daemon_mod._rate_limit_hits.pop(sender, None)

    def test_window_expiry(self, monkeypatch):
        from blip_eraser.daemon import privileged_daemon as daemon_mod
        sender = "test-sender-ventana"
        daemon_mod._rate_limit_hits[sender] = [0.0] * daemon_mod._RATE_LIMIT_MAX
        monkeypatch.setattr(daemon_mod.time, "monotonic", lambda: daemon_mod._RATE_LIMIT_WINDOW + 1)
        assert daemon_mod._check_rate_limit(sender) is True
        daemon_mod._rate_limit_hits.pop(sender, None)

    def test_quota_shared_across_senders_same_uid(self, monkeypatch):
        """Reconectar (sender distinto, mismo UID) NO resetea la cuota."""
        from unittest.mock import MagicMock

        from blip_eraser.daemon import privileged_daemon as daemon_mod

        svc = daemon_mod.PrivilegedService()
        monkeypatch.setattr(svc, "_authorized_uid", lambda conn, sender: 1000)
        monkeypatch.setattr(svc, "_polkit_authorized", lambda conn, sender, action: True)
        monkeypatch.setattr(
            daemon_mod, "clean_system_paths",
            lambda paths: (_ for _ in ()).throw(ValueError("rechazado")),
        )

        class FakeInv:
            def __init__(self):
                self.error = None

            def return_dbus_error(self, name, msg):
                self.error = name

            def return_value(self, value):
                pass

        daemon_mod._rate_limit_hits.pop("uid:1000", None)
        try:
            for i in range(daemon_mod._RATE_LIMIT_MAX):
                inv = FakeInv()
                svc._handle_call(
                    MagicMock(), f":1.{100 + i}", "/", "com.dinopath.BlipEraser.Privileged",
                    "CleanSystemPaths", [["/var/log/x"]], inv,
                )
                assert inv.error == "org.freedesktop.DBus.Error.InvalidArgs"
            inv = FakeInv()
            svc._handle_call(
                MagicMock(), ":1.999", "/", "com.dinopath.BlipEraser.Privileged",
                "CleanSystemPaths", [["/var/log/x"]], inv,
            )
            assert inv.error == "org.freedesktop.DBus.Error.LimitsExceeded"
        finally:
            daemon_mod._rate_limit_hits.pop("uid:1000", None)


class TestPolkitGate:
    """S1: sin autorización polkit no hay operación destructiva."""

    def _call(self, monkeypatch, authorized):
        from unittest.mock import MagicMock

        from blip_eraser.daemon import privileged_daemon as daemon_mod

        svc = daemon_mod.PrivilegedService()
        monkeypatch.setattr(svc, "_authorized_uid", lambda conn, sender: 1000)
        monkeypatch.setattr(svc, "_polkit_authorized", lambda conn, sender, action: authorized)
        called = []
        monkeypatch.setattr(
            daemon_mod, "clean_system_paths", lambda paths: called.append(paths) or "ok"
        )

        class FakeInv:
            def __init__(self):
                self.error = None
                self.value = None

            def return_dbus_error(self, name, msg):
                self.error = name

            def return_value(self, value):
                self.value = value

        inv = FakeInv()
        svc._handle_call(
            MagicMock(), ":1.77", "/", "com.dinopath.BlipEraser.Privileged",
            "CleanSystemPaths", [["/var/log/x"]], inv,
        )
        return inv, called

    def test_denied_blocks_operation(self, monkeypatch):
        inv, called = self._call(monkeypatch, False)
        assert inv.error == "org.freedesktop.DBus.Error.AccessDenied"
        assert called == []

    def test_authorized_runs_operation(self, monkeypatch):
        inv, called = self._call(monkeypatch, True)
        assert inv.error is None
        assert called == [["/var/log/x"]]

class TestNoPackageManagementInDaemon:
    """Regresión: el daemon no ejecuta pacman (hooks y escrituras fuera del sandbox)."""

    def test_remove_packages_method_is_unknown(self, monkeypatch):
        from unittest.mock import MagicMock

        from blip_eraser.daemon import privileged_daemon as daemon_mod

        svc = daemon_mod.PrivilegedService()
        monkeypatch.setattr(svc, "_authorized_uid", lambda conn, sender: 1000)

        class FakeInv:
            error = None

            def return_dbus_error(self, name, msg):
                self.error = name

            def return_value(self, value):
                pass

        inv = FakeInv()
        svc._handle_call(
            MagicMock(), ":1.5", "/", "com.dinopath.BlipEraser.Privileged",
            "RemovePackages", [["x"]], inv,
        )
        assert inv.error == "org.freedesktop.DBus.Error.UnknownMethod"

    def test_daemon_module_has_no_pacman_code(self):
        from blip_eraser.daemon import privileged_daemon as daemon_mod

        assert not hasattr(daemon_mod, "remove_packages")
        assert not hasattr(daemon_mod, "_verify_package_signatures")
        assert "/usr/bin/pacman" not in Path(daemon_mod.__file__).read_text(encoding="utf-8")

    def test_apparmor_profile_does_not_exec_pacman(self):
        profile = (
            Path(__file__).parent.parent
            / "packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged"
        ).read_text(encoding="utf-8")
        assert "/usr/bin/pacman " not in profile and "/usr/bin/pacman-key" not in profile


class TestNonBlockingDispatch:
    """Punto 2: un prompt de polkit abierto no congela al daemon."""

    class FakeInv:
        def __init__(self):
            self.error = None
            self.value = None
            self.done = threading.Event()

        def return_dbus_error(self, name, msg):
            self.error = name
            self.done.set()

        def return_value(self, value):
            self.value = value
            self.done.set()

    def _svc(self, monkeypatch, polkit):
        from blip_eraser.daemon import privileged_daemon as daemon_mod

        svc = daemon_mod.PrivilegedService()
        monkeypatch.setattr(svc, "_authorized_uid", lambda conn, sender: 1000)
        monkeypatch.setattr(svc, "_polkit_authorized", polkit)
        monkeypatch.setattr(daemon_mod, "clean_system_paths", lambda paths: "ok")
        daemon_mod._rate_limit_hits.pop("uid:1000", None)
        daemon_mod._inflight_uids.discard(1000)
        return daemon_mod, svc

    def test_ping_answers_while_polkit_prompt_is_open(self, monkeypatch):
        release = threading.Event()
        entered = threading.Event()

        def slow_polkit(conn, sender, action):
            entered.set()
            release.wait(5)
            return True

        daemon_mod, svc = self._svc(monkeypatch, slow_polkit)
        clean, ping = self.FakeInv(), self.FakeInv()
        try:
            svc.on_method_call(MagicMock(), ":1.1", "/", "i", "CleanSystemPaths", [["/var/log/x"]], clean)
            assert entered.wait(2), "el prompt de polkit no llegó a abrirse"
            svc.on_method_call(MagicMock(), ":1.1", "/", "i", "Ping", [], ping)
            assert ping.done.wait(2), "Ping quedó bloqueado por el prompt abierto"
            assert not clean.done.is_set()
        finally:
            release.set()
        assert clean.done.wait(2)
        assert clean.error is None
        daemon_mod._rate_limit_hits.pop("uid:1000", None)

    def test_second_operation_same_uid_rejected_while_one_in_flight(self, monkeypatch):
        release = threading.Event()
        entered = threading.Event()

        def slow_polkit(conn, sender, action):
            entered.set()
            release.wait(5)
            return True

        daemon_mod, svc = self._svc(monkeypatch, slow_polkit)
        first, second = self.FakeInv(), self.FakeInv()
        try:
            svc.on_method_call(MagicMock(), ":1.1", "/", "i", "CleanSystemPaths", [["/var/log/x"]], first)
            assert entered.wait(2)
            svc.on_method_call(MagicMock(), ":1.2", "/", "i", "CleanSystemPaths", [["/var/log/y"]], second)
            assert second.done.wait(2)
            assert second.error == "org.freedesktop.DBus.Error.LimitsExceeded"
        finally:
            release.set()
        assert first.done.wait(2)
        daemon_mod._rate_limit_hits.pop("uid:1000", None)

    def test_rate_limit_counts_denied_polkit_attempts(self, monkeypatch):
        daemon_mod, svc = self._svc(monkeypatch, lambda conn, sender, action: False)
        try:
            for _ in range(daemon_mod._RATE_LIMIT_MAX):
                inv = self.FakeInv()
                svc._handle_call(MagicMock(), ":1.1", "/", "i", "CleanSystemPaths", [["/var/log/x"]], inv)
                assert inv.error == "org.freedesktop.DBus.Error.AccessDenied"
            inv = self.FakeInv()
            svc._handle_call(MagicMock(), ":1.1", "/", "i", "CleanSystemPaths", [["/var/log/x"]], inv)
            assert inv.error == "org.freedesktop.DBus.Error.LimitsExceeded"
        finally:
            daemon_mod._rate_limit_hits.pop("uid:1000", None)

    def test_inflight_slot_released_after_failure(self, monkeypatch):
        daemon_mod, svc = self._svc(monkeypatch, lambda conn, sender, action: False)
        inv = self.FakeInv()
        svc._handle_call(MagicMock(), ":1.1", "/", "i", "CleanSystemPaths", [["/var/log/x"]], inv)
        assert 1000 not in daemon_mod._inflight_uids
        daemon_mod._rate_limit_hits.pop("uid:1000", None)

    def test_busy_when_no_worker_slots(self, monkeypatch):
        from blip_eraser.daemon import privileged_daemon as daemon_mod

        svc = daemon_mod.PrivilegedService()
        held = [daemon_mod._worker_slots.acquire(blocking=False) for _ in range(daemon_mod._MAX_WORKERS)]
        try:
            inv = self.FakeInv()
            svc.on_method_call(MagicMock(), ":1.1", "/", "i", "Ping", [], inv)
            assert inv.error == "org.freedesktop.DBus.Error.LimitsExceeded"
        finally:
            for ok in held:
                if ok:
                    daemon_mod._worker_slots.release()
