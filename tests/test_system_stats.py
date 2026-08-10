"""Tests para utils/system_stats.py (métricas, sin /proc en Windows)."""

import pytest

from blip_eraser.utils import system_stats as stats


class TestCpu:
    def test_sample_invalid_returns_none(self, monkeypatch):
        monkeypatch.setattr(stats, "_read_lines", lambda p: None)
        assert stats.read_cpu_sample() is None

    def test_sample_parses_total_and_idle(self, monkeypatch):
        monkeypatch.setattr(
            stats, "_read_lines",
            lambda p: ["cpu  100 10 30 200 30 0 0 0 0 0"],
        )
        result = stats.read_cpu_sample()
        assert result == (370, 230)  # total=sum, idle=idle+iowait

    def test_cpu_usage_percent_zero_when_all_idle(self):
        prev = (1000, 700)
        curr = (2000, 1700)  # todo el delta es idle → 0%
        assert stats.cpu_usage_percent(prev, curr) == 0

    def test_cpu_usage_percent_50(self):
        prev = (1000, 800)
        curr = (1000 + 200, 800 + 100)  # 100 idle de 200 total → 50%
        assert stats.cpu_usage_percent(prev, curr) == 50

    def test_cpu_usage_clamps(self):
        assert stats.cpu_usage_percent((0, 0), (10, 0)) == 100
        assert stats.cpu_usage_percent((0, 0), (10, 1000)) == 0

    def test_cpu_usage_missing_samples(self):
        assert stats.cpu_usage_percent(None, (1, 1)) is None
        assert stats.cpu_usage_percent((1, 1), None) is None
        assert stats.cpu_usage_percent((1, 1), (1, 1)) is None  # sin delta


class TestMemory:
    def test_meminfo_parses(self, monkeypatch):
        lines = [
            "MemTotal:       16384000 kB",
            "MemAvailable:    4096000 kB",
            "SwapTotal:            0 kB",
        ]
        monkeypatch.setattr(stats, "_read_lines", lambda p: lines)
        usage = stats.memory_usage_percent()
        assert usage == 75  # 1 - (4096000/16384000)

    def test_meminfo_missing_returns_none(self, monkeypatch):
        monkeypatch.setattr(stats, "_read_lines", lambda p: None)
        assert stats.memory_usage_percent() is None

    def test_meminfo_incomplete_returns_none(self, monkeypatch):
        monkeypatch.setattr(stats, "_read_lines", lambda p: ["MemTotal: 100 kB"])
        assert stats.memory_usage_percent() is None


class TestDisk:
    def test_disk_usage_percent(self, monkeypatch):
        class FakeUsage:
            total = 100
            used = 45

        monkeypatch.setattr(stats.shutil, "disk_usage", lambda path: FakeUsage())
        assert stats.disk_usage_percent("/") == 45

    def test_disk_usage_error_returns_none(self, monkeypatch):
        def boom(path):
            raise PermissionError

        monkeypatch.setattr(stats.shutil, "disk_usage", boom)
        assert stats.disk_usage_percent("/") is None

    def test_disk_total_zero_returns_none(self, monkeypatch):
        class FakeUsage:
            total = 0
            used = 0

        monkeypatch.setattr(stats.shutil, "disk_usage", lambda path: FakeUsage())
        assert stats.disk_usage_percent("/") is None


class TestReadLines:
    def test_existing_file(self, tmp_path):
        file = tmp_path / "data.txt"
        file.write_text("a\nb\n", encoding="utf-8")
        assert stats._read_lines(file) == ["a", "b"]

    def test_missing_file(self):
        assert stats._read_lines(stats._CPU_STAT.parent / "no-tale") is None


class TestCpuModel:
    def test_reads_model_name(self, monkeypatch):
        lines = ["processor : 0", "model name : AMD Ryzen 5", "processor : 1"]
        monkeypatch.setattr(stats, "_read_lines", lambda p: lines)
        assert stats.cpu_model() == "AMD Ryzen 5"

    def test_missing_returns_none(self, monkeypatch):
        monkeypatch.setattr(stats, "_read_lines", lambda p: None)
        assert stats.cpu_model() is None


class TestGpuModel:
    def test_reads_from_lspci(self, monkeypatch):
        fake_out = "00:02.0 VGA compatible controller: Intel UHD\n00:01.0 Audio: X"
        fake = type("R", (), {"stdout": fake_out})
        monkeypatch.setattr(stats.subprocess, "run", lambda *a, **k: fake())
        assert stats.gpu_model() == "Intel UHD"

    def test_lspci_missing_returns_none(self, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError

        monkeypatch.setattr(stats.subprocess, "run", boom)
        assert stats.gpu_model() is None

    def test_lspci_no_gpu_line_returns_none(self, monkeypatch):
        fake = type("R", (), {"stdout": "00:00.0 Host bridge: Example"})
        monkeypatch.setattr(stats.subprocess, "run", lambda *a, **k: fake())
        assert stats.gpu_model() is None


class TestRamTotal:
    def test_reads_memtotal(self, monkeypatch):
        monkeypatch.setattr(stats, "_read_lines", lambda p: ["MemTotal: 16384000 kB"])
        assert stats.ram_total_bytes() == 16384000 * 1024

    def test_missing_returns_none(self, monkeypatch):
        monkeypatch.setattr(stats, "_read_lines", lambda p: None)
        assert stats.ram_total_bytes() is None


class TestDiskTotal:
    def test_reads_total(self, monkeypatch):
        class FakeUsage:
            total = 512_000_000_000
            used = 1

        monkeypatch.setattr(stats.shutil, "disk_usage", lambda path: FakeUsage())
        assert stats.disk_total_bytes("/") == 512_000_000_000

    def test_error_returns_none(self, monkeypatch):
        def boom(path):
            raise PermissionError

        monkeypatch.setattr(stats.shutil, "disk_usage", boom)
        assert stats.disk_total_bytes("/") is None