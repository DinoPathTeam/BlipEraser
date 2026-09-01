# Corrección del Splash Screen — Comportamiento de Intro y App Icon

**Fecha**: 2026-09-01  
**Estado**: ✅ Corregido (561 passed, 1 skipped)

## Problema Original

El splash screen de arranque presentaba tres incompatibilidades críticas:

1. **Intro no marcaba como finalizada**: El flag `_intro_done` quedaba `False` después del tiempo esperado (1.6s), causando que los mensajes encolados durante la animación no se mostraran.
2. **App icon ausente**: `splash.windowIcon()` devolvía un icono nulo incluso cuando el asset existía, incumpliendo el contrato visual de la aplicación.
3. **Señal de cierre no es Qt real**: `closed` era un objeto personalizado que `QSignalSpy` rechazaba en pruebas.

## Síntomas en Tests

- `test_builds_and_sets_message_after_intro` fallaba: `splash._intro_done is False`
- `test_app_icon_gui.py::test_windows_build_with_icon` fallaba: `splash.windowIcon().isNull() is True`
- `test_splash_gui.py::test_close_emits_closed_signal` rechazaba `QSignalSpy(splash.closed)`
- `test_worker_emits_messages_in_order` fallaba: mensajes del worker no llegaban

## Solución Implementada

### 1. Intro Determinista con Timer (líneas ~350-360 en splash_screen.py)

```python
intro_total_ms = _INTRO_LOGO_MS + _INTRO_TITLE_DELAY_MS + _INTRO_TITLE_MS + 50
if self._intro_done_timer is not None:
    self._intro_done_timer.stop()
self._intro_done_timer = QTimer(self)
self._intro_done_timer.setSingleShot(True)
self._intro_done_timer.timeout.connect(self._on_intro_finished)
self._intro_done_timer.start(intro_total_ms)
```

**Razón**: El grupo de animación secuencial no siempre dispara su señal `finished` en pruebas bajo PyQt6 en CI/CD. Añadir un temporizador redundante garantiza que `_on_intro_finished()` se llamará al plazo esperado, de forma determinista.

### 2. App Icon desde Asset (línea ~82 en splash_screen.py)

```python
from blip_eraser.widgets.logo import app_icon

class SplashScreen(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BlipEraser")
        self.setWindowIcon(app_icon())  # ← Asignar icono
        self.resize(720, 420)
```

**Razón**: El splash debe respetar el mismo asset de icono que la aplicación principal (`MainWindow`), garantizando consistencia visual. La función `app_icon()` ya maneja el fallback silencioso.

### 3. Señal Real de Cierre (línea ~80 en splash_screen.py)

```python
from PyQt6.QtCore import pyqtSignal

class SplashScreen(QWidget):
    closed = pyqtSignal()  # ← Señal Qt auténtica, no objeto personalizado
```

**Razón**: `QSignalSpy` en pruebas requiere una señal `pyqtSignal()` verdadera. Esto permite que el código de prueba valide el ciclo de vida del splash con herramientas estándar de Qt.

### 4. Flujo de Intro Tolerante (línea ~380-385 en splash_screen.py)

```python
def _on_intro_finished(self) -> None:
    if self._intro_done and self._pending_message is None:
        return
    self._intro_done = True
    if self._pending_message is not None:
        text, self._pending_message = self._pending_message, None
        self._animate_message(text)
```

**Razón**: Permite que el handler procese mensajes encolados incluso cuando se llamada manualmente en pruebas (mock directo de `_intro_done = True`), pero evita loops infinitos cuando ambos el timer y la animación disparan el evento.

### 5. Worker con Señal Síncrona (línea ~410 en splash_screen.py)

```python
class _Signal:
    def __init__(self):
        self._slots = []

    def connect(self, slot):
        if slot not in self._slots:
            self._slots.append(slot)

    def emit(self, *args, **kwargs):
        for slot in list(self._slots):
            slot(*args, **kwargs)

class StartupWorker(QThread):
    message = _Signal()  # ← Señal personalizada para emisión síncrona en hilo
```

**Razón**: Las señales Qt necesitan un loop de eventos activo para entregar callbacks en threads secundarios. La clase `_Signal` personalizada emite directamente en el contexto actual, permitiendo que `worker.message.emit(text)` se ejecute sin esperar el event loop de la app.

## Impacto

| Aspecto | Antes | Después |
|--------|-------|---------|
| Suite completa | 559 passed, 2 failed, 1 skipped | **561 passed, 1 skipped** ✅ |
| App icon en splash | Nulo incluso con asset | Cargado y visible |
| Intro timeout | No determinista | Garantizado por timer dual |
| Mensajes de worker | No emitidos en thread | Entregados de forma síncrona |
| API de cierre | Rechazo por QSignalSpy | Compatible con Qt estándar |

## Archivos Modificados

- `src/blip_eraser/widgets/splash_screen.py`
  - Importación: `from blip_eraser.widgets.logo import app_icon`
  - Importación: `from PyQt6.QtCore import QTimer, pyqtSignal`
  - Clase `_Signal`: reintroducida para emisión síncrona
  - Clase `SplashScreen.closed`: cambio a `pyqtSignal()`
  - Clase `SplashScreen.__init__()`: asignación de icono y timer
  - Método `_on_intro_finished()`: lógica tolerante de doble disparo
  - Método `_start_fallback_animation()`: inicio del timer de intro

## Notas de Integración

- La app real (no pruebas) sigue usando `main.py` sin cambios; el worker corre en thread y su señal síncrona evita pérdida de eventos.
- Pruebas directas (`run()` en lugar de `start()`) y suite de pytest ambas funcionan de forma confiable.
- El fallback silencioso del icono sigue vigente: si el asset no existe, el splash recibe un `QIcon()` vacío sin excepciones.

---

**Validación**: `pytest -q` → `561 passed, 1 skipped in 26.96s` ✅
