
# FiQA — Contrato de integración frontend/backend

## Base URL local

http://127.0.0.1:8000

## Endpoints

### GET /health
Comprueba que el proceso HTTP responde.

### GET /ready
Comprueba la presencia de índices, corpus y metadatos.
- 200: recursos preparados.
- 503: faltan recursos o hay inconsistencias.

### GET /models
Devuelve los modelos para el selector de búsqueda.

Identificadores admitidos:
- jaccard
- tfidf
- bm25
- bge
- hybrid

Modelo predeterminado: bge.

### POST /search
Content-Type: application/json

Solicitud:

{
  "query": "What is APR?",
  "model": "bge",
  "top_k": 5
}

Respuesta:
- query: consulta original
- model: identificador del modelo utilizado
- count: número de documentos recuperados
- elapsed_ms: tiempo de búsqueda en el servidor
- results: lista de documentos

Cada resultado contiene:
- rank: posición (comienza en 1)
- doc_id: identificador original de FiQA
- score: puntuación del modelo
- text: texto documental completo
- preview: fragmento para mostrar en la interfaz

Restricciones:
- query: 1 a 500 caracteres no vacíos
- top_k: entre 1 y 20
- model: uno de los cinco identificadores

### POST /search/compare
Ejecuta una consulta con entre 2 y 5 modelos distintos.

## Errores HTTP
- 422: solicitud inválida
- 503: recursos del motor no disponibles
- 500: error interno inesperado

## Notas de integración
- Las puntuaciones no son probabilidades.
- No comparar directamente los scores de distintos modelos.
- Mostrar la posición, el texto y el identificador.
- Presentar un estado de carga durante la solicitud.
- Mostrar un mensaje claro cuando no se obtengan resultados.
- No modificar ni calcular relevancias en el frontend.
```

### Ejemplo mínimo para conectar la barra de búsqueda

Este JavaScript es independiente de React, Vue o cualquier otro framework:

<CodeBlock language="javascript" editable>
const API_URL = "http://127.0.0.1:8000";

export async function obtenerModelos() {
  const response = await fetch(`${API_URL}/models`);

  if (!response.ok) {
    throw new Error("No se pudieron cargar los modelos.");
  }

  return await response.json();
}

export async function buscarDocumentos(
  consulta,
  modelo = "bge",
  cantidad = 5
) {
  const response = await fetch(`${API_URL}/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      query: consulta,
      model: modelo,
      top_k: cantidad
    })
  });

  if (!response.ok) {
    if (response.status === 422) {
      throw new Error("Revisa la consulta y el modelo.");
    }

    if (response.status === 503) {
      throw new Error("El motor de búsqueda no está disponible.");
    }

    throw new Error("No se pudo completar la búsqueda.");
  }

  return await response.json();
}
