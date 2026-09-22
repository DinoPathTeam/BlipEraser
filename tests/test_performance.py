"""Tests para utils/performance.py — lógica de tweaks de rendimiento."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blip_eraser.utils.performance import (
    TWEAKS,
    TweakResult,
    check_tweak_state,
    apply_tweak,
    get_all_tweak_states,
    get_tweak_info,
    _pkg_installed,
    _systemctl_is_enabled,
    _systemctl_is_active,
    _install_pkg_via_pkexec,
    _write_root_file,
    _remove_root_file,
    tweak_trim_check_state,
    tweak_trim_apply,
    tweak_zram_check_state,
    tweak_zram_apply,
    tweak_reflector_check_state,
    tweak_reflector_apply,
)


class TestUtils:
    """Tests de funciones utilitarias internas."""

    def test_pkg_installed_true(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            assert cmd[:2] == ["pacman", "-Q"]
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        assert _pkg_installed("zram-generator") is True

    def test_pkg_installed_false(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        import subprocess
        assert _pkg_installed("nonexistent-pkg") is False

    def test_systemctl_is_enabled_true(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            assert cmd[:2] == ["systemctl", "is-enabled"]
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        assert _systemctl_is_enabled("fstrim.timer") is True

    def test_systemctl_is_enabled_false(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd)
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        import subprocess
        assert _systemctl_is_enabled("fstrim.timer") is False

    def test_install_pkg_uses_pacman_S_only(self, monkeypatch):
        """Instalar NO debe desinstalar antes: solo `pacman -S` (regresión P1)."""
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            mock = MagicMock()
            mock.returncode = 0
            return mock

        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        assert _install_pkg_via_pkexec("reflector") is True
        assert calls == [["pkexec", "pacman", "-S", "--needed", "--noconfirm", "reflector"]]


class TestTweakRegistry:
    """Tests del registro de tweaks."""

    def test_all_three_tweaks_registered(self):
        assert "perf_trim_mounts" in TWEAKS
        assert "perf_compress_ram" in TWEAKS
        assert "perf_mirror_sort" in TWEAKS
        assert len(TWEAKS) == 3

    def test_each_tweak_has_required_fields(self):
        for key, info in TWEAKS.items():
            assert "check" in info
            assert "apply" in info
            assert "deps" in info
            assert "friendly_name" in info
            assert callable(info["check"])
            assert callable(info["apply"])
            assert isinstance(info["deps"], list)
            assert isinstance(info["friendly_name"], str)

    def test_get_tweak_info(self):
        info = get_tweak_info("perf_trim_mounts")
        assert info is not None
        assert info["friendly_name"] == "TRIM periódico (SSD/NVMe)"
        
        assert get_tweak_info("unknown") is None


class TestTweakTrim:
    """Tests para tweak TRIM (fstrim.timer)."""

    def test_check_state_enabled(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: True)
        assert tweak_trim_check_state() is True

    def test_check_state_disabled(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: False)
        assert tweak_trim_check_state() is False

    def test_apply_enable_success(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            assert cmd[:3] == ["pkexec", "systemctl", "enable"]
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        
        result = tweak_trim_apply(True)
        assert result.success is True
        assert "activado" in result.message.lower()

    def test_apply_disable_success(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            assert cmd[:3] == ["pkexec", "systemctl", "disable"]
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        
        result = tweak_trim_apply(False)
        assert result.success is True
        assert "desactivado" in result.message.lower()

    def test_apply_failure(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise subprocess.CalledProcessError(1, cmd, stderr="permission denied")
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        import subprocess
        
        result = tweak_trim_apply(True)
        assert result.success is False
        assert "error" in result.message.lower()


class TestTweakZram:
    """Tests para tweak compresión RAM (zram-generator)."""

    def test_check_state_enabled_and_active(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_active", lambda u: True)
        assert tweak_zram_check_state() is True

    def test_check_state_enabled_but_inactive(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_active", lambda u: False)
        assert tweak_zram_check_state() is False

    def test_apply_enable_installs_dep_and_config(self, monkeypatch):
        # Mock: zram-generator no instalado
        monkeypatch.setattr("blip_eraser.utils.performance._pkg_installed", lambda p: False)
        
        # Mock: _install_pkg_via_pkexec éxito
        def mock_install(pkg):
            assert pkg == "zram-generator"
            return True
        monkeypatch.setattr("blip_eraser.utils.performance._install_pkg_via_pkexec", mock_install)
        
        # Mock: _write_root_file éxito
        def mock_write(path, content):
            assert "zram-generator.conf" in str(path)
            assert "zram-size" in content
            assert "zstd" in content
            return True
        monkeypatch.setattr("blip_eraser.utils.performance._write_root_file", mock_write)
        
        # Mock: systemctl daemon-reload y enable
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        
        result = tweak_zram_apply(True)
        assert result.success is True
        assert result.installed_deps is True
        assert "activada" in result.message.lower()

    def test_apply_enable_install_fails(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._pkg_installed", lambda p: False)
        monkeypatch.setattr("blip_eraser.utils.performance._install_pkg_via_pkexec", lambda p: False)
        
        result = tweak_zram_apply(True)
        assert result.success is False
        assert "instalar" in result.message.lower()

    def test_apply_disable(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        monkeypatch.setattr("blip_eraser.utils.performance._remove_root_file", lambda p: True)
        
        result = tweak_zram_apply(False)
        assert result.success is True
        assert "desactivada" in result.message.lower()


class TestTweakReflector:
    """Tests para tweak espejos (reflector)."""

    def test_check_state_enabled_and_mirrorlist_generated(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr("blip_eraser.utils.performance.Path.read_text", lambda self: "# Generated by reflector\nServer = ...")
        assert tweak_reflector_check_state() is True

    def test_check_state_enabled_but_not_generated(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr("blip_eraser.utils.performance.Path.read_text", lambda self: "Server = ...")
        assert tweak_reflector_check_state() is False

    def test_check_state_disabled(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: False)
        assert tweak_reflector_check_state() is False

    def test_apply_enable_installs_dep_and_config(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._pkg_installed", lambda p: False)
        monkeypatch.setattr("blip_eraser.utils.performance._install_pkg_via_pkexec", lambda p: True)
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", lambda *a, **k: MagicMock(returncode=0))
        monkeypatch.setattr("blip_eraser.utils.performance._write_root_file", lambda p, c: True)
        
        result = tweak_reflector_apply(True)
        assert result.success is True
        assert result.installed_deps is True
        assert "activado" in result.message.lower()

    def test_apply_disable(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            return mock
        monkeypatch.setattr("blip_eraser.utils.performance._run_cmd", mock_run)
        monkeypatch.setattr("blip_eraser.utils.performance._remove_root_file", lambda p: True)
        
        result = tweak_reflector_apply(False)
        assert result.success is True
        assert "desactivado" in result.message.lower()


class TestPublicAPI:
    """Tests de la API pública (check_tweak_state, apply_tweak, get_all_tweak_states)."""

    def test_check_tweak_state_unknown(self):
        assert check_tweak_state("unknown_key") is False

    def test_check_tweak_state_delegates(self, monkeypatch):
        monkeypatch.setitem(TWEAKS["perf_trim_mounts"], "check", lambda: True)
        assert check_tweak_state("perf_trim_mounts") is True

    def test_apply_tweak_unknown(self):
        result = apply_tweak("unknown_key", True)
        assert result.success is False
        assert "desconocido" in result.message.lower()

    def test_apply_tweak_delegates(self, monkeypatch):
        def mock_apply(enable):
            return TweakResult(success=True, message="ok")
        monkeypatch.setitem(TWEAKS["perf_trim_mounts"], "apply", mock_apply)
        
        result = apply_tweak("perf_trim_mounts", True)
        assert result.success is True
        assert result.message == "ok"

    def test_get_all_tweak_states(self, monkeypatch):
        monkeypatch.setitem(TWEAKS["perf_trim_mounts"], "check", lambda: True)
        monkeypatch.setitem(TWEAKS["perf_compress_ram"], "check", lambda: False)
        monkeypatch.setitem(TWEAKS["perf_mirror_sort"], "check", lambda: True)
        
        states = get_all_tweak_states()
        assert states["perf_trim_mounts"] is True
        assert states["perf_compress_ram"] is False
        assert states["perf_mirror_sort"] is True


class TestConfigIntegration:
    """Tests de integración con config (persistencia)."""

    def test_config_defaults_include_perf_keys(self):
        from blip_eraser.utils.config import PREFS_DEFAULTS
        assert "perf_trim_mounts" in PREFS_DEFAULTS
        assert "perf_compress_ram" in PREFS_DEFAULTS
        assert "perf_mirror_sort" in PREFS_DEFAULTS
        assert PREFS_DEFAULTS["perf_trim_mounts"] is False
        assert PREFS_DEFAULTS["perf_compress_ram"] is False
        assert PREFS_DEFAULTS["perf_mirror_sort"] is False