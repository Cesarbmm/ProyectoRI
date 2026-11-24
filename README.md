# FiQA — Motor de Recuperación de Información

## Enlaces de entrega

- **Link al PDF — Informe final:** [Abrir el informe en PDF](https://github.com/Cesarbmm/ProyectoRI/blob/main/docs/InformeProyecto.pdf)
- **Link a la página web — Buscador FiQA:** [Abrir FiQA en Vercel](https://fiqa-indol.vercel.app/)

Proyecto académico de **Recuperación de Información (RI)** sobre el corpus financiero **FiQA (BEIR)**. Datos de referencia: `BeIR/fiqa` (corpus y consultas) y `BeIR/fiqa-qrels` (juicios de relevancia). Implementa cuatro familias de recuperación, un sistema híbrido y una API REST para integrarse con una interfaz web.

La web ofrece únicamente **Jaccard, TF-IDF, BM25 y BGE + FAISS**. La opción
predeterminada es **Default (BGE + FAISS)**. El híbrido se conserva para
reproducción histórica y como fila histórica en Evaluación, sin ser seleccionable.

> **Estado:** frontend y API desplegados y verificados en Vercel. Los archivos de datos y los índices no se almacenan en Git.

El frontend definitivo está en [`frontend/`](frontend/), con búsqueda real,
comparación de modelos y evaluación de la configuración final Snowball. Consulta la
[guía de instalación, pruebas y capturas](docs/FRONTEND.md).

## Modelos disponibles

| Identificador | Método | Implementación |
|---|---|---|
| `jaccard` | Similitud binaria de Jaccard | Índice invertido propio |
| `tfidf` | TF-IDF con similitud de coseno | Índice invertido propio |
| `bm25` | BM25 (`k1=0.8`, `b=0.75`, Snowball) | Índice invertido propio |
| `bge` | Embeddings BGE-base-en-v1.5 + FAISS | Índice vectorial exacto |
| `hybrid` | RRF ponderado de BM25 y BGE | `k=10`, peso BGE `0.9` |

Los modelos léxicos no dependen de Whoosh, Elasticsearch ni Solr. El híbrido es una extensión experimental, no reemplaza los cuatro modelos obligatorios.

### Resultados de referencia históricos (baseline léxico)

Evaluación en **FiQA test**: 648 consultas, profundidad 1.000. La selección de parámetros se realizó previamente sobre `validation`, sin reajustes usando `test`.

| Modelo | MAP@1000 | NDCG@10 | Recall@100 |
|---|---:|---:|---:|
| Jaccard | 0.037510 | 0.047394 | 0.194680 |
| TF-IDF | 0.128536 | 0.158654 | 0.455322 |
| BM25 | 0.191335 | 0.234115 | 0.520526 |
| BGE | 0.347148 | 0.406231 | 0.741472 |
| Híbrido | **0.350006** | **0.408302** | **0.745461** |

Las métricas se contrastaron con `ir-measures`. La ventaja del híbrido sobre BGE individual es pequeña; el análisis exploratorio en `validation` no encontró significación estadística para esa diferencia.

### Configuración final de preprocesamiento

Se compararon baseline, Snowball y WordNet nominal con las mismas **500 consultas
de validation**, reconstruyendo sus índices y optimizando BM25 con la misma
rejilla para cada variante. El criterio principal fue MAP@1000 medio entre
Jaccard, TF-IDF, BM25 e híbrido:

| Configuración | MAP@1000 global | Cambio vs baseline | p Holm pareada |
|---|---:|---:|---:|
| Baseline | 0.184091 | — | — |
| **Snowball (seleccionada)** | **0.197320** | **+7.19%** | **0.000200** |
| WordNet nominal | 0.190588 | +3.53% | 0.009999 |

La configuración final común a los modelos léxicos es **Snowball**, con BM25
`k1=0.8`, `b=0.75`. BGE y FAISS se conservan intactos, y RRF mantiene `k=10`,
peso BGE `0.9`. Snowball mejora especialmente TF-IDF y BM25; el híbrido pierde
un **0.21% relativo de MAP en validation**, diferencia no significativa.
La selección admite pérdidas individuales de hasta un 2% relativo por métrica,
según el límite fijado antes de evaluar. La inferencia es exploratoria porque
la optimización y los contrastes comparten validation.

Después de congelar la selección se evaluó únicamente Snowball en las **648
consultas de test**, sin reajustes: MAP@1000 de Jaccard `0.038587`, TF-IDF
`0.141153`, BM25 `0.210294` e híbrido `0.349604`.

Consulta la [tabla completa, análisis estadístico y comandos de reproducción](docs/EXPERIMENTOS_PREPROCESAMIENTO.md),
la [selección congelada](results/preprocessing_v1/selection_frozen.json) y las
[métricas nuevas](results/preprocessing_v1/). Los resultados históricos de la
tabla anterior no se han modificado. El baseline sigue disponible con
`PreprocessConfig(morphology="baseline")`.

## Arquitectura

```text
src/ri_fiqa/
  preprocessing.py          # Normalización y tokenización
  preprocessing_experiment.py # Protocolo y selección pareada de morfología
  indexing.py               # Índice invertido propio
  retrieval/                # Jaccard, TF-IDF, BM25, BGE/FAISS y RRF
  embedding_models.py       # Perfiles MiniLM/BGE/E5
  config.py                 # Parámetros seleccionados
  search_service.py         # Servicio unificado y caché de modelos
  evaluation.py             # Métricas y exportador TREC
  statistics.py             # Comparaciones pareadas
  runtime.py                # Comprobación de archivos
  api.py                    # FastAPI
scripts/                    # Preparación, indexación, evaluación y diagnóstico
tests/                      # Pruebas unitarias y de API
docs/API_FRONTEND.md        # Contrato de integración
results/                    # Métricas JSON y reportes (sin rankings .trec)
data/raw/                   # Generado localmente; ignorado por Git
data/processed/             # Índices generados; ignorados por Git
```

![Arquitectura final de FiQA: selector de modelos, recuperación léxica y semántica](docs/arquitectura_fiqa.webp)

## Requisitos

- Python **3.11** recomendado, Git y acceso a internet para descargar corpus y modelos.
- La API y los modelos léxicos pueden ejecutarse en CPU.
- Para indexación y consulta BGE se recomienda una GPU NVIDIA compatible con PyTorch/CUDA, **pero no es obligatoria**; CPU es más lento.
- Los recursos de FiQA son **indispensables** para búsquedas reales; un `git clone` por sí solo no incluye corpus, índices ni pesos del encoder.

### 1. Clonar y crear el entorno (Windows / PowerShell)

```powershell
git clone URL_DEL_REPOSITORIO
cd recuperacion-fiqa
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

**Opción GPU NVIDIA (entorno comprobado en Windows):**

```powershell
python -m pip install torch==2.9.1 --index-url https://download.pytorch.org/whl/cu128
python -m pip install -r requirements.txt
python -m pip install -e .
python -c "import torch; print('CUDA disponible:', torch.cuda.is_available())"
```

**Opción CPU:**

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

> `requirements-lock.txt` registra el entorno de desarrollo validado (Windows + CUDA). No es una receta universal para Linux/CPU: utiliza `requirements.txt` y la instalación de PyTorch apropiada para el equipo. Consulta la documentación oficial de PyTorch si cambia la plataforma.

### 2. Preparar los datos e índices

Los siguientes comandos son necesarios si no dispones de una copia autorizada de los recursos ya generados:

```powershell
python scripts/preparar_datos.py
python scripts/construir_indice.py
python scripts/construir_indice_semantico.py --name semantic_bge --encoder bge --batch-size 16
```

El último paso descarga `BAAI/bge-base-en-v1.5` y genera embeddings para los 57.600 documentos no vacíos. Puede requerir bastante memoria y tiempo, especialmente en CPU. Un token `HF_TOKEN` es opcional para modelos públicos; **no lo guardes en Git**.

Rutas esperadas:

```text
data/raw/corpus/
data/raw/queries/
data/raw/qrels/
data/processed/inverted_index_stopwords.json.gz
data/processed/inverted_index_stemming.json.gz
data/processed/semantic_bge/index.faiss
data/processed/semantic_bge/doc_ids.json
data/processed/semantic_bge/metadata.json
```

Si el docente/equipo ya cuenta con recursos generados y se permite compartirlos, pueden transferirse **fuera del repositorio** respetando estas rutas. No se deben subir pesos, corpus ni índices grandes directamente al Git convencional.

### 3. Configurar variables de entorno

```powershell
Copy-Item .env.example .env
```

Valores previstos en `.env`:

```dotenv
RI_DEVICE=auto
RI_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000
# RI_PROJECT_ROOT=C:\ruta\al\proyecto
```

- `RI_DEVICE`: `auto`, `cpu` o `cuda`.
- `RI_CORS_ORIGINS`: orígenes **exactos** permitidos para el navegador, separados por comas.
- `RI_PROJECT_ROOT`: opcional; si se omite, el proyecto detecta su raíz automáticamente.

### 4. Iniciar la API

```powershell
python -m uvicorn ri_fiqa.api:app --host 127.0.0.1 --port 8000 --reload --env-file .env
```

Verificaciones locales:

- Salud HTTP: <http://127.0.0.1:8000/health>
- Recursos disponibles: <http://127.0.0.1:8000/ready>
- Lista de modelos: <http://127.0.0.1:8000/models>
- Documentación interactiva (Swagger): <http://127.0.0.1:8000/docs>

`/health` comprueba el proceso; `/ready` comprueba archivos y metadatos sin cargar el modelo neuronal. La primera solicitud semántica puede demorar más por la carga inicial de BGE.

### 5. Buscar desde PowerShell

En otra terminal, con la API levantada:

```powershell
$body = @{
  query = 'What is the difference between APR and APY?'
  model = 'bge'
  top_k = 3
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/search' `
  -Method Post -ContentType 'application/json; charset=utf-8' -Body $body
```

También se puede usar la consola sin HTTP:

```powershell
python scripts/buscar.py --model bm25 --query 'How can I invest for retirement?' --top 5
python scripts/buscar.py --model bge --interactive
```

## Contrato HTTP para el frontend

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Proceso en funcionamiento |
| `GET` | `/ready` | Recursos listos (HTTP 200) o incompletos (HTTP 503) |
| `GET` | `/models` | Lista de identificadores y nombres del selector |
| `POST` | `/search` | Búsqueda con un modelo |
| `POST` | `/search/compare` | Comparación opcional de 2 a 5 modelos |

**Solicitud principal:**

```json
{
  "query": "What is APR?",
  "model": "bge",
  "top_k": 5
}
```

**Respuesta:** `query`, `model`, `count`, `elapsed_ms`, `results`. Cada documento contiene `rank`, `doc_id`, `score`, `text` y `preview`.

Restricciones: consulta no vacía de hasta 500 caracteres; `top_k` entre 1 y 20; identificador de modelo válido. Errores habituales: `422` solicitud inválida; `503` faltan recursos. Los `score` no son probabilidades ni deben compararse entre modelos.

**Para el frontend:** consulta `GET /models` al iniciar la página, muestra esos nombres en el selector a la derecha de la barra de búsqueda y envía `POST /search` al buscar. Consulta el contrato detallado en `docs/API_FRONTEND.md` y la guía de entrega en `docs/ENTREGA_FRONTEND.md`.

> **Atención:** `127.0.0.1` apunta a **la máquina del navegador**, no a la máquina de otra persona. Si el frontend se ejecuta desde otro computador, necesita una API accesible mediante red local confiable o una URL pública; hospedar solo el frontend en Vercel no publica automáticamente este backend.

## Pruebas y reproducibilidad

```powershell
python -m pip check
python -m unittest discover -s tests -v
```

La última ejecución verificada tuvo **108 pruebas correctas**. Con la API iniciada y los recursos disponibles:

```powershell
python scripts/verificar_api.py
```

El script prueba disponibilidad, los cinco modelos, comparación, validaciones y CORS. La evaluación académica ya fue realizada en `validation` (500 consultas) y `test` (648 consultas). No se deben modificar los parámetros congelados basándose en `test`.

Las métricas se guardan en `results/` como JSON/CSV; los rankings `.trec` se regeneran localmente y están excluidos de Git. Los archivos de datos y los índices también están excluidos.

## Despliegue: situación actual

Configuración de Vercel, capacidad del backend y verificación de despliegues:
[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).

**Aplicación pública:** [FiQA](https://fiqa-indol.vercel.app).
**API completa:** [fiqa-api.vercel.app/docs](https://fiqa-api.vercel.app/docs).

El frontend estático y FastAPI se alojan en dos proyectos Vercel independientes.
La API utiliza Python 3.12, PyTorch CPU y Large Functions, con corpus, Snowball,
FAISS y pesos BGE completos verificados durante el build. Los cuatro modelos activos,
la comparación y el frontend público pasaron pruebas reales sin autenticación.
El Preview midió aproximadamente 1,26 GB de RAM, dentro de los 2 GB de Hobby.
No se activaron recursos de pago; se aplican las cuotas y límites del plan.

## Colaboración y mantenimiento

- No versionar `.env`, `.venv`, `data/raw`, `data/processed`, pesos ni índices en el historial Git. El despliegue descarga el paquete inmutable de la Release y los pesos BGE por sus hashes.
- Registrar los cambios de modelos y API en ramas o *pull requests* para no romper el contrato del frontend.
- Mantener las rutas y campos de `/search` estables; comunicar cualquier cambio al frontend.
- Los documentos provienen de FiQA: el buscador **recupera textos existentes**, no genera respuestas nuevas ni garantiza corrección financiera.
