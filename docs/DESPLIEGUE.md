# ProyectoRI en Vercel

## URLs públicas verificadas

- **Buscador:** https://fiqa-indol.vercel.app
- **API:** https://fiqa-api.vercel.app
- **Swagger:** https://fiqa-api.vercel.app/docs
- **Recursos completos:** https://fiqa-api.vercel.app/ready

La aplicación ya no depende del backend incompleto de Render. No se modificó
ningún servicio de Render. Se conservaron el diseño del frontend, los algoritmos,
los embeddings y los resultados académicos.

| Proyecto | Root Directory | Ejecución |
|---|---|---|
| `fiqa` | `frontend` | React/Vite estático; Node 24 durante el build |
| `fiqa-api` | `backend` | FastAPI, Python 3.12, PyTorch CPU, Fluid Compute/Large Functions |

Equipo: `fonfini123-1060`, plan **Hobby**. Ambos proyectos incluyen archivos fuera
de Root Directory: el frontend verifica `../results/`; el backend empaqueta
`../src/ri_fiqa`. La configuración sigue siendo Snowball, BM25 `k1=0.8`, `b=0.75`,
RRF `k=10`, peso BGE `0.9`. Automático resuelve a `hybrid`.

## Recursos reproducibles

`backend/pyproject.toml` y `uv.lock` fijan dependencias de Linux/Python 3.12.
Torch procede exclusivamente del índice CPU. No se utiliza el lockfile
Windows/CUDA ni se instalan paquetes de evaluación como `ir-measures`.

