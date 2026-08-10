"""Tests para utils/log.py (buffer de registro, sin PyQt6)."""

from blip_eraser.utils.log import LogBuffer


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
