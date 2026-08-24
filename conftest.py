"""Configuración de pytest: permite importar `blip_eraser` sin instalarlo."""

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _reset_pacman_cache():
    """Resetea la caché de pacman antes de cada test para evitar contaminación entre tests.

    En entornos con pacman real (WSL/Arch), algún test puede disparar la carga
    real de la caché y quedar pegada para el resto de la sesión.
    """
    from blip_eraser.utils.pacman import reset_package_cache_state
    reset_package_cache_state()
    yield
    reset_package_cache_state()