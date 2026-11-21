# FiQA — refinamiento del buscador existente

Se aplicó `frontend-app-builder` junto con `frontend-testing-debugging`. Se
conservaron React/Vite, el cliente FastAPI, los hooks de conexión y búsqueda, los
rankings, la comparación y las fuentes experimentales. No se creó otra aplicación.

Referencia de movimiento: `forja-buscador-claro.html`; se inspeccionaron las
transiciones de logo/barra, el cristal, las luces ambientales y el escalonado de
resultados. No se trasladaron sus búsquedas de demostración, dominios inventados,
cifras aleatorias, temporizadores de resultados ni canvas de partículas.

## Concepto y tokens

El concepto actualizado está en [concepto-refinado.png](concepto-refinado.png).
Se generó con Image Gen integrado, con este brief: buscador FiQA claro completo,
sin navegación superior ni métricas laterales, logo grande y centrado, barra de
cristal amplia, selector Automático completo, botón coral, Top-K, comparación,
Sugerencias y tres consultas reales de ejemplo. Footer con conexión, Evaluación
y Acerca del sistema. Paleta `#F4F4F6`, `#E7E7E7`, `#D2D2D4`, `#FF634A` y grafito
para contraste; ningún resultado ni métrica inventados. Controles implementables
en código y animación posterior hacia un dock fijo.

| Elemento | Decisión |
|---|---|
| Fondo | Gris perla `#F4F4F6` |
| Superficies | Transparencias blancas y gris `#E7E7E7`, con blur moderado |
| Borde y luz | Gris `#D2D2D4`, halo coral discreto |
| Acento | Coral `#FF634A`; grafito sobre el botón para legibilidad |
| Texto | Grafito `#202228`; coral oscurecido en enlaces y foco para contraste |
| Selector | Menú grafito con texto claro, foco visible, selección y hover |
| Tipografía | Se conservan DM Sans y Space Grotesk locales |
| Movimiento | FLIP de 680ms en logo/barra, escalonado de resultados y luces lentas |

## Transición y continuidad

`useDockMotion` mide los rectángulos antes/después de cambiar la distribución y
anima `transform` mediante Web Animations. El logo y la barra son los mismos nodos
en los dos estados. No se anima el layout frame a frame ni se clona el formulario.
La barra compacta es sticky y su altura real se observa con ResizeObserver.

Las búsquedas siguientes mantienen el dock compacto. El campo permanece montado
y conserva su identidad. Se reserva temporalmente la altura de los resultados
anteriores para evitar que una búsqueda nueva en una página desplazada provoque
un salto al retirar su contenido. Tras el nuevo resultado se vuelve arriba con
scroll suave antes de liberar esa reserva.

FiQA cancela una solicitud pendiente, vuelve arriba y anima el regreso al estado
inicial. El campo se limpia, Automático vuelve a estar seleccionado y las
sugerencias se abren. Cancelar una petición conserva la barra compacta. Con
`prefers-reduced-motion`, los movimientos, transiciones y scroll animado se omiten.

## Comprobación visual

Se compararon con `view_image` el concepto y las capturas reales del frontend.
La pantalla de escritorio se captura a 1488×1057 y también se validan 1440×1000,
820×1180 y 390×844; el selector se comprueba adicionalmente a 320px de ancho.

| Punto | Verificación y diferencia deliberada |
|---|---|
| Jerarquía | FiQA y búsqueda centrados; sin panel lateral ni header de navegación |
| Paleta | Perla y coral exactos como base; grafito y acento oscuro derivados para accesibilidad |
| Logo | Se conserva la tipografía existente con inclinación y órbita discreta |
| Cristal | Transparencias y halo suave; se evita el exceso de partículas del ejemplo |
| Selector | Se utiliza un menú realmente oscuro, como pide el usuario, aunque el concepto generado lo dibuja gris claro |
| Capas | Se corrigió el stacking context del cristal para que el interruptor no aparezca por encima del menú; se verifica el hit-test de toda la opción seleccionada |
| Navegación | Enlaces en el footer; no hay recuentos de documentos/vectores en el buscador |
| Copy | Automático y Sugerencias completos; métricas solo en Evaluación y corpus solo en Acerca |
| Resultados | Lectura y expansión protagonistas; score explicado en un detalle secundario |
| Responsive | Dock junto al logo en escritorio y agrupado en filas en móvil, sin superposición |

El chrome y la dirección de navegador dibujados por Image Gen son solo marco del
concepto; no forman parte de la aplicación. No se publican esas direcciones.
La revisión final no encontró desajustes materiales en los tamaños probados.

QA: Playwright/Chromium porque Browser y su skill no están disponibles en esta
sesión. Se comprobaron la identidad de la página, consola, ausencia de overlay,
datos reales, foco, menú, scroll, navegación, búsquedas sucesivas y retorno al inicio.
Las capturas se guardan con las animaciones finalizadas para evaluar la tipografía
y el contraste; las pruebas de movimiento se ejecutan con las animaciones activas.
