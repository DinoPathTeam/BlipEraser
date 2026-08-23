"""Tests para utils/log.py (buffer de registro, sin PyQt6)."""

from pathlib import Path

from blip_eraser.utils.log import LogBuffer, write_diagnostic

import blip_eraser.utils.log as log_mod


class TestLogBuffer:
    def test_starts_empty(self):
        assert LogBuffer().entries() == []

    def test_add_and_latest(self):
        buf = LogBuffer()
        buf.add("hola")
        buf.add("mundo")
        assert buf.latest() == "mundo"
        assert [msg for _ts, msg in buf.entries()] == ["hola", "mundo"]

    def test_entries_are_snapshots(self):
        buf = LogBuffer()
        buf.add("uno")
        entries = buf.entries()
        entries.append(("00:00:00", "mutado"))
        assert len(buf.entries()) == 1

    def test_clear(self):
        buf = LogBuffer()
        buf.add("uno")
        buf.clear()
        assert buf.entries() == []
        assert buf.latest() is None

    def test_max_entries_truncated(self):
        buf = LogBuffer(max_entries=3)
        for i in range(10):
            buf.add(str(i))
        msgs = [msg for _ts, msg in buf.entries()]
        assert msgs == ["7", "8", "9"]

    def test_subscribe_receives_snapshot(self):
        buf = LogBuffer()
        received = []
        buf.subscribe(lambda entries: received.append(list(entries)))
        assert received == [[]]
        buf.add("uno")
        assert [msg for _ts, msg in received[-1]] == ["uno"]

    def test_max_entries_cannot_be_zero(self):
        buf = LogBuffer(max_entries=0)
        buf.add("keep")
        buf.add("overflow")
        assert len(buf.entries()) == 1  # clampeado a 1: nunca se queda "sin límite"
        assert buf.latest() == "overflow"

    def test_timestamp_format(self):
        import re

        buf = LogBuffer()
        buf.add("x")
        ts, msg = buf.entries()[0]
        assert re.fullmatch(r"\d{2}:\d{2}:\d{2}", ts)
        assert msg == "x"

    def test_consecutive_duplicates_are_deduped(self):
        buf = LogBuffer()
        for _ in range(3):
            buf.add("mismo evento")
        msgs = [msg for _ts, msg in buf.entries()]
        assert msgs == ["mismo evento"]

    def test_duplicate_refreshes_timestamp(self):
        buf = LogBuffer()
        buf.add("x")
        first_ts = buf.entries()[0][0]
        buf.add("x")
        ts, msg = buf.entries()[0]
        assert msg == "x"
        assert ts >= first_ts
        assert len(buf.entries()) == 1

    def test_non_consecutive_duplicates_are_kept(self):
        buf = LogBuffer()
        buf.add("a")
        buf.add("b")
        buf.add("a")
        assert [msg for _ts, msg in buf.entries()] == ["a", "b", "a"]


class TestWriteDiagnostic:
    """Bitácora forense (archivo aparte, no visible en la UI)."""

    def test_writes_timestamped_line_with_thread(self, tmp_path, monkeypatch):
        import threading

        path = tmp_path / "diagnostics.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", path)
        write_diagnostic("RENDER_FAILED probe")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert lines[0].endswith("] [MainThread] RENDER_FAILED probe")
        assert lines[0].startswith("[20")  # timestamp ISO con año

    def test_appends_multiple_lines(self, tmp_path, monkeypatch):
        path = tmp_path / "diagnostics.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", path)
        write_diagnostic("a")
        write_diagnostic("b")
        assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 2

    def test_rotates_when_file_too_large(self, tmp_path, monkeypatch):
        path = tmp_path / "diagnostics.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", path)
        monkeypatch.setattr(log_mod, "DIAG_LOG_MAX_BYTES", 200)
        write_diagnostic("x" * 300)  # supera el límite
        write_diagnostic("segunda")
        content = path.read_text(encoding="utf-8")
        assert content.endswith("] [MainThread] segunda\n")
        assert "x" * 300 not in content  # la primera línea se truncó

    def test_never_raises_on_bad_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", Path("Z:/inexistente/dir/debug.log"))
        write_diagnostic("no debe romper")  # sin excepción


