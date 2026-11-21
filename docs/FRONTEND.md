# Frontend definitivo FiQA — entrega local

Implementado en `frontend/` con React 19, Vite 7 y TypeScript estricto. Se aplicó
la skill `frontend-app-builder`: concepto Image Gen, sistema visual, implementación
modular y comparación de capturas. La idea de `ejemplo.html` se conserva en el
estructura de componentes; los HTML de referencia no se modifican. El refinamiento
actual utiliza `forja-buscador-claro.html` como referencia de movimiento y cristal.

Esta fase no publica el frontend ni el backend. No se utilizó el complemento de
Vercel ni se crearon servicios de alojamiento.

## Estructura y archivos

```text
frontend/
  .env.example
  package.json / package-lock.json
  index.html / vite.config.ts / tsconfig.json / playwright.config.ts
  public/favicon.svg
  design/concepto.png / README.md
  scripts/sync-benchmark.mjs
  src/
    App.tsx / main.tsx / styles.css
    components/
      SearchForm.tsx    # Consulta, Top-K, comparación y sugerencias
      ModelSelect.tsx   # Selector oscuro accesible, independiente del popup nativo
      Results.tsx       # Rankings reales y expansión de documentos
      Benchmark.tsx     # Evaluación final, tabla y gráficas
      About.tsx / Icon.tsx
    lib/
      api.ts / types.ts # Contrato y validación de las respuestas de FastAPI
      useEngine.ts      # Salud, recursos, modelos, reconexión y sondeo
      useSearch.ts      # Búsqueda, comparación, cancelación y estado
      useDockMotion.ts  # Transición FLIP y retorno al inicio
      benchmark.ts
    data/benchmark.json # Solo métricas académicas con procedencia
    refinement.css     # Refinamiento visual sobre el sistema existente
  tests/                # Vitest y Testing Library
  e2e/                  # Playwright con API y corpus completos
docs/capturas/           # Capturas reales de las pantallas principales
```

También se actualizan `.gitignore` (dependencias y salidas temporales) y el README
principal. **No se cambia ningún archivo de `src/ri_fiqa`, `tests/`, `scripts/`
del backend ni `results/`**, ni los hiperparámetros, el encoder o FAISS.

## Instalación y desarrollo

Requisitos: Node **22.12+** (entorno comprobado: Node 24.14.1 y npm 11.11.0), el
entorno Python del proyecto y los recursos completos de FiQA ya preparados.

Primera terminal, desde la raíz del repositorio:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn ri_fiqa.api:app --host 127.0.0.1 --port 8000
```

Segunda terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Abrir <http://127.0.0.1:5173>. `.env.local`:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

`VITE_API_URL` es pública y se incorpora durante el build; no debe contener
secretos. Reiniciar Vite tras cambiarla y reconstruir para cambiarla en producción.
Se admite una URL con prefijo de ruta y se eliminan las barras finales.
[Referencia oficial de Vite](https://vite.dev/guide/env-and-mode).

La configuración CORS actual de FastAPI admite `http://127.0.0.1:5173` y
`http://localhost:5173`. Para otra dirección, definir `RI_CORS_ORIGINS` en el
**backend**, con el origen exacto. El origen de `npm run preview` es distinto
(`4173`); añadirlo si se quiere probar la compilación servida con ese comando.

## Conexión y comportamiento

| Endpoint | Uso |
|---|---|
| `GET /health` | Comprueba que la API responde |
| `GET /ready` | Exige recursos preparados antes de permitir búsquedas |
| `GET /models` | Obtiene los cinco modelos reales y la configuración léxica |
| `POST /search` | Envía consulta, modelo resuelto y Top-K |
| `POST /search/compare` | Solicita rankings separados para entre 2 y 5 modelos |

Las comprobaciones iniciales se ejecutan en paralelo. Se comprueba nuevamente la
conexión cada 30 segundos y ante cambios de conectividad; también existe un
botón de reconexión cuando falta el servidor. El estado conectado exige que las
tres comprobaciones sean correctas. La API se consulta directamente, sin proxy
de desarrollo obligatorio, lo que conserva el mismo contrato para la siguiente
fase de despliegue.

