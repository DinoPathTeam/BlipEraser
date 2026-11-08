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
    exec sudo INSTALL_DESKTOP="${INSTALL_DESKTOP:-0}" "$0" "$@"
fi

echo "[1/8] Código del daemon -> $LIBDIR/blip_eraser"
# Este código lo ejecuta root: nada de symlinks en el origen (apuntarían a
# rutas que el usuario puede cambiar) ni dependencia del umask del invocador.
if [[ -n "$(find "$REPO/src/blip_eraser" -type l -print -quit)" ]]; then
    echo "[ERROR] Hay symlinks en src/blip_eraser; se rechaza el despliegue:" >&2
    find "$REPO/src/blip_eraser" -type l >&2
    exit 1
fi
install -d -m 755 "$LIBDIR"
rm -rf "$LIBDIR/blip_eraser"
cp -r "$REPO/src/blip_eraser" "$LIBDIR/blip_eraser"
find "$LIBDIR/blip_eraser" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
# Sin assets GUI (30 MB de vídeo/logo que el daemon jamás usa).
rm -rf "$LIBDIR/blip_eraser/assets"
install -m 755 "$REPO/packaging/scripts/blip-eraser-privileged" "$LIBDIR/blip-eraser-privileged"
# Permisos normalizados: root, directorios 755, ficheros 644 (sin escritura de
# grupo/otros aunque el árbol de origen la tuviera).
find "$LIBDIR/blip_eraser" -type d -exec chmod 755 {} +
find "$LIBDIR/blip_eraser" -type f -exec chmod 644 {} +
if [[ -z "$DEST" ]]; then
    chown -R root:root "$LIBDIR"
fi

echo "[2/8] Unidad systemd + D-Bus"
install -Dm 644 "$REPO/packaging/systemd/blip-eraser-privileged.service" "$SYSTEMD_UNIT"
install -Dm 644 "$REPO/packaging/dbus/blip-eraser-privileged.conf" "$DBUS_CONF"
install -Dm 644 "$REPO/packaging/dbus/com.dinopath.BlipEraser.Privileged.xml" "$DBUS_XML"

echo "[3/8] Polkit (acciones + reglas wheel)"
install -Dm 644 "$REPO/packaging/polkit/com.dinopath.blip-eraser.policy" "$POLKIT_POLICY"
install -Dm 644 "$REPO/packaging/polkit/49-blip-eraser.rules" "$POLKIT_RULES"

echo "[4/8] Acceso directo (.desktop) + icono"
# Estos accesos lanzan `blip-eraser` / `blip-eraser-tray` del PATH: solo tienen
# sentido si la app está instalada en el host. Con el Flatpak (que exporta su
# propio acceso) dejarían una entrada duplicada que no abre nada. Se omiten salvo
# DESTDIR (empaquetado/pruebas), si `blip-eraser` existe, o INSTALL_DESKTOP=1.
if [[ -n "$DEST" ]] || command -v blip-eraser >/dev/null 2>&1 || [[ "${INSTALL_DESKTOP:-0}" == "1" ]]; then
    install -Dm 644 "$REPO/packaging/blip-eraser.desktop" "$DEST/usr/share/applications/blip-eraser.desktop"
    install -Dm 644 "$REPO/packaging/blip-eraser-tray.desktop" "$DEST/usr/share/applications/blip-eraser-tray.desktop"
    install -Dm 644 "$REPO/packaging/icons/hicolor/512x512/apps/blip-eraser.png" \
        "$DEST/usr/share/icons/hicolor/512x512/apps/blip-eraser.png"
    if [[ -z "$DEST" ]]; then
        update-desktop-database /usr/share/applications 2>/dev/null || true
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
    fi
else
    echo "[INFO] 'blip-eraser' no está en el PATH (¿solo Flatpak?): se omite el acceso"
    echo "       directo del host. Para instalarlo igualmente: sudo INSTALL_DESKTOP=1 $0"
fi

echo "[5/8] AppArmor (enforce, Fase 3)"
if [[ -d /sys/kernel/security/apparmor ]] && command -v apparmor_parser >/dev/null; then
    install -Dm 644 "$REPO/packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged" \
        "$DEST/etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged"
    if [[ -z "$DEST" ]]; then
        apparmor_parser -r /etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged \
            && echo "[OK] Perfil cargado en enforce."
    fi
else
    echo "[WARN] Kernel sin AppArmor: perfil copiado pero sin cargar (solo aviso)."
    if [[ -z "$DEST" ]]; then
        install -Dm 644 "$REPO/packaging/apparmor/usr.lib.blip-eraser.blip-eraser-privileged" \
            /etc/apparmor.d/usr.lib.blip-eraser.blip-eraser-privileged || true
    fi
fi

if [[ -n "$DEST" ]]; then
    echo "[OK] Despliegue de prueba en $DEST (sin systemctl)."
    exit 0
fi

echo "[6/8] Recargar systemd y (re)arrancar servicio"
systemctl daemon-reload
systemctl reset-failed blip-eraser-privileged.service 2>/dev/null || true
# restart (no solo enable --now): si ya corría, hay que recargar el código nuevo
systemctl enable blip-eraser-privileged.service
systemctl restart blip-eraser-privileged.service
sleep 2

echo "[7/8] Verificar servicio"
if ! systemctl is-active --quiet blip-eraser-privileged.service; then
    echo "[ERROR] El servicio no arrancó. Ver con:"
    echo "  journalctl -u blip-eraser-privileged.service -n 30"
    exit 1
fi
echo "[OK] Servicio active."

echo "[8/8] Ping D-Bus"
# El daemon solo atiende a usuarios wheel con sesión gráfica activa: root (sudo)
# siempre es rechazado, así que el ping se hace como el usuario que invocó sudo.
PING_USER="${SUDO_USER:-}"
if [[ -z "$PING_USER" || "$PING_USER" == "root" ]]; then
    echo "[INFO] Sin usuario normal (SUDO_USER): ping omitido. Prueba como tu usuario:"
    echo "  busctl call com.dinopath.BlipEraser.Privileged /com/dinopath/BlipEraser/Privileged com.dinopath.BlipEraser.Privileged Ping"
elif sudo -u "$PING_USER" busctl call com.dinopath.BlipEraser.Privileged \
    /com/dinopath/BlipEraser/Privileged \
    com.dinopath.BlipEraser.Privileged Ping 2>&1 | grep -q "b true"; then
    echo "[OK] Daemon responde Ping en el bus de sistema (usuario $PING_USER)."
else
    echo "[WARN] Servicio activo pero Ping no responde para $PING_USER."
    echo "  Causas: no está en wheel, o no hay sesión gráfica activa (corre esto"
    echo "  desde una terminal dentro de tu sesión). Revisa: groups $PING_USER"
    echo "  La app usará fallback pkexec."
fi
echo "[OK] Listo. Tras cambiar código, re-ejecuta este script."
