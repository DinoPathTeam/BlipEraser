#!/usr/bin/env bash
# Ajuste guiado del perfil AppArmor de la GUI de BlipEraser.
# Uso: ./scripts/aa-tune-gui.sh   (pide sudo solo)
# Requiere instalación NATIVA (/usr/bin/blip-eraser existe: AUR o pip).
# Con Flatpak no aplica: la GUI corre en el sandbox, no bajo este perfil.
set -euo pipefail

GUI_BIN="/usr/bin/blip-eraser"
PROFILE_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged"
PROFILE_DEST="/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged"

if [[ ! -x "$GUI_BIN" ]]; then
    echo "[STOP] No existe $GUI_BIN."
    echo "  Instala nativo primero (AUR: makepkg -si con packaging/aur/)"
    echo "  y vuelve a ejecutar este script. Con Flatpak no aplica."
    exit 1
fi

if [[ "$(id -u)" -ne 0 ]]; then
    echo "[INFO] Se necesita root: re-ejecutando con sudo…"
    exec sudo "$0" "$@"
fi

echo "[1/4] Perfil GUI en complain (registra sin bloquear)"
aa-complain "$GUI_BIN"

echo "[2/4] Usa la app con normalidad ~10 min:"
echo "  abre cada pestaña, cambia de tema/idioma, haz un borrado de prueba."
read -r -p "Pulsa Enter cuando termines de usarla… "

echo "[3/4] aa-logprof: revisa cada permiso y acepta (A) o deniega (D)"
aa-logprof

echo "[4/4] Pasar a enforce"
aa-enforce "$GUI_BIN"
aa-status | grep -A1 "blip-eraser" || true
echo "[OK] Revisa denegaciones futuras con: sudo dmesg | grep -i apparmor | grep blip"
