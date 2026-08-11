"""Aviso único de "Permisos de BlipEraser" — lógica pura, sin PyQt6.

Registra si el usuario ya vio el diálogo informativo de permisos. La bandera
se guarda en ~/.config/blip-eraser/settings.json bajo `permissions_notice_shown`.
La lectura/escritura es best-effort y se puede redirigir a tmp_path en tests
reaprovechando `i18n.SETTINGS_FILE` (mismo archivo de config).

Este módulo NO crea ventanas: solo decide si debe mostrarse el aviso y marca
que ya se vio. El widget (GUI) consume `should_show_permissions_notice()` y
reutiliza el mismo texto desde Configuración / Ayuda sin duplicar contenido.
"""

from __future__ import annotations

import json

from blip_eraser.utils import i18n

PERMISSIONS_KEY = "permissions_notice_shown"


def _settings_file():
    """Ruta de settings.json, resuelta en el momento de uso (monkeypachable)."""
    return i18n.SETTINGS_FILE


def should_show_permissions_notice() -> bool:
    """True si el usuario aún NO ha visto el aviso de permisos.

    Ausencia de la clave o archivo inexistente => True (primera ejecución).
    """
    data = i18n._read_settings_file()
    return not bool(data.get(PERMISSIONS_KEY, False))


def mark_permissions_notice_shown() -> None:
    """Persiste la bandera para no volver a mostrar el aviso. Best-effort."""
    try:
        data = i18n._read_settings_file()
        data[PERMISSIONS_KEY] = True
        settings = _settings_file()
        settings.parent.mkdir(parents=True, exist_ok=True)
        with open(settings, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    except OSError:
        pass