Automático comienza seleccionado y resuelve **exclusivamente a `hybrid`**. Se
informa “Automatic selected Hybrid BM25 + BGE” al recibir una búsqueda correcta.
Se ignora el `default_model=bge` del servidor solo para esta preferencia explícita
del producto; los modelos y sus algoritmos no cambian.

Las sugerencias rellenan la consulta y sitúan el foco en el campo. Buscar o Enter
envía la solicitud. Top-K admite 3, 5, 10 y 20. La comparación usa su propio conjunto
de modelos y exige al menos dos. Cada documento muestra posición, ID, fragmento,
un control nativo `details` para leer el texto completo. La puntuación lleva una
etiqueta específica: Term overlap (Jaccard, porcentaje), Text similarity (TF-IDF),
Lexical score (BM25), Semantic affinity (BGE) o Fusion score (híbrido). El botón de
información explica su significado y `Technical score` conserva el valor exacto
de la API. Las etiquetas redondeadas no cambian los scores ni el orden del ranking.
La consulta y las opciones se conservan al cambiar de vista.

Se muestran tiempos `elapsed_ms` devueltos por FastAPI, tanto totales como por
ranking. No se etiquetan como tiempo total de red o renderizado. Los scores no
son probabilidades y no se comparan entre modelos.

Se manejan HTTP 422, 503, otros errores HTTP, JSON inválido, contrato incompatible,
desconexión, resultados vacíos y cancelación. No se sustituyen errores por listas
de ejemplo. Los controles de entrada se bloquean durante una solicitud y se
ofrece Cancelar. El timeout de búsqueda es 130 segundos para permitir la carga
inicial de BGE; salud/recursos/modelos usan 10 segundos. Cancelar descarta la
respuesta en el cliente; no garantiza detener una inferencia que FastAPI ya
esté ejecutando.

## Métricas, configuración vigente y procedencia

Las métricas pertenecen a **FiQA test: 648 consultas**, con qrels y profundidad
1.000. Se publican MAP@1000, Precision@10 (`P@10` en los JSON), Recall@100 y NDCG@10.
No se calcula ninguna de estas métricas para consultas libres.

| Serie | Fuente | MAP@1000 híbrido |
|---|---|---:|
| Configuración final · Snowball | `results/preprocessing_v1/final_test/stemming_<modelo>_test.json` | 0.349604 |

BGE utiliza su resultado original porque no se modificó. La interfaz muestra
exclusivamente la configuración final en Evaluación; no hay métricas en el
buscador ni selector de series históricas. Los resultados históricos se conservan
en los archivos y en la exportación de datos para trazabilidad, sin exponerse
como configuración de la búsqueda actual. No se utiliza la etiqueta «Baseline»
en la interfaz. El benchmark se identifica por configuración y split y se
distingue de la latencia y puntuación de una búsqueda.

Automático usa el híbrido final; no afirma significación estadística de su
pequeña ventaja sobre BGE. Las
búsquedas actuales se realizan con el servicio Snowball ya congelado:
BM25 `k1=0.8`, `b=0.75`; RRF `k=10`, peso BGE `0.9`. No se revierte ni reajusta esa
configuración para reproducir un número histórico.

`frontend/scripts/sync-benchmark.mjs` lee los archivos académicos, comprueba split,
número de consultas y rango de métricas, y exporta únicamente agregados. Registra
archivo fuente y SHA-256 con saltos de línea canonizados. La serie vigente se
contrasta con `selection_frozen.json`. `npm run build` ejecuta `benchmark:check`
y falla si el JSON del frontend deja de coincidir con las fuentes reales.

```powershell
# Solo si cambian legítimamente los archivos fuente del benchmark:
npm run benchmark:sync
npm run benchmark:check
```

Esto no ejecuta evaluaciones ni modifica resultados académicos. La procedencia
se conserva en los datos y scripts; se retiró su bloque desplegable de la interfaz.

## Corpus completo verificado

Se comprobó directamente en esta máquina:

