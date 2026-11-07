"""Tests para utils/performance.py — lógica de tweaks de rendimiento."""

from unittest.mock import MagicMock

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
    _install_pkg_via_pkexec,
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


class TestRootFileBackup:
    """D4: copia .blip-bak antes de escribir, restaura al desactivar."""

    def test_write_calls_backup_first(self, monkeypatch):
        from pathlib import Path as _Path

        import blip_eraser.utils.performance as perf

        order = []
        monkeypatch.setattr(
            perf, "_backup_root_file", lambda p: order.append(("backup", str(p)))
        )

        def fake_run(cmd, **kwargs):
            order.append(("write", cmd[0]))
            mock = MagicMock()
            mock.returncode = 0
            return mock

        monkeypatch.setattr(perf.subprocess, "run", fake_run)
        assert perf._write_root_file(_Path("/etc/x.conf"), "data") is True
        assert order[0][0] == "backup"
        assert order[0][1].endswith("/etc/x.conf")

    def test_remove_restores_backup(self, monkeypatch):
        from pathlib import Path as _Path

        import blip_eraser.utils.performance as perf

        cmds = []

        def fake_run(cmd, **kwargs):
            cmds.append(cmd)
            mock = MagicMock()
            mock.returncode = 0
            return mock

        monkeypatch.setattr(perf, "_run_cmd", fake_run)
        assert perf._remove_root_file(_Path("/etc/x.conf")) is True
        shell = " ".join(cmds[0])
        assert "mv -f" in shell
        assert "x.conf.blip-bak" in shell


