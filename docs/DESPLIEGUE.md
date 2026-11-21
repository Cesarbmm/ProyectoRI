# Despliegue FiQA

## Arquitectura

Frontend React/Vite estático en Vercel; FastAPI, BGE y FAISS en un proceso
persistente de un proveedor de contenedores o VPS. La URL del backend es pública,
HTTPS y se fija en `VITE_API_URL` para Preview y Production. No contiene secretos.

La selección sigue siendo Snowball, BM25 `k1=0.8`, `b=0.75`, RRF `k=10` y peso BGE
`0.9`. No se reconstruyen embeddings, se recortan documentos ni se desactivan modelos.

## Proyecto Vercel preparado

- Proyecto: `fiqa`, cuenta/equipo `fonfini123-1060`.
- Root Directory: `frontend`.
- Framework: Vite. Node: `24.x`.
- Install: `npm ci`. Build: `npm run build`. Output: `dist`.
- **Include source files outside of Root Directory**: activado. La comprobación
  del benchmark necesita `../results/`, no solo el JSON empaquetado del frontend.
- Archivo versionado: `frontend/vercel.json`.
- El build en Vercel rechaza una URL ausente, HTTP, local o con credenciales.
  El desarrollo local sigue usando la API local.
- `.vercel/` y todos los archivos de entorno locales están excluidos de Git.

El MCP de Vercel no expuso herramientas en esta sesión aunque el plugin figuraba
habilitado. Se utilizó la CLI oficial `66.6.0` con acceso autorizado mediante OAuth.

## Capacidad del backend

Recursos existentes, sin alterar:

| Recurso | Tamaño |
|---|---:|
| Corpus Arrow, 57.638 documentos | 45.324.568 bytes |
| Índice Snowball comprimido | 12.076.326 bytes |
| FAISS, 57.600 vectores de 768 dimensiones | 176.947.245 bytes |
| Pesos BGE base en v1.5 | 437.955.512 bytes |

Solo FAISS y los pesos ya superan el límite estándar de 500 MB de una función
Python. La documentación actual permite **Large Functions de hasta 5 GB en beta**;
por tanto, el tamaño no prueba una imposibilidad absoluta. El plan Hobby limita
la memoria a 2 GB y la duración a 300 s. La inicialización repetida y el almacenamiento
del modelo/corpus requieren validación específica de la plataforma. No se declara
fiable una migración serverless a partir de una prueba en Windows.

La medición [local-cpu-profile.json](deployment/local-cpu-profile.json) ejecutó
los cinco modelos con el corpus e índices completos, sin descargar pesos:
BGE inicial 10,4 s; proceso residente final aproximadamente 1,07 GB. La memoria
privada comprometida alcanzó 7,79 GB con el PyTorch CUDA instalado en Windows;
**no equivale al RSS ni a una medida de PyTorch CPU en Linux**. No permite fijar
por sí sola el tamaño de una instancia Linux.

Recomendación: contenedor Linux con PyTorch CPU, un worker Uvicorn y recursos
persistentes. Render admite este patrón y disco persistente en planes de pago;
un VPS con Docker también es adecuado. Se debe medir en Linux antes de elegir
el plan mínimo. No se crean recursos facturables sin concretar proveedor y coste.

Referencias verificadas:

- [Límites actuales de Vercel Functions](https://vercel.com/docs/functions/limitations).
- [Archivos y monorepos en Vercel](https://vercel.com/docs/monorepos/monorepo-faq).
- [Discos persistentes de Render](https://render.com/docs/disks).
- [Planes de cómputo de Render](https://render.com/docs/compute-plans).

## Backend, HTTPS y CORS

El backend completo debe tener el corpus, el índice Snowball y los tres archivos
de `semantic_bge/`, además del encoder BGE original y sus prompts. Estos recursos
están excluidos de Git; clonar el repositorio **no los instala**.

El proveedor debe terminar TLS y entregar una URL HTTPS estable. Configurar en el
backend `RI_CORS_ORIGINS` con los orígenes exactos del frontend de prueba y de
producción, separados por comas y sin rutas ni barras finales. El middleware
existente ya permite GET, POST, Content-Type y no usa credenciales de navegador.
Reiniciar el proceso para aplicar cambios de CORS.

No permitir todos los dominios `*.vercel.app`: cada despliegue de prueba tiene
su origen propio y debe autorizarse expresamente. `/ready` comprueba estructura;
la prueba de abajo también ejecuta todos los modelos para comprobar la carga real.

## Comprobación antes de publicar

Desde `frontend/`, con URLs reales:

```powershell
$env:FIQA_FRONTEND_URL='https://<preview-verificado>.vercel.app'
$env:FIQA_API_URL='https://<backend-completo>'
npm run test:deployed
```

Esta prueba no arranca servidores, no simula respuestas y no captura imágenes.
Comprueba salud, recursos, catálogo/configuración, CORS real, preflight, los cinco
modelos, Automático, scores y textos devueltos por HTTP, comparación y métricas
académicas. Conserva la regresión BGE APR/APY: primer documento `263225`.

Para comprobar únicamente la propia prueba contra el entorno local se admite
`FIQA_ALLOW_LOCAL_SMOKE=1`; ese resultado **no es una validación pública**.

Después de probar Preview, crear un build de Production sin asignar dominios,
autorizar su origen en CORS y repetir el recorrido:

```powershell
# Desde la raíz enlazada y con VITE_API_URL configurada en Vercel:
npx --yes vercel@66.6.0 deploy --prod --skip-domain
# Ejecutar npm run test:deployed sobre esa URL exacta.
npx --yes vercel@66.6.0 promote <url-production-validada>
```

La promoción se realiza únicamente al pasar las comprobaciones. La URL estable
de producción también debe estar permitida en CORS; repetir el smoke test sobre
esa URL tras promocionar. No promover Preview como atajo: Vercel puede reconstruir
con otras variables de Production.

## Estado de esta fase

Proyecto configurado; publicación de prueba y producción pendientes de una URL
HTTPS del backend completo y de configurar sus orígenes CORS. No hay una URL
pública funcional validada todavía. Pruebas locales: 39 unitarias, build y un
recorrido E2E completo de los cinco sistemas correctos. Sin nuevas capturas.