- `datasets.load_from_disk('data/raw/corpus')`: **57.638 documentos**.
- `faiss.read_index('data/processed/semantic_bge/index.faiss').ntotal`:
  **57.600 vectores**.
- `semantic_bge/metadata.json`: 57.638 procesados y **38 documentos vacíos
  excluidos**. La auditoría versionada también registra esas 38 exclusiones.
- La configuración efectiva es Snowball y BM25 `0.8/0.75`, sin cambios.

El navegador no indexa, descarga ni sustituye el corpus por una muestra. Para
consultas reales necesita este backend completo y sus archivos existentes. Las
cifras de corpus en la interfaz describen los recursos del proyecto verificados;
no son un contador calculado mediante resultados de una búsqueda.

## Pruebas ejecutadas

```powershell
# Desde la raíz:
python -m unittest discover -s tests

# Desde frontend/:
npm test
npx playwright install chromium
npm run test:e2e
npm run build
npm run format:check
```

| Comprobación | Resultado |
|---|---|
| Backend | **104 pruebas correctas**, incluidas las 82 originales |
| Frontend, Vitest/Testing Library | **29 pruebas correctas** |
| Playwright, validación completa previa | **25 pruebas correctas**: 8 desktop, 8 tablet, 8 móvil y 1 recorrido completo de API real |
| Playwright, revisión rápida en inglés | **16 pruebas correctas**: 8 desktop y 8 móvil, con búsquedas reales y sin nuevas capturas |
| Compilación TypeScript y Vite | Correcta; artefacto estático en `frontend/dist/` |
| Sincronización del benchmark | Coincide con los resultados fuente |
| Formato | Prettier correcto |
| Accesibilidad automática | Sin infracciones detectadas por axe en inicio y resultados de los tres tamaños comprobados |
| Consola/navegador | Sin errores de aplicación en el recorrido real; sin overlay de Vite ni pantalla vacía |

Playwright inicia Vite y Uvicorn si no existen y usa un único worker para la API
compartida. Detecta `.venv/Scripts/python.exe` en Windows o `.venv/bin/python`
en Linux; `FIQA_PYTHON` permite otra ruta. Las pruebas arrancan FastAPI con
`HF_HUB_OFFLINE=1`: los pesos BGE deben estar ya descargados. Una ejecución que
carece de índices completos no se convierte en una prueba simulada ni se omite
silenciosamente.

Los recorridos positivos pasan por la API real: Automático, cambio a cada uno de
los cinco modelos, Top-K, Enter, expansión, ranking vacío real y comparación de
los cinco modelos. Se compara el fragmento visible con la respuesta HTTP y se
conserva la regresión BGE: primer documento `263225` para APR/APY.

Solo las pruebas de fallo inyectan HTTP 503 o una desconexión, y la prueba de
carga retrasa el transporte. No hay interceptores, fixtures ni respuestas
estáticas de búsquedas en el código de producción. Las llamadas de prueba se
interceptan con Playwright únicamente dentro de `e2e/`.

Entorno: Chromium de Playwright, `http://127.0.0.1:5173`, API
`http://127.0.0.1:8000`. Viewports 1440×1000, 820×1180 y 390×844; capturas de
entrega de escritorio a 1488×1057. Se verificaron identidad de página, contenido,
ausencia de overlay, consola, foco, ausencia de overflow horizontal y transición
de cada interacción al estado esperado. Se usó Playwright porque el plugin
Browser y su skill no están disponibles en esta sesión. No se probaron aún
Firefox, Safari ni un backend remoto en HTTPS.

Las pruebas de cancelación pueden producir un `ConnectionResetError` de asyncio
en el log de Uvicorn sobre Windows al cerrar una conexión en curso. La interfaz
descarta correctamente la solicitud y la suite sigue pasando; no se modificó el
backend para ocultar ese evento de transporte.

## Refinamiento de búsqueda y movimiento

La vista inicial ocupa el espacio central con FiQA grande y una barra ampliada;
se eliminaron el header de navegación y el panel lateral de métricas. El footer
solo contiene conexión y enlaces a Evaluación/Acerca (y Buscar en esas vistas).
Las cifras del corpus siguen disponibles en Acerca.

