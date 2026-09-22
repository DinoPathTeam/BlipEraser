#!/usr/bin/env bash
# Despliega el daemon privilegiado de BlipEraser en el sistema.
# Idempotente: se puede re-ejecutar tras cada cambio de código.
# Uso: ./scripts/install-daemon.sh            (pide sudo solo)
#      DESTDIR=/tmp/prueba ./scripts/install-daemon.sh   (prueba sin tocar el sistema)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DESTDIR:-}"
SYSTEMD_UNIT="$DEST/usr/lib/systemd/system/blip-eraser-privileged.service"
DBUS_CONF="$DEST/usr/share/dbus-1/system.d/blip-eraser-privileged.conf"
DBUS_XML="$DEST/usr/share/dbus-1/interfaces/com.dinopath.BlipEraser.Privileged.xml"
POLKIT_POLICY="$DEST/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy"
POLKIT_RULES="$DEST/etc/polkit-1/rules.d/49-blip-eraser.rules"
LIBDIR="$DEST/usr/lib/blip-eraser"

if [[ -z "$DEST" && "$(id -u)" -ne 0 ]]; then
    echo "[INFO] Se necesita root: re-ejecutando con sudo…"
    exec sudo "$0" "$@"
fi

echo "[1/6] Código del daemon -> $LIBDIR/blip_eraser"
mkdir -p "$LIBDIR"
rm -rf "$LIBDIR/blip_eraser"
cp -r "$REPO/src/blip_eraser" "$LIBDIR/blip_eraser"
find "$LIBDIR/blip_eraser" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
# Sin assets GUI (30 MB de vídeo/logo que el daemon jamás usa).
rm -rf "$LIBDIR/blip_eraser/assets"
install -m 755 "$REPO/packaging/scripts/blip-eraser-privileged" "$LIBDIR/blip-eraser-privileged"

echo "[2/6] Unidad systemd + D-Bus"
install -Dm 644 "$REPO/packaging/systemd/blip-eraser-privileged.service" "$SYSTEMD_UNIT"
install -Dm 644 "$REPO/packaging/dbus/blip-eraser-privileged.conf" "$DBUS_CONF"
install -Dm 644 "$REPO/packaging/dbus/com.dinopath.BlipEraser.Privileged.xml" "$DBUS_XML"

echo "[3/6] Polkit (acciones + reglas wheel)"
install -Dm 644 "$REPO/packaging/polkit/com.dinopath.blip-eraser.policy" "$POLKIT_POLICY"
install -Dm 644 "$REPO/packaging/polkit/49-blip-eraser.rules" "$POLKIT_RULES"

if [[ -n "$DEST" ]]; then
    echo "[OK] Despliegue de prueba en $DEST (sin systemctl)."
    exit 0
fi

echo "[4/6] Recargar systemd y (re)arrancar servicio"
systemctl daemon-reload
systemctl reset-failed blip-eraser-privileged.service 2>/dev/null || true
systemctl enable --now blip-eraser-privileged.service
sleep 2

echo "[5/6] Verificar servicio"
if ! systemctl is-active --quiet blip-eraser-privileged.service; then
    echo "[ERROR] El servicio no arrancó. Ver con:"
    echo "  journalctl -u blip-eraser-privileged.service -n 30"
    exit 1
fi
echo "[OK] Servicio active."

echo "[6/6] Ping D-Bus"
if busctl call com.dinopath.BlipEraser.Privileged \
    /com/dinopath/BlipEraser/Privileged \
    com.dinopath.BlipEraser.Privileged Ping 2>&1 | grep -q "b true"; then
    echo "[OK] Daemon responde Ping en el bus de sistema."
else
    echo "[WARN] Servicio activo pero Ping no responde (¿usuario fuera de wheel?)."
    echo "  La app usará fallback pkexec. Revisa: groups \$USER"
fi
echo "[OK] Listo. Tras cambiar código, re-ejecuta este script."
