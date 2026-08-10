"""Lógica pura para interactuar con pacman / pkexec — sin PyQt6.

Usa solo subprocess para que sea fácil de mockear y testear sin tener
paquetes reales instalados (o siquiera estar en un sistema Arch).
"""

from __future__ import annotations

import subprocess


def _query_packages(flag: str) -> list[tuple[str, str]]:
    """[(nombre, versión), ...] desde `pacman <flag>`.

    Lanza FileNotFoundError si pacman no existe y CalledProcessError
    si el comando falla. La GUI se encarga de mostrar el mensaje.
    """
    result = subprocess.run(
        ["pacman", flag],
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


def list_explicit_packages() -> list[tuple[str, str]]:
    """Devuelve [(nombre, versión), ...] desde `pacman -Qe`.
    Paquetes instalados explícitamente (las 'aplicaciones').
    """
    return _query_packages("-Qe")


def list_dependency_packages() -> list[tuple[str, str]]:
    """Devuelve [(nombre, versión), ...] desde `pacman -Qd`.

    Paquetes instalados como dependencia de otros (no explícitos).
    Mismo formato de salida que `pacman -Qe`.
    """
    return _query_packages("-Qd")


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