class TestSanitizeMessage:
    """Tests para _sanitize_message (sanitización de paths en bitácora)."""

    def test_single_path_hashed(self):
        from blip_eraser.utils.log import _sanitize_message
        msg = _sanitize_message("AUDIT action=remove_system paths=/var/log/a result=success")
        # Formato: path#hash (path original + # + hash de 16 chars hex)
        assert "paths=/var/log/a#" in msg
        import re
        assert re.search(r"paths=/var/log/a#[0-9a-f]{16}", msg)

    def test_multiple_paths_comma_separated_all_hashed(self):
        from blip_eraser.utils.log import _sanitize_message
        msg = _sanitize_message("AUDIT action=remove_system paths=/var/log/a,/var/log/b result=success")
        # Ambas rutas deben estar hasheadas (formato path#hash)
        import re
        hashes = re.findall(r"#[0-9a-f]{16}", msg)
        assert len(hashes) == 2

    def test_mixed_path_and_target_both_hashed(self):
        from blip_eraser.utils.log import _sanitize_message
        msg = _sanitize_message("paths=/home/user/file,target=/etc/passwd")
        assert msg.count("#") == 2
        import re
        hashes = re.findall(r"#[0-9a-f]{16}", msg)
        assert len(hashes) == 2

    def test_already_hashed_not_double_hashed(self):
        from blip_eraser.utils.log import _sanitize_message
        # Ya tiene hash válido (16 chars hex)
        msg = _sanitize_message("paths=/var/log/a#a1b2c3d4e5f67890")
        assert msg.count("#") == 1  # no doble hash
        assert msg == "paths=/var/log/a#a1b2c3d4e5f67890"


class TestFilePermissions:
    """Tests para permisos 600 en bitácora forense."""

    def test_write_diagnostic_creates_file_with_600(self, tmp_path, monkeypatch):
        import stat
        import os
        path = tmp_path / "diagnostics.log"
        monkeypatch.setattr(log_mod, "DIAG_LOG_PATH", path)
        write_diagnostic("test")
        # Verificar permisos 600 (owner rw only) - solo en POSIX
        if os.name == "posix":
            mode = path.stat().st_mode
            assert stat.S_IMODE(mode) == 0o600
        else:
            # En Windows, verificar que el archivo existe y se escribió
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "test" in content


class TestIsPathDeniedInHome:
    """Tests para denylist de $HOME en privileges.py."""

    def test_ssh_directory_rejected(self, tmp_path, monkeypatch):
        import blip_eraser.utils.privileges as priv
        # Mock home
        home = tmp_path / "home"
        home.mkdir()
        ssh_dir = home / ".ssh"
        ssh_dir.mkdir()
        (ssh_dir / "id_rsa").write_text("fake")
        monkeypatch.setattr(Path, "home", lambda: home)
        assert priv._is_path_denied_in_home(ssh_dir / "id_rsa") is True
        assert priv._is_path_denied_in_home(ssh_dir) is True

    def test_gnupg_directory_rejected(self, tmp_path, monkeypatch):
        import blip_eraser.utils.privileges as priv
        home = tmp_path / "home"
        home.mkdir()
        gnupg = home / ".gnupg"
        gnupg.mkdir()
        (gnupg / "pubring.gpg").write_text("fake")
        monkeypatch.setattr(Path, "home", lambda: home)
        assert priv._is_path_denied_in_home(gnupg / "pubring.gpg") is True

    def test_config_directory_rejected(self, tmp_path, monkeypatch):
        import blip_eraser.utils.privileges as priv
        home = tmp_path / "home"
        home.mkdir()
        config = home / ".config"
        config.mkdir()
        (config / "app.conf").write_text("fake")
        monkeypatch.setattr(Path, "home", lambda: home)
        assert priv._is_path_denied_in_home(config / "app.conf") is True

    def test_allowed_home_path_not_rejected(self, tmp_path, monkeypatch):
        import blip_eraser.utils.privileges as priv
        home = tmp_path / "home"
        home.mkdir()
        downloads = home / "Downloads"
        downloads.mkdir()
        (downloads / "archivo.txt").write_text("fake")
        monkeypatch.setattr(Path, "home", lambda: home)
        assert priv._is_path_denied_in_home(downloads / "archivo.txt") is False
