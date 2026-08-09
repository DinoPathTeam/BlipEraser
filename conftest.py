"""Configuración de pytest: permite importar `blip_eraser` sin instalarlo."""

import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))