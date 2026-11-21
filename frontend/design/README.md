# Primera propuesta visual FiQA (referencia)

La especificación vigente es [refinamiento.md](refinamiento.md), con la paleta
perla/coral, navegación en el footer y transición a la barra compacta. Este
documento conserva el registro de la primera propuesta, que ya no describe la UI.

Skill aplicada: `frontend-app-builder`, acompañada de `react-best-practices` y
`frontend-testing-debugging`. Concepto generado con la herramienta integrada
Image Gen y guardado en [concepto.png](concepto.png). La interfaz se implementa
con HTML/CSS y controles React nativos; la imagen no se usa como interfaz.

Brief del prompt utilizado: una pantalla completa de buscador universitario FiQA,
minimalista retrofuturista, con solo tinta azul `#101923`, marfil `#F3EEE5` y cobre
`#D19A66`; wordmark FiQA grande e inclinado con una órbita sutil, una barra de
búsqueda protagonista con modelo integrado y botón Buscar, Top-K, comparación,
tres sugerencias y un panel de métricas histórico con los valores reales del
híbrido. Navegación Buscar, Evaluación y Acerca del sistema. Fondo discreto,
glassmorphism moderado, sin verde, morado, elementos decorativos superfluos ni
resultados inventados. Texto y controles implementables en código. El prompt
incluyó las cuatro métricas históricas exactas y ambos tamaños del corpus.

| Token o familia | Especificación |
|---|---|
| Colores | Tinta `#101923`, marfil `#F3EEE5`, cobre `#D19A66`; superficies y bordes son transparencias de estos colores |
| Tipografía | DM Sans para lectura, Space Grotesk para títulos y marca; archivos locales de `@fontsource` |
| Escala | Base 17px escritorio, 16px móvil; metadatos secundarios ≥13,6px; controles con tamaños explícitos |
| Contenedores | Una barra de búsqueda y un panel lateral; resultados como listas abiertas, evaluación como tabla y gráfica |
| Foco | Contorno cobre de 2px, acceso por teclado y enlace para saltar al contenido |
| Iconos | Lupa SVG de trazo 1,7; chevron en selectores; indicadores de estado con texto |
| Movimiento | Entrada breve de resultados, giro de carga, transiciones de controles; desactivación con reduced-motion |
| Adaptación | 1440px escritorio, 820px tablet, 390px móvil; panel bajo el buscador en tablet/móvil |

## Revisión de fidelidad

Se inspeccionaron con `view_image` tanto el concepto como las capturas finales del
navegador. Se capturó la pantalla principal a **1488×1057**, tamaño nativo del
concepto, y se verificaron los flujos con Playwright en otros tres tamaños.

| Punto comparado | Evidencia y ajuste |
|---|---|
| Paleta y fondo | Se mantuvieron los tres colores; el halo se dibuja con una transparencia cobre y no una imagen que distraiga |
| Marca y tipografía | Se corrigió la inclinación real mediante transformación de la tipografía local; se aumentó el tamaño de lectura |
| Jerarquía y composición | Marca centrada, búsqueda protagonista, navegación superior y métricas a la derecha; se redujo la altura del panel para que el inicio quepa en el viewport de referencia |
| Barra y controles | Selector integrado, Buscar, Top-K y comparación; separación de etiquetas para que el nombre accesible no incluya las opciones |
| Superficies | Bordes finos, cristal y desenfoque; resultados abiertos sin una tarjeta adicional por cada documento |
| Contenido visible | Se conserva el copy principal del concepto; se añade una aclaración necesaria sobre las métricas de benchmark y el enlace a Evaluación |
| Móvil | Controles en filas completas, texto legible, navegación sin menú oculto y métricas debajo del flujo de búsqueda |
| Estados y capturas | Se desactivan las animaciones solo durante la captura, para que las imágenes no congelen resultados a media opacidad |

Las diferencias respecto de la imagen son funcionales y deliberadas: aviso de
benchmark histórico, contexto de 648 consultas, enlace a evaluación y estados de
conexión reales. No se conserva la indicación de motor conectado del concepto
si la API no confirma disponibilidad. No quedan desajustes visuales materiales
observados en los tamaños comprobados.
