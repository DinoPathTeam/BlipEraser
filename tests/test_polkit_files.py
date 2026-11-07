"""Coherencia de los archivos de polkit y del instalador automático."""

import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock

from blip_eraser.utils import phase2_installer as p2

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "packaging" / "polkit" / "com.dinopath.blip-eraser.policy"
RULES = ROOT / "packaging" / "polkit" / "49-blip-eraser.rules"


def _actions():
    out = {}
    for a in ET.parse(POLICY).getroot().iter("action"):
        notes = {n.get("key"): n.text for n in a.iter("annotate")}
        out[a.get("id")] = notes
    return out


def test_every_rules_action_exists_in_policy_and_vice_versa():
    text = RULES.read_text()
    in_rules = {i for i in _actions() if f'"{i}"' in text}
    assert in_rules == set(_actions())


def test_uninstall_command_matches_pacman_remove_annotations():
    # pkexec elige la acción por exec.path/argv1/argv2: si el comando real
    # cambia y esto no, el aviso de polkit dejaría de ser el nuestro.
    from blip_eraser.utils import dbus_client
    notes = _actions()["com.dinopath.blip-eraser.pacman-remove"]
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return MagicMock(returncode=0, stdout="", stderr="")

    import subprocess
    orig = subprocess.run
    subprocess.run = fake_run
    try:
        dbus_client.PrivilegedAPI(prefer_daemon=False).remove_packages(["foo"], noconfirm=True)
    finally:
        subprocess.run = orig
    cmd = captured["cmd"]
    i = cmd.index("pkexec")
    assert notes["org.freedesktop.policykit.exec.path"].endswith("/" + cmd[i + 1])
    assert notes["org.freedesktop.policykit.exec.argv1"] == cmd[i + 2]
    assert notes["org.freedesktop.policykit.exec.argv2"] == cmd[i + 3]


class TestInstallerCopiesRules:
    def _patch(self, monkeypatch, tmp_path, root):
        copied = []
        monkeypatch.setattr(p2, "check_root", lambda: root)
        monkeypatch.setattr(p2, "POLKIT_POLICY_DEST", tmp_path / "actions" / "p.policy")
        monkeypatch.setattr(p2, "POLKIT_RULES_DEST", tmp_path / "rules.d" / "49.rules")
        monkeypatch.setattr(p2.shutil, "copy2", lambda s, d: copied.append((Path(s).name, Path(d))))
        return copied

    def test_root_copies_policy_and_rules(self, monkeypatch, tmp_path):
        copied = self._patch(monkeypatch, tmp_path, True)
        ok, _ = p2.install_polkit_policy()
        assert ok
        assert {name for name, _ in copied} == {
            "com.dinopath.blip-eraser.policy", "49-blip-eraser.rules",
        }

    def test_non_root_uses_pkexec_for_both(self, monkeypatch, tmp_path):
        self._patch(monkeypatch, tmp_path, False)
        calls = []
        monkeypatch.setattr(p2.subprocess, "run", lambda cmd, **k: calls.append(cmd) or MagicMock(returncode=0))
        ok, _ = p2.install_polkit_policy()
        assert ok
        cps = [c for c in calls if c[:2] == ["pkexec", "cp"]]
        assert len(cps) == 2
        assert any(str(p2.POLKIT_RULES_SRC) in c for c in cps)

    def test_missing_rules_reported_as_not_installed(self, monkeypatch, tmp_path):
        monkeypatch.setattr(p2, "POLKIT_RULES_DEST", tmp_path / "absent.rules")
        ok, missing = p2.check_daemon_installed()
        assert not ok and "Reglas Polkit" in missing
