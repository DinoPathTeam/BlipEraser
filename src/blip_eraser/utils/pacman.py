"""Lógica pura para interactuar con pacman / pkexec — sin PyQt6.

Usa solo subprocess para que sea fácil de mockear y testear sin tener
paquetes reales instalados (o siquiera estar en un sistema Arch).
"""

from __future__ import annotations

import subprocess


def list_explicit_packages() -> list[tuple[str, str]]:
    """Devuelve [(nombre, versión), ...] desde `pacman -Qe`.

    Lanza FileNotFoundError si pacman no existe y CalledProcessError
    si el comando falla. La GUI se encarga de mostrar el mensaje.
    """
    result = subprocess.run(
        ["pacman", "-Qe"],
        capture_output=True,
        text=True,
        check=True,
    )
    packages: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        name = parts[0]
        version = parts[1] if len(parts) > 1 else ""
        packages.append((name, version))
    return packages


def uninstall_packages(
    packages: list[str],
    noconfirm: bool = True,
) -> str:
    """Desinstala paquetes vía `pkexec pacman -Rns`.

    Devuelve la salida estándar del comando. Lanza CalledProcessError en
    error y FileNotFoundError si el comando no está disponible.
    """
    cmd = ["pkexec", "pacman", "-Rns"]
    if noconfirm:
        cmd.append("--noconfirm")
    cmd.extend(packages)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout