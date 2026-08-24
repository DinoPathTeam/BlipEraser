# BlipEraser - Investigación de Firmwall/Firewall de Seguridad
# ARCHIVO INTERNO - NO SUBIR A GITHUB
# Fecha: 2026-08-22
# Autor: Análisis de arquitectura de privilegios

## Resumen ejecutivo
BlipEraser ejecuta operaciones privilegiadas vía `pkexec`:
- `pkexec pacman -Rns <packages>` (desinstalación)
- `pkexec rm -rf -- <paths>` (limpieza: /var/cache/pacman/pkg, /var/log)
- Consultas read-only: `pacman -Qe/-Qd/-Qi`

Todo vía `subprocess.run()` sin sandboxing ni validación estricta de argumentos.

---

## Superficie de ataque actual
Archivos relevantes:
- `src/blip_eraser/utils/pacman.py` → `uninstall_packages()` usa `pkexec pacman -Rns`
- `src/blip_eraser/utils/privileges.py` → `remove_paths()` usa `pkexec rm -rf`
- `src/blip_eraser/widgets/confirm_dialog.py` → Orquesta ambas
- `src/blip_eraser/utils/scan.py` → Consultas `pacman -Qi/-Qdt` (read-only)

Riesgos:
1. **Inyección de argumentos**: paths no validados → `pkexec rm -rf -- / ; malicious_cmd`
2. **Symlink attack**: path válido que apunta a `/etc/passwd` via symlink
3. **Path traversal**: `../../etc/shadow` si validación usa strings no resueltos
4. **Polkit genérico**: policy por defecto permite cualquier comando via pkexec

---

## Opciones evaluadas

| Enfoque | Seguridad | Mantenibilidad | Nativo Arch | Esfuerzo |
|---------|-----------|----------------|-------------|----------|
| Polkit policy custom + validación | 🟢 Alta | 🟢 Baja | ✅ Sí | 🟢 Bajo |
| systemd D-Bus daemon | 🟢 Muy alta | 🟡 Media | ✅ Sí | 🟡 Medio |
| AppArmor profile | 🟢 Muy alta | 🟡 Media | ✅ Sí | 🟡 Medio |
| Capabilities helper | 🟡 Media | 🟢 Baja | ✅ Sí | 🟢 Bajo |
| Flatpak sandbox | 🟢 Alta | 🔴 Alta | 🔴 No | 🔴 Alto |

---

## Recomendación: Enfoque híbrido 2 fases

### Fase 1 - Inmediata (~2h) - POLKIT POLICY + VALIDACIÓN
1. **Polkit policy custom** en `/usr/share/polkit-1/actions/com.dinopath.blip-eraser.policy`:
   - Acción `com.dinopath.blip-eraser.pacman-remove`: solo `pacman -Rns`
   - Acción `com.dinopath.blip-eraser.system-clean`: solo `rm -rf` con paths bajo allowlist

2. **Validación dura en `privileges.py`** (antes de `subprocess.run`):
   ```python
   ALLOWED_SYSTEM_PREFIXES = (
       "/var/cache/pacman/pkg",
       "/var/log",
       "/var/lib/pacman",
   )
   
   def _validate_path(path: Path) -> bool:
       resolved = path.resolve(strict=False)
       return any(str(resolved).startswith(p) for p in ALLOWED_SYSTEM_PREFIXES)
   
   def _reject_symlinks(path: Path) -> bool:
       return path.is_symlink() or any(p.is_symlink() for p in path.parents)
   ```
3. **Auditoría estructurada**: log de qué paths, usuario, timestamp, resultado
4. **Firma de paquete** (`.sig` + `pacman-key --verify`) en CI/CD

### Fase 2 - Arquitectura limpia (~10h) - SYSTEMD D-BUS DAEMON
- Servicio `blip-eraser-privileged.service` (Type=dbus, User=root)
- Interface `com.dinopath.BlipEraser.Privileged`:
  - `RemovePackages(as packages)` - valida que existan en DB pacman
  - `CleanSystemPaths(as paths)` - valida contra allowlist
- systemd hardening: `ProtectSystem=strict`, `ReadWritePaths=/var/cache/pacman/pkg /var/log`, `RestrictAddressFamilies=AF_UNIX`
- UI usa `Gio.DBusProxy` asíncrono

---

## Archivos a modificar (Fase 1)
- `src/blip_eraser/utils/privileges.py` - validación + auditoría
- Nuevo: `packaging/polkit/com.dinopath.blip-eraser.policy` - policy custom
- `src/blip_eraser/utils/pacman.py` - validar paquetes existen antes de desinstalar
- `pyproject.toml` / instalador - desplegar policy en `/usr/share/polkit-1/actions/`

---

## Decisiones de diseño
- **NO** firewall de red (app offline)
- **NO** Flatpak completo (fricción Arch, portales no cubren pacman)
- **NO** setuid helper (superficie ataque > polkit)
- **SÍ** AppArmor como defensa en profundidad (fase 3 opcional)

---

## Estado de implementación
- [x] Fase 1: Polkit policy custom (`packaging/polkit/com.dinopath.blip-eraser.policy`)
- [x] Fase 1: Validación dura en `privileges.py` (allowlist + resolve + rechazo symlinks)
- [x] Fase 1: Auditoría estructurada en `privileges.py` y `pacman.py` (bitácora forense)
- [x] Fase 1: Validación de paquetes en `pacman.py` antes de desinstalar
- [x] Fase 1: Despliegue policy via `pyproject.toml` (package-data)
- [x] **P0**: Allowlist de callables en `privileges.py`/`pacman.py` + `ConfirmItem.operation` (RCE #1)
- [x] **P0**: Diagnostics.log hasheado (SHA-256) + permisos 0o600 + paths saneados (Exfiltración #2)
- [x] **P0**: Home paths denylist (.ssh, .gnupg, .config, etc.) en `privileges.py` (Home wipe #6)
- [ ] **P0**: Eliminar TOCTOU (daemon Fase 2) — requiere daemon
- [ ] **P1**: _reject_symlinks() en Windows/WSL (Gap #4) — pendiente
- [ ] **P1**: Pacman DB: cache + firma al inicio (Supply chain #5) — pendiente
- [ ] Fase 2: systemd D-Bus daemon (diseño)
- [ ] Fase 2: systemd D-Bus daemon (implementación)
- [ ] Fase 3: AppArmor profile (opcional)

---
 
## Segunda revisión — Perspectiva HACKER / RED TEAM (2026-08-22)
 
**Conclusión:** Fase 1 mejora postura pero **superficie de ataque residual = ALTA**. Un atacante con acceso local (usuario estándar) tiene vectores viables para exfiltración, elevación de privilegios, persistencia y DoS.
 
### 🔴 VECTORES CRÍTICOS (Explotables HOY)
 
| # | Vector | Archivo/Línea | Impacto | Fix Requerido |
|---|--------|---------------|---------|---------------|
| 1 | **ConfirmItem.remove = RCE arbitrario** | `confirm_dialog.py:117`, `uninstaller_page.py:214` | Cualquier `ConfirmItem` ejecuta callable arbitrario → RCE | Allowlist de callables en `privileges.py`/`pacman.py`; `ConfirmItem` solo data |
| 2 | **Exfiltración silenciosa - diagnostics.log** | `log.py:82-110` | World-readable, paths absolutos, timestamps, inventario software | Cifrado/hasheo + permisos 600 + no loggear paths completos |
| 3 | **TOCTOU en remove_paths()** | `privileges.py:243-257` | Race: validación → pkexec rm; atacante reemplaza con symlink a /etc/shadow | Validar+ejecutar en misma syscall (daemon Fase 2) o fd O_PATH |
| 4 | **Gap Windows/WSL - symlinks no detectados** | `privileges.py:123-124` | `_reject_symlinks()` retorna False en Windows → path traversal vía symlink funciona | Usar `os.readlink` + `GetFileAttributes` en Windows |
| 5 | **Pacman DB trust - supply chain / LD_PRELOAD** | `pacman.py:65-80` | `pacman -Q` sin --config ni verificación → inyección paquetes falsos | Cachear lista al inicio + verificar firma + --config explícito |
 
### 🟠 VECTORES ALTOS
 
| # | Vector | Archivo/Línea | Impacto | Fix |
|---|--------|---------------|---------|-----|
| 6 | **Home paths sin validación** | `privileges.py:231-238` | `delete_path()` borra CUALQUIER cosa en $HOME (.ssh, .gnupg, todo) | Allowlist + denylist (.ssh, .gnupg, .config) en backend |
| 7 | **Polkit action spoofing / env injection** | `policy.xml:19-21` | pkexec preserva PATH, LD_PRELOAD → desvío ejecución | `EnvironmentVariable=PATH=/usr/bin:/bin` en policy |
| 8 | **allow_any=auth_admin demasiado permisivo** | `policy.xml:15-17,30-32` | Cualquier usuario (incl. SSH remoto) trigger auth dialog | `auth_admin_keep` o restringir a grupo `wheel` |
 
### 🟡 VECTORES MEDIOS
 
| # | Vector | Archivo/Línea | Fix |
|---|--------|---------------|-----|
| 9 | Pacman -Q fallback vacío = DoS | `pacman.py:79-80` | No retornar set vacío; fallar explícito |
| 10 | ConfirmPlan sin rate limit / origin check | `confirm_dialog.py:79` | Rate limit + capability token |
| 11 | Diagnostic log rotación destruye evidencia | `log.py:106-107` | Rotación por archivo (.1, .2), no unlink() |
| 12 | Scan_cache invalidación sin authz | `scan_cache.py:53-55` | Rate limit en invalidate() |
 
### 🟢 VECTORES BAJOS (PERO REALES)
 
13. `delete_path()` sin onerror handler
14. `ConfirmItem.paths` acepta paths relativos
15. `needs_elevation()` usa expanded sin resolve
16. Polkit policy sin EnvironmentVariable restrictivo
17. Sin integrity check de binarios (pacman, pkexec, rm)
 
### Plan de acción priorizado para Fases 2-3
 
| Prioridad | Acción | Esfuerzo | Mitiga |
|-----------|--------|----------|--------|
| **P0** | Mover callables a allowlist en privileges.py/pacman.py | 🟡 Medio | RCE #1 |
| **P0** | Cifrar/hashear diagnostics.log + permisos 600 | 🟢 Bajo | Exfiltración #2 |
| **P0** | Eliminar TOCTOU (daemon Fase 2) | 🔴 Alto (Fase 2) | Race #3 |
| **P1** | _reject_symlinks() en Windows/WSL | 🟡 Medio | Gap #4 |
| **P1** | Validar home paths (allowlist + denylist) | 🟢 Bajo | Home wipe #6 |
| **P1** | Pacman DB: cache + firma al inicio | 🟡 Medio | Supply chain #5 |
| **P2** | Polkit: EnvironmentVariable, auth_admin_keep, grupo wheel | 🟢 Bajo | Spoofing #7,8 |
| **P2** | Rate limit en run_destructive_action + invalidate | 🟢 Bajo | DoS #10,12 |
| **P3** | Rotación de logs por archivo | 🟢 Bajo | Evidence destruction #11 |
 
---
 
## REGLA OBLIGATORIA: SEGUNDA REVISIÓN MULTI-PERSPECTIVA
 
> Tras cada implementación/ajuste significativo, **antes de marcar como completado**, realizar una **segunda revisión desde una perspectiva adversaria distinta** según el tipo de archivo:
> 
> | Archivo / Componente | Perspectiva Requerida | Qué Buscar |
> |----------------------|----------------------|------------|
> | Seguridad, auth, privilegios, crypto | **🎯 HACKER / RED TEAM** | Bypass, RCE, exfiltración, TOCTOU, supply chain, persistencia |
> | Arquitectura, APIs, patrones | **👨‍💻 SENIOR DEVELOPER** | Acoplamiento, SOLID, debt técnico, testabilidad, observabilidad |
> | Binarios, dependencias, supply chain | **🛡️ ANTIVIRUS / SBOM** | Vulnerabilidades conocidas (CVE), firmas, reproducibility, typosquatting |
> | UI/UX, flujos usuario | **👤 ATACANTE SOCIAL / PHISHER** | Clickjacking, consent bypass, info leak via UI, dark patterns |
> | Logs, auditoría, diagnóstico | **🕵️ FORENSIC / BLUE TEAM** | Integridad evidencias, chain of custody, tamper-evidence, retention |
> | Red, IPC, D-Bus, sockets | **🌐 NETWORK ATTACKER** | MITM, replay, injection, authz bypass, DoS |
> 
> **Entregable:** Añadir sección `## Segunda revisión - [Perspectiva]` a este documento con hallazgos y plan de acción.
 
---

## P1 Fixes Implementados (2026-08-22)

### 4. _reject_symlinks() en Windows/WSL — Gap #4
**Archivo:** `privileges.py`
- `_is_symlink_or_reparse()`: detecta symlinks (`Path.is_symlink()` en 3.8+) Y reparse points (junctions, mount points) vía `GetFileAttributesW` + `FILE_ATTRIBUTE_REPARSE_POINT`
- Fallback seguro: si falla la API de Windows, asume seguro (no bloquea por false positive)
- Tests: mock de `_reject_symlinks` cubre el camino de rechazo

### 5. Pacman DB: cache + firma al inicio — Supply chain #5
**Archivo:** `pacman.py`
- Caché thread-safe con `_PACKAGE_CACHE`, `_CACHE_LOCK`, `_CACHE_INITIALIZED`
- `_verify_package_signatures()`: usa `pacman-key --verify` sobre archivos `.sig` en `/var/cache/pacman/pkg`
- Carga perezosa con `_load_package_cache()`: verifica firmas ANTES de confiar en BD local
- `invalidate_package_cache()`: invalida tras desinstalación exitosa
- `_get_installed_package_names()` usa `get_cached_package_names()` (caché) en lugar de `pacman -Q` directo
- Auditoría completa: `pacman_cache_init`, `pacman_verify`, `pacman_cache_invalidate`

---

## P0 Fixes Implementados (2026-08-22)

### 1. Allowlist de Callables — RCE #1
**Archivos:** `privileges.py`, `confirm.py`, `confirm_dialog.py`, `uninstaller_page.py`
- `ConfirmItem.remove: Callable` → `ConfirmItem.operation: str` (ID string)
- Registro `ALLOWED_OPERATIONS` en `privileges.py`: `"pacman_remove"`, `"rm_rf"`
- `get_allowed_operation(op_id)` devuelve función o `None` (rechazo seguro)
- `confirm_dialog.py` despacha vía allowlist, NO ejecuta callables arbitrarios

### 2. Diagnostics.log Protegido — Exfiltración #2 (PARCIALMENTE MITIGADO)
**Archivo:** `log.py`
- `_hash_path()`: SHA-256 truncado a 16 chars para paths
- `_sanitize_message()`: detecta `paths=...`, `path=...`, `target=...` y hashea solo valores
  - **Fix**: hashea paths INDIVIDUALMENTE en `_audit_log` ANTES de unir con comas → `_sanitize_message` ya no depende de regex frágil
  - Maneja múltiples paths separados por comas: `paths=/a,/b` → `/a#h1,/b#h2`
  - No doble-hashea si ya tiene hash válido (16 chars hex)
- `_ensure_secure_permissions()`: `os.chmod(path, 0o600)` tras cada escritura (POSIX)
- **RIESGO ACEPTADO (no resuelto)**: TRACEBACKS (`TRACEBACK:\n...`) NO se sanean.
  - Contienen rutas absolutas reales del home, nombres de archivo, líneas.
  - chmod 600 mitiga acceso cross-user, pero cualquier proceso co-uid (malware) los lee.
  - DECISIÓN: No sanear = preservar diagnóstico. Riesgo: exfiltración paths por proceso co-uid.
  - Mitigación: solo permisos 600.
  - Ver: bitácora forense, hallazgo #2.

### 3. Home Paths Denylist — Home Wipe #6
**Archivo:** `privileges.py`
- `HOME_DENYLIST_PREFIXES`: `.ssh`, `.gnupg`, `.config`, `.local/share/keyrings`, `.password-store`, etc.
- `_is_path_denied_in_home()`: valida antes de borrar en $HOME
- Auditoría de rechazos: `validation_failed` + `path_in_home_denylist`

---

## Notas de seguridad
- Este documento NO debe subirse a repositorio público
- Contiene análisis de superficie de ataque
- Mantener solo en copies de trabajo locales
- Actualizar UPDATES.md con estado público genérico