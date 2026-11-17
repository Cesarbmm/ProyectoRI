# Entrega técnica al equipo frontend — FiQA

## Lo que ya está implementado

- API REST con FastAPI y documentación Swagger en `/docs`.
- Cinco sistemas seleccionables: `jaccard`, `tfidf`, `bm25`, `bge`, `hybrid`.
- Los endpoints `/health`, `/ready`, `/models`, `/search` y `/search/compare` están probados.
- Última ejecución: 82 pruebas unitarias/HTTP aprobadas y verificación integral satisfactoria.
- La selección y evaluación de parámetros está finalizada. **No modificar los algoritmos para desarrollar el frontend.**

## Qué debe implementar el frontend

1. Una barra de búsqueda para escribir texto libre.
2. Un selector junto a la barra que use los identificadores devueltos por `GET /models`.
3. Un botón o envío con Enter para llamar a `POST /search`.
4. Resultados ordenados que muestren posición, fragmento, documento ID y, si se desea, texto expandible.
5. Un indicador de carga y estados de error/vacío.
6. Opcional: un modo de comparación con `/search/compare`.

## Contrato mínimo

`POST /search` con `Content-Type: application/json`:

```json
{"query":"How can I invest for retirement?","model":"bge","top_k":5}
```

Respuesta: `query`, `model`, `count`, `elapsed_ms`, `results[]`, y cada elemento de `results` incluye `rank`, `doc_id`, `score`, `text`, `preview`.

Ejemplo en JavaScript:

```javascript
const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

export async function buscar(query, model = 'bge', top_k = 5) {
  const res = await fetch(`${API_URL}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, model, top_k }),
  });
  if (!res.ok) throw new Error(`Error de búsqueda (HTTP ${res.status})`);
  return res.json();
}
```

## Ejecutar el backend en el mismo equipo

Desde el directorio clonado, tras instalar dependencias y generar/restaurar los índices (ver `README.md`):

```powershell
Copy-Item .env.example .env
python -m uvicorn ri_fiqa.api:app --host 127.0.0.1 --port 8000 --reload --env-file .env
```

Abrir <http://127.0.0.1:8000/docs> y <http://127.0.0.1:8000/models>. El frontend de Vite suele usar <http://localhost:5173>.

## Qué no incluye Git

**Clonar el repositorio no basta para ejecutar búsquedas reales:** se excluyen corpus FiQA, índices invertidos, FAISS, IDs y modelos descargados. Ver instrucciones de reconstrucción en `README.md`. Para trabajar exclusivamente en el frontend, usar una API accesible que ya tenga esos recursos; no es necesario instalar Python si solo se desarrolla la interfaz.

## Alojamiento futuro

- Frontend estático: puede publicarse independientemente, por ejemplo mediante Vercel.
- Backend: necesita proceso Python, índices persistentes, pesos BGE, memoria, HTTPS y CORS con el dominio público.
- `127.0.0.1` solo funciona cuando el navegador y la API están en el mismo equipo; cambiar `VITE_API_URL` por una URL accesible para pruebas distribuidas.
- No exponer la API directamente a internet sin revisar los límites de uso, seguridad y los recursos del proveedor.

## Errores a manejar

- HTTP 422: consulta/modelo/top_k inválidos.
- HTTP 503: recursos no disponibles.
- HTTP 500: error inesperado.
- Tiempo de primera búsqueda semántica mayor por la carga inicial de BGE.

**Importante:** el `score` no es un porcentaje de certeza y no es comparable entre distintos modelos. El backend recupera documentos, no redacta una respuesta generativa.
