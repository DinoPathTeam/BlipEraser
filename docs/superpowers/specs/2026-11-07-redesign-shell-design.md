# Rediseño de BlipEraser (lavado de cara) — especificación

Fecha: 2026-11-07 · Estado: aprobado por el usuario (prototipo "Prototipo de rediseño", versión 1794091846-602a)

## Objetivo

Llevar toda la app al diseño del prototipo: mismos colores, degradados, sombras
y, sobre todo, la misma **posición de la información** en cada pestaña. Sin
perder ni inventar información: todos los textos y datos son los de la app real.

## Alcance por lotes (un PR por lote, contra `main`)

1. **Estructura + Vista general**: barra lateral nueva, encabezado, tarjeta con
   sombra (`Card`), Vista general, textos de ayuda "Uso" al día.
2. Desinstalador.
3. Limpiador del sistema.
4. Ajustes de rendimiento.
5. Configuración (Personalización, Tema de color, Ayuda).
6. Barra de estado y panel de actividad (si quedan retoques).

## Decisiones

- **Barra lateral**: logo + "BlipEraser" arriba; 5 entradas solo de texto con
  píldora de degradado en la activa; widget "Actividad" abajo. Los iconos
  dejan de dibujarse (la API `refresh_icons`/`set_icon_color` se conserva).
- **Encabezado**: título de la página a la izquierda; a la derecha búsqueda y
  botón "Actividad de la app" (solo en Desinstalador y Limpiador, como hoy). El
  título propio que algunas páginas tenían dentro se oculta (lo da el
  encabezado).
- **Sombras**: widget `Card` que pinta fondo, borde y sombra con `QPainter`
  (QSS no soporta `box-shadow`; no se usa `QGraphicsDropShadowEffect` por coste
  de render y artefactos con scroll). Colores tomados del tema.
- **Vista general**: fila superior (anillo de salud + 3 métricas), fila media
  (aplicaciones instaladas ancha + información del sistema), fila inferior
  (limpieza recomendada en horizontal con Escanear ahora / Limpiar ahora).
  Se elimina "Actividad reciente" de esta página: la barra lateral ya la
  muestra.
- **Compatibilidad**: se conservan los nombres de atributos públicos usados por
  los tests y la lógica (`gauge`, `metric_*`, `cpu_row`…, `scan_btn`,
  `cleanup_btn`, `cleanup_*_label`).
- **Ayuda "Uso"**: reescrita en ES/EN para describir las 5 secciones reales.

## Fuera de alcance

Cambios de lógica de negocio, nuevas funciones, nuevos temas.

## Verificación

`ruff`, `pytest` (incluye tests GUI offscreen), CI verde y revisión visual por
el usuario en su equipo antes de fusionar cada lote.
