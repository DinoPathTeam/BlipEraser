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