El selector muestra «Automático», sin recortes, con una flecha visible y un menú
oscuro propio. Admite ratón/táctil y teclado: flechas, Home, End, Enter, Espacio,
Escape y Tab. La selección se informa mediante roles de combobox/listbox y no
depende del estilo de los menús nativos de Windows. Top-K conserva el selector
nativo, con esquema oscuro.

La transición inicial reduce y desplaza el mismo logo y barra mediante FLIP;
ambos quedan en un dock sticky. Los resultados aparecen debajo al terminar esa
transición. Las nuevas búsquedas conservan el dock, el campo y su configuración.
FiQA vuelve al inicio con scroll y movimiento suaves. Las Sugerencias siguen
disponibles, plegadas en la barra compacta para ahorrar espacio.

El movimiento se omite con `prefers-reduced-motion`. Las pruebas verifican la
identidad del campo antes/después, el tamaño y desplazamiento del logo, que la
barra siga visible al hacer scroll, la segunda búsqueda real y el retorno al
inicio sin resultados residuales. La configuración y respuestas de FastAPI se
conservan intactas. Ver [diseño y revisión](../frontend/design/refinamiento.md).

La interfaz está completamente en inglés, incluidos errores, ayudas accesibles
y formatos numéricos. El punto del logo recorre su elipse cada 22 segundos mediante
CSS Motion Path; también se desactiva con movimiento reducido. La revisión rápida
de esta fase comprueba etiquetas, valores exactos, conservación del ranking,
controles de información, idioma, animación y navegación, sin nuevas capturas.

Tras corregir el orden de capas del cristal, se repitieron correctamente otros
4 recorridos de menú/API: tres tamaños de pantalla y el recorrido completo real.
Se comprueba que el interruptor no cubra ninguna parte de la opción seleccionada.

## Diseño y capturas

Paleta gris perla `#F4F4F6`, `#E7E7E7`, `#D2D2D4` y coral `#FF634A`, con grafito
para lectura y menú oscuro. Glassmorphism moderado, tipografías locales, búsqueda
central y navegación exclusivamente en el footer. Se revisó con `view_image` el
concepto y el render final: composición, paleta, marca, tipografía, controles,
espaciado y móvil. El registro de fidelidad y las
diferencias funcionales deliberadas están en
[`frontend/design/refinamiento.md`](../frontend/design/refinamiento.md).

Capturas obtenidas con la API real, con animaciones finalizadas para no congelar
contenido a media opacidad:

- [Inicio](capturas/inicio.png)
- [Selector de modelos](capturas/selector-modelos.png)
- [Resultados del híbrido](capturas/resultados.png)
- [Comparación de rankings](capturas/comparacion.png)
- [Evaluación](capturas/evaluacion.png)
- [Acerca del sistema](capturas/acerca.png)
- [Inicio móvil](capturas/movil.png)
- [Resultados móviles](capturas/movil-resultados.png)
- [Servidor desconectado](capturas/desconectado.png)

Las capturas anteriores se conservan como registro de la fase previa; esta revisión
no las regenera. Playwright no toma capturas por defecto, tampoco en los fallos.
Para regenerarlas explícitamente en otra fase, ejecutar en PowerShell
`$env:FIQA_CAPTURE="1"; npm run test:e2e:real; Remove-Item Env:FIQA_CAPTURE`.
Las trazas temporales y dependencias quedan excluidas de Git.

## Preparación para la fase siguiente

El artefacto `frontend/dist/` es estático y se genera con `npm ci && npm run build`.
Antes de cualquier despliegue futuro habrá que configurar `VITE_API_URL` con la
URL HTTPS del **backend completo**, configurar CORS allí y repetir los flujos
reales. `127.0.0.1` apunta al equipo donde se abre el navegador y no sirve como
dirección de un backend remoto. Publicar solo este frontend no publica los
modelos, los datos ni FastAPI.

No se han creado archivos de despliegue específicos de Vercel ni se ha publicado
esta fase. La configuración y resultados académicos están conservados.
