"""Pruebas opt-in contra el daemon privilegiado real de systemd/D-Bus.

No se ejecutan por defecto: requieren Arch/Linux, el servicio instalado y
acceso autorizado al bus de sistema.
"""

import os
import platform
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from blip_eraser.utils.dbus_client import PrivilegedClient


pytestmark = pytest.mark.skipif(
    platform.system() != "Linux"
    or os.environ.get("BLIP_ERASER_RUN_DAEMON_INTEGRATION") != "1",
    reason="requiere Linux y BLIP_ERASER_RUN_DAEMON_INTEGRATION=1",
)


@pytest.fixture(scope="module")
def client() -> "PrivilegedClient":
    from blip_eraser.utils.dbus_client import PrivilegedClient

    instance = PrivilegedClient()
    if not instance.is_available():
        pytest.fail(
            "El daemon D-Bus no está disponible; comprueba "
            "systemctl status blip-eraser-privileged.service"
        )
    return instance


def test_daemon_ping(client: "PrivilegedClient") -> None:
    """El servicio responde al health-check sobre el bus de sistema."""
    assert client.ping() is True


def test_daemon_rejects_disallowed_path(client: "PrivilegedClient") -> None:
    """La validación del daemon rechaza rutas fuera de su allowlist."""
    from blip_eraser.utils.dbus_client import DBusError

    with pytest.raises(DBusError):
        client.clean_system_paths(["/etc/passwd"])


def test_daemon_rejects_unknown_package(client: "PrivilegedClient") -> None:
    """La validación del daemon rechaza nombres de paquete no instalados."""
    from blip_eraser.utils.dbus_client import DBusError

    with pytest.raises(DBusError):
        client.remove_packages(["__blip_eraser_integration_package_must_not_exist__"])
