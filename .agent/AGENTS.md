# AGENTS.md — Reglas de Operación del Agente (BlipEraser)

> Adaptado de TripleWrapper como referencia. Proyecto, stack y seguridad son
> TOTALMENTE distintos: no aplicar decisiones de TripleWrapper aquí.

## 1. IDENTIDAD Y ROL

Asistente de código para **BlipEraser** — desinstalador + limpiador del sistema
para Arch Linux y derivadas (pacman + systemd + D-Bus).
Detecta lo que pacman no ve (AppImages, carpetas sueltas, Hydra) y lo unifica
con paquetes en una sola UI. Licencia MIT. Estado: funcional, desordenado,
en fase de orden/limpieza por partes. **Fase actual: solo entender, no fix.**

**Ruta canónica:** `/home/adrexcou/BlipEraser/` (clon de GitHub para probar
en Linux; el trabajo anterior era en Windows). Ignorar cualquier otra copia.

## 2. STACK REAL (verificado)

- **Python ≥3.11** (probado en 3.14): todo — GUI, lógica, daemon.
- **GUI: PyQt6** (+ QtMultimedia opcional para vídeo splash). QSS para temas.
- **IPC privilegiado: D-Bus** (bus de sistema, `gi.repository Gio/GLib`) +
  daemon systemd `blip-eraser-privileged` corriendo como root.
- **Auth: polkit** (policy XML + rules JS) + fallback `pkexec`.
- **Confinamiento: AppArmor** (perfil en `packaging/`, Fase 3 opcional).
- **Sistema: pacman, systemd, loginctl, gst-libav** (H.264), `lspci`, `/proc`.
- **Packaging: setuptools** (`pyproject.toml`), sin PKGBUILD ni `.desktop` aún.
- Deps pip = `[]` (+ `pytest` dev). Qt/GObject/gst **siempre vía pacman**,
  nunca pip. Regla: jamás `pip install --break-system-packages` global
  sin permiso; preferir `--system-site-packages` o pacman.

## 3. REGLAS

1. **Leer antes de tocar.** Proyectos desordenados: parte por parte.
   Nada de fixes sin que el creador los pida explícitamente.
2. **Cambios menores autónomos:** comentarios, formato sin cambio lógico,
   `.gitkeep`, typos en docs, logs debug temporales, tests nuevos para
   código existente, `exit`-style basura solo con permiso (son `rm`,
   pedir confirmación).
3. **Cambios sensibles (pedir permiso):** allowlists/denylists de paths,
   policy polkit, conf D-Bus, unit systemd, perfil AppArmor, cualquier
   `rm -rf`/`pacman -Rns`, dependencias, CI/packaging, >3 archivos,
   cualquier cosa que rompa arranque o tests.
4. **Commits locales siempre, push nunca sin permiso.** Cada cambio
   significativo se commitea en local con Conventional Commits.
   Push solo con autorización explícita del creador (rama incluida).
5. **Cambios privilegiados** (daemon, privileges, validation, dbus_client,
   pacman, packaging): auto-revisión Red/Blue/Senior/CyberSec/QA/DevOps
   antes de commitear. Un rol crítico = parar y notificar.
6. **Reviews locales** en `.agent/reviews/review-log.md`. No subir
   (añadir `.agent/` a `.gitignore`), no mostrar en docs.
7. **Seguridad > conveniencia.** Allowlist estricta única en
   `utils/validation.py` (hoy duplicada en 3 sitios: deuda conocida).
   Sin shell, sin secretos, auditoría en cada op privilegiada.
8. **No overengineering** (ponytail): stdlib antes que deps, borrar antes
   que añadir, un fix en la función compartida antes que en cada caller.

## 4. PROTOCOLO DE SESIÓN

1. Leer este archivo. 2. `git status` + `git log --oneline -5`.
3. Leer `.agent/reviews/review-log.md` si existe.
4. `python3 -m pytest -q` si se va a tocar lógica (referencia, no gate
   ciego: hoy hay 9 fallos por deriva de entorno, ver log).
5. Resumir estado en 3 líneas y preguntar en qué parte trabajamos.

## 5. ARQUITECTURA (referencia rápida)

```
main.py (check PyQt6 → idioma → Splash+StartupWorker → MainWindow)
  └── renderer.py MainWindow (Sidebar + QStackedWidget + StatusBar + LogPanel)
        ├── pages/overview (gauge+scan fondo) · uninstaller (tabla pacman+manual)
        ├── pages/cleaner (recomendada+manual) · performance (tweaks)
        └── pages/settings/personalize/tools/help
  └── widgets/ (splash QVideoSink, check_table, scan_worker mixin, dialogs)
  └── utils/ puros sin Qt (scan, apps, pacman, privileges, validation,
                           dbus_client, file_utils, i18n dict, theme, log...)
        ├── D-Bus → daemon root (RemovePackages/CleanSystemPaths/Ping)
        └── fallback → pkexec (pacman -Rns / rm -rf allowlist)
```

Versión canónica: `src/blip_eraser/__init__.py` (`1.0.0`).
`pyproject.toml` dice `0.1.0` — deuda pendiente, la canónica es `1.0.0`.

---
Versión: 1.0.0-blip · 2026-09-22 · Solo con autorización del creador.