class TestTweakRegistry:
    """Tests del registro de tweaks."""

    def test_all_tweaks_registered(self):
        assert set(TWEAKS) == {
            "perf_trim_mounts", "perf_compress_ram", "perf_zswap", "perf_mirror_sort",
        }

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
        monkeypatch.setattr("blip_eraser.utils.performance._blip_zram_config_exists", lambda: True)
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

    def test_check_state_ignores_mirrorlist_header(self, monkeypatch):
        monkeypatch.setattr("blip_eraser.utils.performance._systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr("blip_eraser.utils.performance.Path.read_text", lambda self: "Server = ...")
        assert tweak_reflector_check_state() is True

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

class TestSystemManagedProtections:
    """Los tweaks no deben pisar configuración gestionada por la distro."""

    CACHY_MIRRORLIST = "# STARTED AT: 2026-11-01\n# VERSION: 0.33.0\nServer = https://x/$repo\n"

    def test_zram_blocked_when_distro_zram_active(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_zram_device_present", lambda: True)
        monkeypatch.setattr(perf, "_blip_zram_config_exists", lambda: False)
        reason = perf.get_tweak_block_reason("perf_compress_ram")
        assert reason is not None and reason.code == "system_zram"

    def test_zram_not_blocked_when_it_is_ours(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_zram_device_present", lambda: True)
        monkeypatch.setattr(perf, "_blip_zram_config_exists", lambda: True)
        assert perf.get_tweak_block_reason("perf_compress_ram") is None

    def test_zram_not_blocked_without_any_zram(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_zram_device_present", lambda: False)
        monkeypatch.setattr(perf, "_blip_zram_config_exists", lambda: False)
        assert perf.get_tweak_block_reason("perf_compress_ram") is None

    def test_apply_zram_enable_refused_and_writes_nothing(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_zram_device_present", lambda: True)
        monkeypatch.setattr(perf, "_blip_zram_config_exists", lambda: False)
        calls = []
        monkeypatch.setattr(perf, "_write_root_file", lambda *a, **k: calls.append(a) or True)
        monkeypatch.setattr(perf, "_run_cmd", lambda *a, **k: calls.append(a))
        res = perf.apply_tweak("perf_compress_ram", True)
        assert not res.success and calls == []

    def test_apply_zram_disable_of_foreign_zram_does_nothing(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_zram_device_present", lambda: True)
        monkeypatch.setattr(perf, "_blip_zram_config_exists", lambda: False)
        calls = []
        monkeypatch.setattr(perf, "_run_cmd", lambda *a, **k: calls.append(a))
        res = perf.apply_tweak("perf_compress_ram", False)
        assert not res.success and calls == []

    def test_zram_state_false_for_distro_zram(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_blip_zram_config_exists", lambda: False)
        monkeypatch.setattr(perf, "_systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr(perf, "_systemctl_is_active", lambda u: True)
        assert perf.tweak_zram_check_state() is False

    def test_mirrors_blocked_when_other_tool_manages_them(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_read_mirrorlist", lambda: self.CACHY_MIRRORLIST)
        reason = perf.get_tweak_block_reason("perf_mirror_sort")
        assert reason is not None and reason.code == "system_mirrors"

    def test_mirrors_not_blocked_for_plain_mirrorlist(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_read_mirrorlist", lambda: "Server = https://x/$repo\n")
        assert perf.get_tweak_block_reason("perf_mirror_sort") is None

    def test_apply_reflector_enable_refused_and_writes_nothing(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_read_mirrorlist", lambda: self.CACHY_MIRRORLIST)
        calls = []
        monkeypatch.setattr(perf, "_write_root_file", lambda *a, **k: calls.append(a) or True)
        monkeypatch.setattr(perf, "_run_cmd", lambda *a, **k: calls.append(a))
        res = perf.apply_tweak("perf_mirror_sort", True)
        assert not res.success and calls == []

    def test_reflector_state_does_not_depend_on_header(self, monkeypatch):
        from blip_eraser.utils import performance as perf
        monkeypatch.setattr(perf, "_systemctl_is_enabled", lambda u: True)
        monkeypatch.setattr(perf, "_read_mirrorlist", lambda: "Server = https://x/$repo\n")
        assert perf.tweak_reflector_check_state() is True

    def test_trim_has_no_block(self):
        from blip_eraser.utils import performance as perf
        assert perf.get_tweak_block_reason("perf_trim_mounts") is None


class TestZswapTweak:
    """zswap: opcional, persistente vía tmpfiles.d, excluyente con zram."""

    @pytest.fixture
    def perf(self, monkeypatch):
        from blip_eraser.utils import performance as p
        monkeypatch.setattr(p, "_zswap_supported", lambda: True)
        monkeypatch.setattr(p, "_zswap_enabled", lambda: False)
        monkeypatch.setattr(p, "_blip_zswap_config_exists", lambda: False)
        monkeypatch.setattr(p, "_swap_devices", lambda: ["/dev/nvme0n1p3"])
        return p

    def test_registered_as_tweak(self):
        assert "perf_zswap" in TWEAKS

    def test_no_block_with_disk_swap(self, perf):
        assert perf.get_tweak_block_reason("perf_zswap") is None

    def test_blocked_when_zram_swap_active(self, perf, monkeypatch):
        monkeypatch.setattr(perf, "_swap_devices", lambda: ["/dev/zram0"])
        b = perf.get_tweak_block_reason("perf_zswap")
        assert b is not None and b.code == "zram_swap" and b.enable_only

    def test_blocked_without_any_swap(self, perf, monkeypatch):
        monkeypatch.setattr(perf, "_swap_devices", lambda: [])
        b = perf.get_tweak_block_reason("perf_zswap")
        assert b is not None and b.code == "no_swap" and b.enable_only

    def test_blocked_when_kernel_lacks_zswap(self, perf, monkeypatch):
        monkeypatch.setattr(perf, "_zswap_supported", lambda: False)
        b = perf.get_tweak_block_reason("perf_zswap")
        assert b is not None and b.code == "zswap_unsupported" and not b.enable_only

    def test_blocked_when_enabled_by_system(self, perf, monkeypatch):
        monkeypatch.setattr(perf, "_zswap_enabled", lambda: True)
        b = perf.get_tweak_block_reason("perf_zswap")
        assert b is not None and b.code == "system_zswap" and not b.enable_only

    def test_ours_can_still_be_disabled_when_zram_appears(self, perf, monkeypatch):
        monkeypatch.setattr(perf, "_zswap_enabled", lambda: True)
        monkeypatch.setattr(perf, "_blip_zswap_config_exists", lambda: True)
        monkeypatch.setattr(perf, "_swap_devices", lambda: ["/dev/zram0"])
        calls = []
        monkeypatch.setattr(perf, "_remove_root_file", lambda p: calls.append(("rm", p)) or True)
        monkeypatch.setattr(perf, "_run_cmd", lambda c, **k: calls.append(("run", c)) or MagicMock(returncode=0))
        res = perf.apply_tweak("perf_zswap", False)
        assert res.success
        assert ("rm", perf.ZSWAP_CONFIG_PATH) in calls

    def test_enable_refused_with_zram_and_writes_nothing(self, perf, monkeypatch):
        monkeypatch.setattr(perf, "_swap_devices", lambda: ["/dev/zram0"])
        calls = []
        monkeypatch.setattr(perf, "_write_root_file", lambda *a, **k: calls.append(a) or True)
        monkeypatch.setattr(perf, "_run_cmd", lambda *a, **k: calls.append(a))
        res = perf.apply_tweak("perf_zswap", True)
        assert not res.success and calls == []

    def test_enable_writes_tmpfiles_and_applies_now(self, perf, monkeypatch):
        written, ran = [], []
        monkeypatch.setattr(perf, "_write_root_file", lambda p, c: written.append((p, c)) or True)
        monkeypatch.setattr(perf, "_run_cmd", lambda c, **k: ran.append(c) or MagicMock(returncode=0))
        res = perf.apply_tweak("perf_zswap", True)
        assert res.success and not res.needs_reboot
        path, content = written[0]
        assert path == perf.ZSWAP_CONFIG_PATH
        assert str(path).startswith("/etc/tmpfiles.d/")
        assert "/sys/module/zswap/parameters/enabled" in content
        assert any("systemd-tmpfiles" in c for c in ran)

    def test_enable_does_not_touch_bootloader(self, perf, monkeypatch):
        ran = []
        monkeypatch.setattr(perf, "_write_root_file", lambda p, c: True)
        monkeypatch.setattr(perf, "_run_cmd", lambda c, **k: ran.append(c) or MagicMock(returncode=0))
        perf.apply_tweak("perf_zswap", True)
        flat = " ".join(" ".join(c) for c in ran)
        for forbidden in ("grub", "limine", "kernel-install", "cmdline", "mkinitcpio"):
            assert forbidden not in flat

    def test_state_requires_our_config_and_enabled(self, perf, monkeypatch):
        assert perf.tweak_zswap_check_state() is False
        monkeypatch.setattr(perf, "_zswap_enabled", lambda: True)
        assert perf.tweak_zswap_check_state() is False  # activo pero del sistema
        monkeypatch.setattr(perf, "_blip_zswap_config_exists", lambda: True)
        assert perf.tweak_zswap_check_state() is True

    def test_swap_devices_parses_proc_swaps(self, monkeypatch, tmp_path):
        from blip_eraser.utils import performance as p
        f = tmp_path / "swaps"
        f.write_text("Filename\tType\tSize\tUsed\tPriority\n/dev/zram0\tpartition\t1\t0\t100\n")
        monkeypatch.setattr(p, "_PROC_SWAPS", f)
        assert p._swap_devices() == ["/dev/zram0"]


class TestTweakTexts:
    KEYS = ("perf_zswap", "perf_zswap_help", "perf_zswap_tip",
            "perf_compress_ram", "perf_compress_ram_help", "perf_compress_ram_tip",
            "perf_block_system_zram", "perf_block_system_mirrors", "perf_block_zram_swap",
            "perf_block_no_swap", "perf_block_zswap_unsupported", "perf_block_system_zswap")

    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_all_keys_present(self, lang):
        from blip_eraser.utils.i18n import TRANSLATIONS
        missing = [k for k in self.KEYS if k not in TRANSLATIONS[lang]]
        assert missing == []

    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_zram_text_no_longer_says_zswap(self, lang):
        from blip_eraser.utils.i18n import TRANSLATIONS
        assert "zswap" not in TRANSLATIONS[lang]["perf_compress_ram"].lower()

    def test_default_pref_off(self):
        from blip_eraser.utils.config import PREFS_DEFAULTS
        assert PREFS_DEFAULTS["perf_zswap"] is False


class TestReconcile:
    """La preferencia guardada es la intención del usuario: no se pierde."""

    def test_intent_on_but_system_off_is_drift_not_overwritten(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        r = reconcile_tweaks({"perf_zswap": True}, {"perf_zswap": False}, set())
        assert r.drifted == ["perf_zswap"]
        assert r.adopt == {}

    def test_in_sync_has_no_drift(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        r = reconcile_tweaks({"perf_zswap": True}, {"perf_zswap": True}, set())
        assert r.drifted == [] and r.adopt == {}

    def test_active_in_system_but_not_in_prefs_is_adopted(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        r = reconcile_tweaks({"perf_trim_mounts": False}, {"perf_trim_mounts": True}, set())
        assert r.adopt == {"perf_trim_mounts": True}
        assert r.drifted == []

    def test_missing_pref_counts_as_off(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        r = reconcile_tweaks({}, {"perf_trim_mounts": True}, set())
        assert r.adopt == {"perf_trim_mounts": True}

    def test_blocked_tweaks_are_ignored(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        r = reconcile_tweaks(
            {"perf_compress_ram": True}, {"perf_compress_ram": False}, {"perf_compress_ram"},
        )
        assert r.drifted == [] and r.adopt == {}

    def test_off_and_off_is_quiet(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        r = reconcile_tweaks({"perf_mirror_sort": False}, {"perf_mirror_sort": False}, set())
        assert r.drifted == [] and r.adopt == {}

    def test_drift_keys_follow_registry_order(self):
        from blip_eraser.utils.performance import reconcile_tweaks
        prefs = {k: True for k in TWEAKS}
        states = {k: False for k in TWEAKS}
        assert reconcile_tweaks(prefs, states, set()).drifted == list(TWEAKS)


class TestDriftTexts:
    @pytest.mark.parametrize("lang", ["es", "en"])
    def test_keys(self, lang):
        from blip_eraser.utils.i18n import TRANSLATIONS
        for k in ("perf_drift_notice", "perf_drift_reapply"):
            assert k in TRANSLATIONS[lang]
