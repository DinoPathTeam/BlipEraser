"""Pruebas estáticas del wrapper instalado del daemon."""

from pathlib import Path


WRAPPER = (
    Path(__file__).parent.parent
    / "packaging"
    / "scripts"
    / "blip-eraser-privileged"
)


def test_wrapper_bootstraps_its_install_directory_before_import():
    source = WRAPPER.read_text(encoding="utf-8")
    path_setup = "sys.path.insert(0, INSTALL_ROOT)"
    import_line = "from blip_eraser.daemon.privileged_daemon import main"

    assert path_setup in source
    assert source.index(path_setup) < source.index(import_line)