`backend/prepare_runtime.py` descarga el [paquete completo de corpus e índices](https://github.com/Cesarbmm/ProyectoRI/releases/tag/fiqa-runtime-v1),
verifica el SHA-256 del archivo y de cada componente, y obtiene BGE base en v1.5,
revisión `a5beb1e3e68b9ab74eb54cfd186867f64f240e1a`, también con hashes por archivo.
El manifiesto está versionado en `backend/assets-manifest.json`.

El build comprueba **57.638 documentos**, **57.600 vectores** y dimensión **768**.
Los 38 documentos vacíos permanecen en el corpus, sin vector, como en el índice
original. No se reconstruyen embeddings ni se descarga el modelo por solicitud:
los recursos quedan incluidos en la Function y Hugging Face funciona offline.

Archivo de corpus/índices: **197.775.593 bytes**, SHA-256
`088a9cd50b858475d160bffd131a8714c0aa506c7a7779c6eaa23d7e3cde3d0d`.
GitHub confirmó el mismo digest. Con los pesos BGE, los recursos verificados suman
**673.988.333 bytes**. `/ready` verifica su integridad una vez por proceso.

## Configuración y CORS

En `fiqa`, Preview y Production tienen variables **separadas**:
`VITE_API_URL=https://fiqa-api.vercel.app`. Es una URL pública, sin credenciales.
Instalación: `npm ci`; build: `npm run build`; salida: `dist`. El build rechaza
una URL ausente, HTTP, local o con credenciales.

En `fiqa-api`, `VERCEL_SUPPORT_LARGE_FUNCTIONS=1`. `RI_RUNTIME_DIAGNOSTICS=1`
solo en Preview y `0` en Production. El build usa
`uv run --frozen python prepare_runtime.py`.

`RI_CORS_ORIGIN_REGEX` permite exclusivamente el patrón de previews de este
proyecto/cuenta:
`^https://fiqa-(?:[a-z0-9-]+-)?fonfini123-1060\.vercel\.app$`.
Production configura además `RI_CORS_ORIGINS` con
`https://fiqa-indol.vercel.app`, `http://localhost:5173`,
`http://127.0.0.1:5173` y `http://localhost:3000`. Se comprobaron GET y preflight
POST reales. No se permiten dominios Vercel arbitrarios ni se usan credenciales
de navegador para buscar.

HTTPS es nativo de Vercel. Deployment Protection permanece activo para previews
y URLs generadas; los dominios de producción anteriores funcionan anónimamente.
La automatización usa `vercel curl`, OIDC limitado al origen del frontend o una
cookie temporal del build preparado. Ninguna credencial se incorpora a Vite,
Git, capturas ni trazas.

## Pruebas y medición

| Comprobación | Resultado |
|---|---|
| Backend unitario | **108 correctas**, incluidas las 82 originales |
| Frontend unitario | **39 correctas** |
| Linux/CPU | Cinco modelos, comparación y recursos completos correctos |
| API Vercel Preview | Salud, integridad, catálogo, cinco búsquedas, comparación y memoria correctos |
| API pública | Cinco búsquedas y comparación correctas, sin autenticación |
| Frontend Preview | `npm run test:deployed` correcto |
| Production preparado | Mismo E2E correcto antes de promover |
| Frontend público | Mismo E2E correcto **sin OIDC, cookies ni storageState** |
| Comparación pública Top-20 | Cinco rankings de 20 documentos; respuesta de 106.689 bytes |
| TypeScript/Vite y benchmark | Build correcto y métricas coincidentes con las fuentes |

El E2E verifica Automático → híbrido, los cinco modelos, rankings/textos/scores
devueltos por HTTP, comparación, CORS y la tabla real de métricas. BGE conserva
el primer documento `263225` para APR/APY. Sin respuestas simuladas ni capturas nuevas.

Vercel reporta una Function de aproximadamente **932 MB**. Ubuntu/WSL midió
aproximadamente **1,32 GB** de RSS. Vercel Preview midió **1.263.628.288 bytes**
de RSS/pico observado con todos los modelos y documentos cargados en un proceso.
`POST /runtime/measure` existe solo en Preview; `/runtime` no se expone en
Production. Los logs registran memoria y duración, sin contenidos de consultas.

Evidencias en `docs/deployment/`: `linux-cpu-api.json`,
`vercel-preview-api.json`, `vercel-staged-api.json`, `vercel-public-api.json`
y `production-cors.json`, `top20-comparison.json` y `observability.json`.
La revisión de 15 minutos devolvió cero errores runtime en la API y cero
respuestas HTTP 5xx en el frontend; se comprobaron muestras reales de logs de memoria.

## Costos y límites

No se activaron recursos de pago, Pro, instancias Performance ni Blob. Las
pruebas se realizaron con **$0 adicionales dentro de Hobby**: 4 horas de CPU
activa, 360 GB-hora y un millón de invocaciones mensuales incluidos. Agotar
cuotas puede pausar el servicio. La Function tiene 2 GB/1 vCPU y 300 segundos.
Large Functions sigue en **beta**, con límite de 5 GB. Existen arranques en frío;
no se realizó una prueba de carga masiva. Referencias:
[Hobby](https://vercel.com/docs/plans/hobby),
[Functions](https://vercel.com/docs/functions/limitations).

Se mantienen dos proyectos para desplegar y revertir la API grande de forma
independiente. Services permitiría un dominio compartido, pero añade otra beta
y acopla despliegues; no es necesario para esta arquitectura verificada.

## Reproducción

En Linux con `uv`, desde `backend/`:

```bash
uv sync --frozen --no-dev
uv run --frozen python prepare_runtime.py
RI_RUNTIME_DIAGNOSTICS=1 uv run --frozen uvicorn main:app --port 8100
```

Desde la raíz, prueba pública de API:

```powershell
python backend/verify_api.py https://fiqa-api.vercel.app --no-diagnostics --report build/public-api.json
```

Desde `frontend/`, navegador público sin credenciales:

```powershell
npm ci
$env:FIQA_FRONTEND_URL='https://fiqa-indol.vercel.app'
$env:FIQA_API_URL='https://fiqa-api.vercel.app'
npm run test:deployed
npm test
npm run build
```

Para futuros releases, usar CLI `66.6.0`, proyecto explícito y scope correcto:
crear Preview, probarlo, preparar Production con `--prod --skip-domain`, probar
ese build y promoverlo. El primer despliegue de un proyecto nuevo exige target
Production; se creó sin dominio antes del Preview, sin modificar el frontend.

Los despliegues usan la CLI sobre los commits del repositorio. La integración
Git automática requiere añadir la Login Connection de GitHub a la cuenta Vercel;
un push por sí solo todavía no publica una versión. Las URLs públicas funcionan
independientemente de esa integración. Detalle: [backend/README.md](../backend/README.md).
