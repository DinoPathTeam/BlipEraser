"""Cada tweak se aplica con UNA sola llamada a pkexec (una sola autorización).

Antes, activar zram podía pedir la contraseña hasta 6 veces seguidas
(instalar, comprobar, respaldar, escribir, daemon-reload, enable). Ahora los
pasos privilegiados se agrupan en un único `pkexec sh -c`. Los fragmentos de
shell se ejecutan de verdad (en un directorio temporal) para comprobar su
comportamiento, no solo su texto.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import blip_eraser.utils.performance as perf


def _sh(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", "-c", "set -e\n" + script], capture_output=True, text=True
    )


# ─── Fragmentos de shell: comportamiento real ─────────────────────────────

class TestShellFragments:
    def test_write_creates_file_without_backup_when_new(self, tmp_path: Path):
        f = tmp_path / "x.conf"
        r = _sh(perf._sh_write_file(f, "uno\ndos 'q' $HOME\n"))
        assert r.returncode == 0, r.stderr
        assert f.read_text() == "uno\ndos 'q' $HOME\n"  # sin expansión ni comillas rotas
        assert not (tmp_path / "x.conf.blip-bak").exists()

    def test_write_backs_up_existing_once(self, tmp_path: Path):
        f = tmp_path / "x.conf"
        f.write_text("original")
        assert _sh(perf._sh_write_file(f, "nuevo1")).returncode == 0
        assert (tmp_path / "x.conf.blip-bak").read_text() == "original"
        # Segunda escritura: NO pisa la copia previa (primera escritura manda).
        assert _sh(perf._sh_write_file(f, "nuevo2")).returncode == 0
        assert f.read_text() == "nuevo2"
        assert (tmp_path / "x.conf.blip-bak").read_text() == "original"

    def test_remove_restores_backup(self, tmp_path: Path):
        f = tmp_path / "x.conf"
        (tmp_path / "x.conf.blip-bak").write_text("original")
        f.write_text("de blip")
        assert _sh(perf._sh_remove_file(f)).returncode == 0
        assert f.read_text() == "original"
        assert not (tmp_path / "x.conf.blip-bak").exists()

    def test_remove_deletes_when_no_backup(self, tmp_path: Path):
        f = tmp_path / "x.conf"
        f.write_text("de blip")
        assert _sh(perf._sh_remove_file(f)).returncode == 0
        assert not f.exists()

    def test_remove_is_noop_when_missing(self, tmp_path: Path):
        assert _sh(perf._sh_remove_file(tmp_path / "nada.conf")).returncode == 0

    def test_paths_with_spaces_and_quotes_are_safe(self, tmp_path: Path):
        f = tmp_path / "a b'c.conf"
        assert _sh(perf._sh_write_file(f, "ok")).returncode == 0
        assert f.read_text() == "ok"


# ─── Una sola llamada a pkexec por tweak ──────────────────────────────────

@pytest.fixture
def calls(monkeypatch):
    log: list[list[str]] = []

    def fake_run(cmd, check=True):
        log.append(list(cmd))
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(perf, "_run_cmd", fake_run)
    monkeypatch.setattr(perf, "_pkg_installed", lambda p: False)
    return log


def _pkexec_calls(log):
    return [c for c in log if c and c[0] == "pkexec"]


def _script(log) -> str:
    (call,) = _pkexec_calls(log)
    assert call[:3] == ["pkexec", "sh", "-c"], call
    return call[3]


@pytest.mark.parametrize(
    "apply",
    [
        perf.tweak_trim_apply,
        perf.tweak_zram_apply,
        perf.tweak_zswap_apply,
        perf.tweak_reflector_apply,
    ],
)
@pytest.mark.parametrize("enable", [True, False])
def test_exactly_one_pkexec_call(calls, apply, enable):
    result = apply(enable)
    assert result.success, result.message
    assert len(_pkexec_calls(calls)) == 1, calls


def test_zram_enable_script_contents(calls):
    result = perf.tweak_zram_apply(True)
    assert result.installed_deps is True
    script = _script(calls)
    assert "pacman -S --needed --noconfirm zram-generator" in script
    assert "zram-generator.conf" in script and "zstd" in script
    assert "systemctl daemon-reload" in script
    assert "systemctl enable --now" in script
    # orden: instalar -> escribir -> recargar -> habilitar
    order = [
        script.index("pacman -S"),
        script.index("printf"),
        script.index("daemon-reload"),
        script.index("enable --now"),
    ]
    assert order == sorted(order)


def test_zram_enable_skips_install_when_present(calls, monkeypatch):
    monkeypatch.setattr(perf, "_pkg_installed", lambda p: True)
    result = perf.tweak_zram_apply(True)
    assert result.installed_deps is False
    assert "pacman -S" not in _script(calls)


def test_zram_disable_script_contents(calls):
    perf.tweak_zram_apply(False)
    script = _script(calls)
    assert script.index("disable --now") < script.index("daemon-reload")
    assert "zram-generator.conf" in script


def test_zswap_enable_reverts_config_inside_script(calls):
    perf.tweak_zswap_apply(True)
    script = _script(calls)
    assert "systemd-tmpfiles --create" in script
    # Si tmpfiles falla, el propio script deshace la config (sin 2.º pkexec).
    assert "||" in script and "blip-eraser-zswap.conf" in script


def test_zswap_disable_script_contents(calls):
    perf.tweak_zswap_apply(False)
    script = _script(calls)
    assert "/sys/module/zswap/parameters/enabled" in script
    assert "blip-eraser-zswap.conf" in script


def test_reflector_enable_script_contents(calls):
    result = perf.tweak_reflector_apply(True)
    assert result.installed_deps is True
    script = _script(calls)
    assert "pacman -S --needed --noconfirm reflector" in script
    assert "mkdir -p" in script and "reflector.conf" in script
    assert "enable --now" in script


def test_reflector_disable_tolerates_non_empty_dir(calls):
    perf.tweak_reflector_apply(False)
    script = _script(calls)
    assert "rmdir" in script and "|| true" in script


# ─── Errores ──────────────────────────────────────────────────────────────

def test_failure_reports_stderr_and_installed_deps(monkeypatch):
    def fake_run(cmd, check=True):
        raise subprocess.CalledProcessError(1, cmd, stderr="boom\n")

    monkeypatch.setattr(perf, "_run_cmd", fake_run)
    # No estaba instalado antes; tras el fallo sí lo está (pacman llegó a correr).
    seq = iter([False, True])
    monkeypatch.setattr(perf, "_pkg_installed", lambda p: next(seq))
    result = perf.tweak_zram_apply(True)
    assert result.success is False
    assert "boom" in result.message
    assert result.installed_deps is True


def test_missing_pkexec_is_a_clean_failure(monkeypatch):
    def fake_run(cmd, check=True):
        raise FileNotFoundError("pkexec")

    monkeypatch.setattr(perf, "_run_cmd", fake_run)
    monkeypatch.setattr(perf, "_pkg_installed", lambda p: True)
    result = perf.tweak_zswap_apply(True)
    assert result.success is False
    assert "pkexec" in result.message.lower()


def test_quote_helper_is_shlex():
    assert perf._q("a b") == shlex.quote("a b")


@pytest.mark.parametrize(
    "apply",
    [perf.tweak_zram_apply, perf.tweak_zswap_apply, perf.tweak_reflector_apply],
)
@pytest.mark.parametrize("enable", [True, False])
def test_generated_scripts_are_valid_sh(calls, apply, enable):
    apply(enable)
    r = subprocess.run(["sh", "-n", "-c", _script(calls)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_zswap_rollback_restores_original_on_failure(tmp_path: Path):
    """Si tmpfiles falla, el script deja el archivo como estaba (ejecución real)."""
    f = tmp_path / "z.conf"
    f.write_text("original")
    script = (
        perf._sh_write_file(f, "nuevo\n")
        + f"\nfalse || {{ {perf._sh_remove_file(f)}; exit 1; }}"
    )
    r = _sh(script)
    assert r.returncode == 1
    assert f.read_text() == "original"
    assert not (tmp_path / "z.conf.blip-bak").exists()
