"""Rutas de auditoría/identidad bajo /var/log: nunca borrables ni contadas."""

from pathlib import Path

import pytest

from blip_eraser.utils import scan
from blip_eraser.utils.dbus_client import PrivilegedAPI
from blip_eraser.utils.privileges import remove_paths
from blip_eraser.utils.validation import is_audit_protected

PROTECTED = [
    "/var/log/journal", "/var/log/journal/abc/system.journal",
    "/var/log/blip-eraser/daemon.log",
    "/var/log/audit", "/var/log/audit/audit.log", "/var/log/audit/audit.log.1",
    "/var/log/wtmp", "/var/log/wtmp.1", "/var/log/wtmp-20260101",
    "/var/log/btmp", "/var/log/btmp.1",
    "/var/log/lastlog", "/var/log/faillog",
    "/var/log/pacman.log", "/var/log/pacman.log-20260101",
    "/var/log/auth.log", "/var/log/secure",
]
NOT_PROTECTED = [
    "/var/log/Xorg.0.log", "/var/log/old.log", "/var/log/cups/error_log",
    "/var/log/wtmpfoo", "/var/log/auditor.log", "/var/log/mysecure",
    "/var/cache/pacman/pkg/foo.pkg.tar.zst",
]


@pytest.mark.parametrize("p", PROTECTED)
def test_protected(p):
    assert is_audit_protected(p)


@pytest.mark.parametrize("p", NOT_PROTECTED)
def test_not_protected(p):
    assert not is_audit_protected(p)


def test_dotdot_cannot_smuggle_a_protected_path():
    assert is_audit_protected("/var/log/cups/../wtmp")


@pytest.mark.parametrize("p", ["/var/log/wtmp.1", "/var/log/audit/audit.log", "/var/log/pacman.log"])
def test_pkexec_client_rejects(p):
    result = PrivilegedAPI(prefer_daemon=False).clean_system_paths([Path(p)])
    assert not result.success and result.error.code == "VALIDATION_FAILED"


@pytest.mark.parametrize("p", ["/var/log/btmp.1", "/var/log/audit/x"])
def test_remove_paths_rejects(p):
    outcome = remove_paths([Path(p)])
    assert outcome.removed == 0
    assert outcome.errors[0].detail == "audit_path_protected"


@pytest.fixture
def fake_logs(tmp_path, monkeypatch):
    logs = tmp_path / "log"
    (logs / "audit").mkdir(parents=True)
    (logs / "audit" / "audit.log").write_bytes(b"x" * 5000)
    (logs / "journal").mkdir()
    (logs / "journal" / "system.journal").write_bytes(b"x" * 9000)
    (logs / "wtmp").write_bytes(b"x" * 100)
    (logs / "wtmp.1").write_bytes(b"x" * 100)
    (logs / "old.log").write_bytes(b"x" * 2000)
    monkeypatch.setattr(scan, "_LOG_DIR", logs)
    monkeypatch.setattr(scan, "_cache_dir", lambda: tmp_path / "nocache")
    monkeypatch.setattr(scan, "_PACMAN_CACHE", tmp_path / "nopkg")
    monkeypatch.setattr(scan, "orphan_packages", lambda: [])
    return logs


def test_listing_hides_protected_entries(fake_logs):
    names = {p.name for k, p, _ in scan.scan_cleanup_items() if k == "logs"}
    assert names == {"old.log"}


def test_recoverable_logs_total_excludes_protected(fake_logs):
    assert scan.scan_cleanup()["logs_bytes"] == 2000
