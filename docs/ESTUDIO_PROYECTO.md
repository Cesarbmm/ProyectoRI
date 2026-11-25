# ESTUDIO DEL PROYECTO FIQA — Arquitectura, código y defensa técnica

**Proyecto:** [Cesarbmm/ProyectoRI](https://github.com/Cesarbmm/ProyectoRI) · **Versión analizada:** `1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23` (rama `main`, 24/11/2026).  
**Aplicación:** <https://fiqa-indol.vercel.app/> · **API:** <https://fiqa-api.vercel.app/> · **Swagger:** <https://fiqa-api.vercel.app/docs>.  
**Propósito de este documento:** comprender la implementación existente, defender decisiones técnicas y localizar exactamente qué tocaría cambiar **sin modificar el programa entregado**.

> **Alcance de la revisión.** Se inspeccionaron los archivos fuente y la documentación del repositorio mediante GitHub, el manifiesto de despliegue y los resultados versionados. Las cifras son las *reportadas y verificadas en el repositorio*; no se ejecutó de nuevo la batería de pruebas ni se reconstruyeron los índices en esta sesión. Los cambios hipotéticos que se muestran NO se han aplicado. Enlaces permanentes a los archivos: `https://github.com/Cesarbmm/ProyectoRI/blob/1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23/RUTA`.

---

## 1. Lo más importante que debes saber antes de exponer

**FiQA es un motor de recuperación de información, no un chatbot generativo.** El usuario escribe una consulta financiera, selecciona un modelo, y el sistema recupera **documentos ya existentes** del corpus FiQA. No genera una explicación mediante un LLM, no tiene un prompt de sistema generativo y no almacena una base de datos conversacional. En sentido estricto **no hay un pipeline RAG completo**: está implementado el componente *retrieval* que podría alimentar un RAG futuro; el componente *generation* no existe. El prefijo en inglés de BGE es una **instrucción del encoder de consultas**, no un prompt para generar respuestas.

**Cuatro modelos visibles:** Jaccard, TF-IDF con coseno, BM25 y BGE + FAISS. El híbrido BM25+BGE permanece en código, API, métricas históricas y pruebas, pero **no está disponible en el selector del frontend**.

**Corpus de FiQA/BEIR:** 57.638 documentos, 6.648 consultas; **38 documentos con texto vacío** conservan su ID en el corpus e índice léxico, pero no generan embedding, por lo que FAISS contiene **57.600 vectores de 768 dimensiones**. Los títulos están vacíos. Los parámetros se seleccionaron en **500 consultas de `validation`** y se evaluaron al final con **648 de `test`**, manteniendo los qrels binarios.

**Configuración final:** Snowball inglés para los tres métodos léxicos; BM25 `k1=0.8`, `b=0.75`; BGE `BAAI/bge-base-en-v1.5`; índice vectorial exacto `faiss.IndexFlatIP`; consulta de BGE con su prefijo específico, embeddings L2-normalizados.

### Resultados finales (FiQA test, 648 consultas, profundidad 1.000)

| Modelo | MAP@1000 | P@10 | Recall@100 | MRR@10 | NDCG@10 |
|---|---:|---:|---:|---:|---:|
| Jaccard | 0.038587 | 0.015741 | 0.202817 | 0.068289 | 0.048740 |
| TF-IDF | 0.141153 | 0.053241 | 0.491186 | 0.216036 | 0.173773 |
| BM25 | 0.210294 | 0.069599 | 0.545683 | 0.315262 | 0.254969 |
| **BGE + FAISS** | **0.347148** | **0.112346** | **0.741472** | **0.485444** | **0.406231** |

Resultado auxiliar histórico: híbrido Snowball MAP@1000 = `0.349604`, mejora absoluta de `0.002456` respecto de BGE, sin evidencia concluyente de significación estadística. **No presentarlo como quinto modelo obligatorio.** La precisión medida depende de los juicios anotados (qrels incompletos), no representa la satisfacción real de cualquier usuario.

---

## 2. Arquitectura completa: dos momentos diferentes

### 2.1 Preparación e indexación *offline* — antes de buscar

```text
Hugging Face Datasets: BeIR/fiqa + BeIR/fiqa-qrels
          |
          v
scripts/preparar_datos.py --> data/raw/corpus, queries, qrels
          |
          +--- scripts/auditar_corpus.py --> results/auditoria_fiqa.json
          |
          +--- RUTA LÉXICA: TextPreprocessor (Snowball, stopwords protegidas)
          |          |
          |          v
          |     InvertedIndex.build() --> data/processed/inverted_index_stemming.json.gz
          |                       (postings, tf, df, longitudes, vocabulario)
          |
          +--- RUTA SEMÁNTICA: SentenceTransformer BGE (Hugging Face Hub)
                     |
                     v
                encode_document() --> embeddings L2, float32, 768 D
                     |
                     v
                FAISS IndexFlatIP.add() --> semantic_bge/index.faiss
                                          semantic_bge/doc_ids.json
                                          semantic_bge/metadata.json

Estos artefactos se construyen UNA VEZ y se reutilizan en producción.
```

**Qué se guarda, y dónde:** `data/raw/corpus/` contiene los textos con ID; `data/raw/queries/` y `data/raw/qrels/` se usan para experimentación/evaluación; `data/processed/inverted_index_stemming.json.gz` conserva el índice invertido; `data/processed/semantic_bge/` guarda el índice FAISS, los IDs y metadatos; las estadísticas y rankings de evaluación están en `results/`. El repositorio **no** versiona los corpus, índices grandes ni pesos del modelo; un `git clone` no basta para buscar.

### 2.2 Consulta *online* — cuando el usuario pulsa Buscar

```text
Usuario
  | texto, modelo seleccionado, top_k
  v
Frontend React/Vite (formulario + selector + comparación)
  | HTTP POST /search {query, model, top_k}
  v
FastAPI: SearchRequest valida datos --> get_search_service()
  |                                     instancia y cachés en memoria
  v
SearchService.search(query, model, top_k)
  |
  +--- SI modelo = jaccard | tfidf | bm25
  |       |
  |       +--> CARGA del mismo índice invertido y su TextPreprocessor
  |       +--> PROCESAMIENTO DE CONSULTA: normalize, tokenize, stopwords, Snowball
  |       +--> MODELO ELEGIDO: Jaccard / TF-IDF / BM25
  |       +--> score + orden de IDs (ranking propio)
  |
  +--- SI modelo = bge
          |
          +--> CARGA diferida del encoder BGE y del FAISS existente
          +--> encode_query(query, prefijo BGE)
          +--> vector float32 L2-normalizado
          +--> IndexFlatIP.search(vector, top_k)
          +--> puntuación y ranking de IDs de documentos
  |
  v
SearchService._get_document_texts(): resuelve IDs en corpus FiQA
  |
  v
SearchHit(rank, doc_id, score, text, preview) por documento
  |
  v
FastAPI execute(): SearchResponse JSON (+ elapsed_ms)
  |
  v
Frontend: valida JSON con Zod y muestra documentos ordenados
  |
  v
Usuario lee textos originales, no una respuesta generada.
```

**Corrección conceptual esencial para dibujar el sistema:** el usuario **elige el modelo en la interfaz antes de enviar la petición**. En el backend, FastAPI recibe **juntos** `query`, `model` y `top_k`, y `SearchService` enruta según `model`; no existe un microservicio selector independiente ni un único preprocesamiento obligatorio aplicado a todos los modelos. **Jaccard, TF-IDF y BM25 comparten el mismo `TextPreprocessor` y el mismo `InvertedIndex`**, pero BGE tokeniza internamente con su propio tokenizer neuronal; aplicarle Snowball como a los modelos léxicos sería cambiar el experimento.

### 2.3 ¿Ranking, comparación, fusión y generación son lo mismo?

- **Ranking:** cada recuperador calcula su `score` y devuelve una lista **ordenada por su propio criterio**. En Jaccard la puntuación es una razón de conjuntos; TF-IDF usa coseno; BM25 usa pesos probabilísticos; BGE usa similitud coseno vectorial. **Las escalas de puntuación no se comparan directamente.**
- **Comparación:** `POST /search/compare` ejecuta la **misma consulta en varios modelos por separado** y devuelve `rankings` distintos. **Comparar no significa fusionar.**
- **Fusión RRF:** `weighted_rrf` combinaría posiciones de BM25 y BGE para producir *un nuevo ranking*; quedó como experimento complementario oculto en la web, pero se mantiene accesible desde el backend/API histórica.
- **Generación de respuesta:** **no existe** una fase que formule un texto nuevo a partir de los resultados. El JSON solo reúne documentos y metadatos, no es la salida de un generador.

### 2.4 Servicios reales: no inventar microservicios

| Elemento | Implementación real | Responsabilidad |
|---|---|---|
| Web pública | Proyecto Vercel `fiqa`, carpeta `frontend/` | Sirve React/Vite/TypeScript estático |
| Backend público | Proyecto Vercel `fiqa-api`, carpeta `backend/` | Ejecuta FastAPI como Vercel Function con PyTorch CPU |
| Servicio interno | Clase Python `SearchService` | Gestiona recuperadores, sus cachés y el corpus |
| Servicio Hugging Face | Datasets y Hub **en preparación/build** | Provee dataset y pesos BGE; **no** es un servicio HTTP consultado por cada usuario |
| Índice vectorial | FAISS embebido en el proceso Python | Busca vectores: **no** es una base de datos autónoma o microservicio separado |
| Índice léxico | `InvertedIndex` Python cargado de JSON.gz | Accede a postings y frecuencias |
| API Gateway dedicado | **No existe** | El frontend llama directamente a FastAPI por HTTPS; Vercel enruta la solicitud a la Function |
| Base SQL/NoSQL | **No existe en la recuperación actual** | Se utilizan archivos persistidos y diccionarios en memoria |
| Caché | Atributos de `SearchService` y carga diferida | Viven por proceso/instancia; no hay Redis |

---

## 3. Mapa del backend: archivo por archivo

**Cómo estudiar:** cada ficha especifica ruta, propósito y problema que resuelve, funciones relevantes (entrada → salida; momento de ejecución), dependencias y efecto de cambiar/eliminar el archivo. `None` significa función sin retorno de negocio, normalmente con efectos de guardar archivos.

### 3.1 `src/ri_fiqa/config.py` — parámetros congelados

**Problema:** evitar que cada parte del proyecto use un índice, stemming o parámetros BM25 distintos. **Dependencias:** `PreprocessConfig`; el servicio, scripts y runtime leen `SELECTED_CONFIG`.

| Símbolo | Entrada → salida; cuándo se ejecuta |
|---|---|
| `RetrievalConfig` | Dataclass con `morphology`, `bm25_k1`, `bm25_b`, `semantic_index`, `rrf_k`, `rrf_semantic_weight`, `candidate_depth`. Instanciación al importar/configurar. |
| `RetrievalConfig.__post_init__()` | Campos del objeto → valida morfología con `PreprocessConfig`; al crear config. |
| `RetrievalConfig.lexical_index` | `morphology` → nombre del `.json.gz`; al cargar el índice. |
| `SELECTED_CONFIG` | Constante final: `RetrievalConfig(morphology="stemming", bm25_k1=0.8, bm25_b=0.75)`. |

**Si se elimina:** fallan imports y la selección compartida. **Si se cambia:** puede cargar otro índice o cambiar rankings, por lo que se debe reconstruir/evaluar y sincronizar manifiesto y despliegue; no basta con editar un número.

### 3.2 `src/ri_fiqa/preprocessing.py` — preparación léxica común

**Problema:** reducir variaciones superficiales de texto y usar exactamente las mismas reglas en consultas e indexación. **Dependencias:** `re`, `unicodedata`, stopwords de `scikit-learn`, NLTK Snowball/WordNet cuando proceda.

| Símbolo | Entrada → salida; momento e interacción |
|---|---|
| `PROTECTED_TERMS` | Conjunto de palabras financieras y negaciones que se preservan: `not`, `interest`, etc.; constante leída por el proceso. |
| `STOPWORDS` | Stopwords en inglés menos términos protegidos; se utiliza al tokenizar. |
| `TOKEN_PATTERN` | Expresión regular para tokens, números, decimales y porcentajes. |
| `PreprocessConfig(remove_stopwords, morphology)` | Parámetros → objeto validado, cada vez que se define un índice/experimento. |
| `TextPreprocessor.__init__(config)` | Config → instancia, construye transformación Snowball/WordNet con caché LRU si corresponde. |
| `TextPreprocessor.normalize(text)` | Texto/`None` → `str` normalizada (NFKD, minúsculas, negaciones, `401(k)`→`401k`); al indexar o consultar. |
| `TextPreprocessor.process(text)` | Texto/`None` → `list[str]` de tokens filtrados/transformados; lo usa el índice y cada recuperador léxico. |

**Si se elimina:** ni índice ni recuperadores léxicos pueden procesar. **Si se modifica:** documento y consulta deben pasar por las **mismas reglas**; reindexar y repetir test de regresión. Snowball puede confluir palabras diferentes (ej. `apy`→`api`): es una limitación real.

### 3.3 `src/ri_fiqa/indexing.py` — índice invertido propio

**Problema:** localizar documentos por términos sin recorrer todos los textos en cada consulta. **Dependencias:** `TextPreprocessor`, `Counter`, `gzip`, `json`. Mantiene `postings: término → {doc_id: tf}`, `doc_lengths`, `doc_unique_terms`, `total_tokens`, `total_postings`.

| Función | Entrada → salida; cuándo |
|---|---|
| `InvertedIndex.__init__(preprocessor)` | Preprocesador opcional → estado vacío; al construir/cargar índice. |
| `add_document(doc_id, text)` | ID + texto → modifica postings/TF/longitudes, sin retorno; durante indexación offline. Conserva ID aun si texto vacío. |
| `build(documents)` | Iterable de objetos con `_id`, `text` → índice completo, sin retorno; offline. |
| `get_postings(term)` | Término → mapa de documentos y TF; en búsquedas de los tres léxicos. |
| `document_frequency(term)` | Término → `df` entero; cálculo de IDF. |
| `term_frequency(term, doc_id)` | Término e ID → `tf` entero. |
| `num_documents`, `vocabulary_size`, `average_document_length` | Estado → estadísticas de índice; TF-IDF/BM25 y defensa. |
| `save(file_path)` | Ruta → JSON comprimido en disco (escritura temporal y reemplazo); offline. |
| `InvertedIndex.load(file_path)` | Ruta del índice → instancia con configuración guardada; online. |

**Si se elimina:** Jaccard, TF-IDF y BM25 dejan de funcionar. **Si cambian estructuras persistidas:** actualizar versión de formato y reconstruir; leer índices anteriores puede fallar.

### 3.4 `src/ri_fiqa/retrieval/common.py` — tipo compartido

**Problema:** unificar la salida de todos los recuperadores. `SearchResult(doc_id: str, score: float)` es una dataclass inmutable, sin lógica de ejecución. **Se construye** al puntuar y ordenar en cada modelo. **Eliminarlo:** rompe imports de todos los retrievers y de `SearchService`.

### 3.5 `src/ri_fiqa/retrieval/jaccard.py` — referencia binaria

**Problema:** medir solapamiento lexical sin pesos. `JaccardRetriever.__init__(index)` recibe `InvertedIndex` y guarda referencia; `search(query: str, top_k: int) -> list[SearchResult]` se ejecuta al escoger `jaccard`: aplica `index.preprocessor.process`, convierte tokens a conjuntos, accede a postings, cuenta intersecciones, calcula `|Q∩D|/|Q∪D|`, ordena y recorta. **Eliminarlo:** desaparece el modelo de referencia. **Cambiar el denominador o desempate:** modifica MAP y el ranking de defensa.

### 3.6 `src/ri_fiqa/retrieval/tfidf.py` — pesos dispersos/coseno

**Problema:** los términos frecuentes/raros no deben contribuir como una mera coincidencia binaria. **Dependencias:** `InvertedIndex`, `Counter`, `defaultdict`, logaritmo/raíz.

| Función | Entrada → salida; cuándo |
|---|---|
| `TfidfRetriever.__init__(index)` | Índice → instancia; llama a `_prepare` una vez en primera carga. |
| `_prepare()` | Postings/DF/TF → `self.idf` y normas documentales L2 precalculadas; en la creación del retriever, **no** por consulta. |
| `search(query, top_k)` | Texto + K → ranking `list[SearchResult]`; procesa consulta, calcula TF-IDF y similitud coseno únicamente sobre candidatos de postings. |

**IDF exacta:** `log((N + 1) / (df + 1)) + 1`. `+1` dentro de cociente evita divisiones problemáticas y el término `+1` exterior mantiene un peso mínimo incluso si `df=N`. **Eliminarlo:** desaparece TF-IDF. **Modificar suavizado o normalización:** afecta scores, rankings y métricas; recalcular normas.

### 3.7 `src/ri_fiqa/retrieval/bm25.py` — recuperación probabilística

**Problema:** considerar saturación de frecuencia y tamaño de documento. **Dependencias:** `InvertedIndex` y configuración elegida.

| Símbolo | Entrada → salida; cuándo |
|---|---|
| `BM25Config(k1, b)` / `__post_init__()` | Hiperparámetros → objeto validado (`k1 > 0`, `0 ≤ b ≤ 1`); al crear retriever. |
| `BM25Retriever.__init__(index, config)` | Índice + parámetros → precalcula IDF positiva con `log1p((N-df+0.5)/(df+0.5))` y longitud media. |
| `BM25Retriever.search(query, top_k)` | Consulta + K → ranking; usa términos **distintos**, postings TF, saturación `k1` y ajuste de longitud `b`. |

**Eliminarlo:** se pierde BM25 y se rompe la rama híbrida histórica. **Modificar `k1` o `b`:** requiere repetir validación; no ajustar desde test. La configuración final fija es `0.8/0.75`, seleccionada después de Snowball.

### 3.8 `src/ri_fiqa/embedding_models.py` — perfiles de encoders

**Problema:** centralizar la identidad de los modelos y sus instrucciones de entrada. No construye por sí solo FAISS.

| Símbolo | Entrada → salida; cuándo |
|---|---|
| `EmbeddingProfile` | `model_id`, `query_prompt`, `document_prompt` → objeto de perfil inmutable. |
| `MODEL_SPECS['minilm']` | `sentence-transformers/all-MiniLM-L6-v2`, sin prompts; candidato evaluado (384 D). |
| `MODEL_SPECS['bge']` | `BAAI/bge-base-en-v1.5`, prefijo de consulta; ganador (768 D). |
| `MODEL_SPECS['e5']` | `intfloat/e5-base-v2`, prefijos `query: ` y `passage: `; **configurado pero sin evaluación comparable final**. |
| `PromptedEncoder.__init__(model, query_prompt, document_prompt)` | Modelo más instrucciones → adaptador de codificación. |
| `PromptedEncoder.encode_query(texts, **kwargs)` | Lista de consultas → embeddings aplicando prompt de consulta. |
| `PromptedEncoder.encode_document(texts, **kwargs)` | Lista de documentos → embeddings con prompt documental configurado. |
| `configure_encoder(model, query_prompt, document_prompt)` | Modelo y prompts → encoder original o adaptador `PromptedEncoder`; al preparar/cargar modelo. |

**Eliminarlo:** falla construcción semántica y verificación de metadatos. **Cambiar BGE por MiniLM:** no basta alterar `MODEL_SPECS`; debe reconstruirse el índice con dimensión compatible, actualizar `semantic_index`, manifests y volver a medir.

### 3.9 `src/ri_fiqa/retrieval/semantic.py` — búsqueda BGE/FAISS

| Función | Entrada → salida; cuándo |
|---|---|
| `SemanticRetriever.__init__(encoder, vector_index, doc_ids)` | Encoder, índice FAISS e IDs → retriever; valida correspondencia `ntotal == len(doc_ids)` y unicidad. |
| `search_many(queries, top_k=10, batch_size=32)` | Lista de consultas → lista de rankings; `encoder.encode_query`, conversión float32, normalización L2, `index.search(vectors, k)` y mapeo posición→ID. |
| `search(query, top_k=10)` | Texto → ranking individual delegando a `search_many([query], ...)`. |

**Problema:** separar la transformación semántica del algoritmo de vecinos. **Eliminarlo:** BGE deja de recuperar. **Cambiar orden/normalización:** puede romper equivalencia coseno/IP y comparabilidad con qrels; requiere tests.

### 3.10 `src/ri_fiqa/retrieval/fusion.py` — **extensión híbrida histórica**

`weighted_rrf(bm25_ids: list[str], semantic_ids: list[str], *, k: int=60, semantic_weight: float=0.75, top_k: int=1000) -> list[SearchResult]`: combina posiciones de dos rankings, no scores brutos, y devuelve una lista ordenada. La **configuración real** la suministra `SELECTED_CONFIG` (`k=10`, peso BGE `0.9`), por eso NO son los defaults de la función. Se ejecuta si se selecciona `hybrid` desde el servicio/API o en scripts históricos, **no desde la web pública**. **Eliminar sin cambiar referencias rompe `SearchService`, importaciones, test de fusión y contratos API.**

### 3.11 `src/ri_fiqa/search_service.py` — orquestador de búsquedas

**Problema:** exponer una API Python única y evitar cargar índices, texto y pesos en cada consulta. **Dependencias:** `datasets.load_from_disk`, índices, cuatro retrievers, RRF histórica y config.

| Función | Entrada → salida; cuándo |
|---|---|
| `SearchHit` | `rank, doc_id, score, text, preview`; representación final con texto. |
| `SearchService.__init__(project_root=None, *, inverted_index=None, semantic_retriever=None, document_texts=None, device='auto', config=SELECTED_CONFIG)` | Inyección opcional de recursos/config → instancia con cachés vacíos o inyectados; al primer uso de la API o en scripts. |
| `_get_index()` | Sin entrada → carga/cacha `InvertedIndex` desde JSON.gz; valida que morfología del índice coincida con la seleccionada. |
| `_get_lexical(model)` | `jaccard/tfidf/bm25` → objeto recuperador almacenado en `_lexical_models`; carga diferida. |
| `_get_semantic()` | Sin entrada → lee `metadata.json`, `doc_ids.json`, `index.faiss`, comprueba integridad, carga `SentenceTransformer(metadata['model_id'])` y adaptador de prompts; **caché por instancia**. |
| `_get_document_texts()` | Sin entrada → diccionario `{doc_id: text}` cargado del corpus; se usa para enriquecer el ranking. |
| `search(query, model='bge', top_k=5)` | Consulta/modelo/K → `list[SearchHit]`; ruta léxica, semántica o híbrida; resuelve IDs a texto, crea preview de 280 caracteres, ordena por score entregado. |
| `rank_many(queries, model='bge', top_k=1000, batch_size=32)` | Varias consultas → rankings sin texto; en híbrido obtiene BM25 y BGE a profundidad 1000 y llama a `weighted_rrf`. Se usa en evaluación y rama experimental. |

**Eliminarlo:** desaparece el punto central del backend y la API no funcionaría. **Modificar la caché:** aumenta tiempo/costo de memoria y puede afectar concurrencia. **Modificar `MODELS`:** también obliga a revisar esquemas FastAPI, front, pruebas y scripts; no es solo una lista visual.

### 3.12 `src/ri_fiqa/runtime.py` — comprobación de recursos

`inspect_assets(project_root, semantic_index=SELECTED_CONFIG.semantic_index, config=SELECTED_CONFIG) -> dict`: comprueba **sin cargar PyTorch** la existencia de corpus, índice léxico y archivos FAISS, sus metadatos (BGE, 768 D, `IndexFlatIP`, L2 y recuentos). Lo usa `/ready` y el build/despliegue. **Eliminarlo:** la API dejaría de diferenciar servidor vivo de motor realmente preparado. **Modificar FAISS/modelo:** habrá que actualizar expresamente estos chequeos; de lo contrario `/ready` informará inconsistencia aunque los archivos existan.

### 3.13 `src/ri_fiqa/api.py` — API REST FastAPI

**Problema:** traducir HTTP/JSON a operaciones Python y validar entradas de usuarios. **Dependencias:** FastAPI, Pydantic, `SearchService`, `inspect_assets`.

| Símbolo/función | Entrada → salida; momento |
|---|---|
| `ModelName` | Literal que admite cinco identificadores, incluido `hybrid` histórico. |
| `SearchRequest` | JSON `{query, model='bge', top_k=5}` → objeto validado; `query` 1–500, `top_k` 1–20, sin campos extra. |
| `CompareRequest` + `require_distinct_models` | JSON con `models` de 2–5 sin duplicados → entrada validada. |
| `SearchHitOut`, `SearchResponse`, `ComparisonResponse`, `ModelsResponse` | Esquemas de JSON de salida. |
| `get_project_root()` | Lee `RI_PROJECT_ROOT` opcional → ruta absoluta; al localizar recursos. |
| `get_search_service()` | Sin argumento HTTP → única instancia caché por proceso; protegida por `_service_lock`. |
| `get_readiness()` | Sin argumento → dict de `inspect_assets`; dependencia del `/ready`. |
| `execute(service, query, model, top_k)` | Servicio + consulta → `SearchResponse` con `elapsed_ms` y resultados; traduce fallos de recursos en HTTP 503. |
| `health()` | `GET /health` → JSON de salud de proceso; **no** valida índices. |
| `ready()` | `GET /ready` → estado recursos, 200 o 503. |
| `models()` | `GET /models` → catálogo con cinco identificadores en API y config final; el frontend filtra a cuatro. |
| `search(body, service)` | `POST /search` → ejecuta bajo `_inference_lock` y devuelve un ranking. |
| `compare(body, service)` | `POST /search/compare` → **varios rankings independientes**, no RRF; también usa `_inference_lock`. |

**Eliminarlo:** no existe web API. **Modificar esquemas:** rompe clientes Zod y scripts de verificación, incluso si las puntuaciones no cambian. Un `422` indica petición inválida; `503`, recursos no disponibles. CORS restringe orígenes y permite GET/POST, sin credenciales de navegador.

### 3.14 `src/ri_fiqa/evaluation.py` — métricas y TREC

**Problema:** medir calidad de rankings frente a qrels, sin confundir puntuación interna con relevancia.

| Función | Entrada → salida |
|---|---|
| `precision_at_k(ranked_ids, relevant_ids, k)` | Ranking + set de relevantes + K → fracción relevantes en K. |
| `recall_at_k(...)` | Igual → fracción de todos los relevantes conocidos recuperada en K. |
| `average_precision_at_k(...)` | Igual → promedio de precisiones en posiciones relevantes, dividido por **todos los relevantes**. |
| `reciprocal_rank_at_k(...)` | Igual → 1/posición del primer relevante o cero. |
| `ndcg_at_k(...)` | Igual → ganancia descontada normalizada (relevancia binaria). |
| `evaluate_query(ranked_ids, relevant_ids, depth=1000)` | Ranking de una consulta → diccionario de AP/P/R/RR/NDCG; comprueba IDs duplicados y profundidad. |
| `aggregate_metrics(per_query)` | Dict de métricas por consulta → MAP, P@k, Recall, MRR, NDCG medios. |
| `write_trec_ranking(file, query_id, results, run_name)` | Handle y ranking → líneas formato TREC para evaluación externa; **usa score ordinal para evitar empates**, no el score original. |

**Cuándo:** durante los scripts *offline* de evaluación, no en cada búsqueda web. **Eliminarlo:** se pierde evaluación y comparabilidad académica, no necesariamente la búsqueda del usuario.

### 3.15 `src/ri_fiqa/statistics.py` y `src/ri_fiqa/preprocessing_experiment.py`

`statistics.paired_comparison(baseline_scores, candidate_scores, repetitions=10000, seed=20261115) -> dict`: valida series pareadas, calcula diferencia media, IC95% bootstrap por consulta y p bilateral de permutación. **Offline**; no cambia rankings online.  
`preprocessing_experiment.holm_adjust(p_values) -> list[float]`: corrige comparaciones múltiples; `validate_reports(reports) -> list[str]`: exige 500 consultas iguales de *validation*; `select_configuration(reports) -> dict`: aplica criterios congelados para escoger morfología. Tiene constantes `VARIANTS`, `MODELS=('jaccard','tfidf','bm25','hybrid')`, `K1_GRID`, `B_GRID`, `PROTOCOL`. **No borrar esta evidencia histórica a ciegas:** el híbrido formó parte de la regla formal que justificó Snowball. Cambiar la regla produciría otro experimento.

### 3.16 `src/ri_fiqa/__init__.py` y `src/ri_fiqa/retrieval/__init__.py`

Delimitan paquetes Python importables. No contienen el algoritmo principal. Eliminarlos puede alterar resolución/importación según empaquetado/entorno; no se recomienda borrarlos por «parecer vacíos».

---
## 4. Scripts de preparación, diagnóstico, evaluación y despliegue

Estos archivos se ejecutan por CLI; **no todos forman parte del trayecto de una búsqueda online**. Su existencia sirve para reproducir experimentos y demostrar el desarrollo.

| Archivo (ruta relativa a raíz) | Qué hace; funciones importantes; qué recibe/devuelve | Consecuencia de eliminar o modificar |
|---|---|---|
| `scripts/preparar_datos.py` | `cargar_o_descargar(nombre, repositorio, config=None, split=None)` descarga/reutiliza datasets y los guarda en disco; `main()` prepara corpus, queries y qrels, comprueba integridad referencial e imprime ejemplos. | Sin él no se pueden recrear fácilmente los datos originales desde Hugging Face. No interviene por solicitud HTTP. |
| `scripts/auditar_corpus.py` | `estadisticas(valores)`, `auditar_textos(dataset)`, `auditar_qrels(dataset)`, `main()`: recuentos, textos vacíos/duplicados, longitudes, pares relevantes; guarda `results/auditoria_fiqa.json`. | No se pierde búsqueda si se borra; sí diagnóstico y evidencia verificable. |
| `scripts/construir_indice.py` | `construir_indice(morphology, output_path)` → `InvertedIndex`; `mostrar_estadisticas(index)` y `inspeccionar_termino(index, texto)` imprimen información; `main()` CLI con `--rebuild`, `--term`, `--morphology`. | Necesario para recrear índice léxico; sin recurso ya construido, los tres modelos léxicos fallan. |
| `scripts/construir_indice_semantico.py` | `main()` recibe `--encoder`, `--name`, `--batch-size`, `--limit`, `--device`, `--force`; lee corpus, codifica documentos, crea `IndexFlatIP`, guarda FAISS, IDs y `metadata.json`. | Es el **punto exacto para experimentar con tipos FAISS**. Cualquier cambio requiere regenerar los artefactos, no basta actualizar la API. |
| `scripts/buscar.py` | `mostrar_resultados(hits, json_output=False)` y `main()` → consultas en terminal usando `SearchService`; `--model`, `--query`, `--top`, `--device`, `--interactive`, `--json`. | Muy útil para defensa sin navegador. Eliminar no afecta API, pero reduce observabilidad local. |
| `scripts/buscar_jaccard.py` | `main()` busca directamente con Jaccard en índice invertido e imprime IDs/score. | Duplicación funcional respecto a `buscar.py`, pero útil como herramienta didáctica; no declararlo muerto solo por similitud. |
| `scripts/evaluar_jaccard.py` | `main()` lee qrels/consultas y Jaccard, calcula métricas y exporta TREC y ejemplos con bajo AP. | Histórico; perderíamos la evaluación individual reproducible. |
| `scripts/evaluar_modelos.py` | `main()` evalúa léxicos, con `--model`, `--depth`, `--k1`, `--b`; guarda métricas y rankings. | Función académica y de prueba de parámetros, fuera del backend en producción. |
| `scripts/evaluar_semantico.py` | `main()` evalúa FAISS/encoder cargado por `--name`, con `--depth`, `--batch-size`, `--device`, `--query-prompt-mode saved|none`. | Permite comparar MiniLM/BGE y la ablación de instrucción. No genera un índice nuevo. |
| `scripts/evaluar_hibrido.py` | `read_run(path)`, `read_qrels(path)`, `main()`: fusiona rankings TREC preexistentes y calcula métricas RRF. | **Experimento candidato a archivar**, pero su eliminación elimina un mecanismo de reproducción histórica. No está enlazado a la web. |
| `scripts/evaluar_final.py` | `load_evaluation_data(split)`, `verify_baseline(model, per_query)`, `main()`; flags `--model`, `--split validation|test`, `--device`, `--batch-size`, `--verify-baseline`, `--frozen`. | Es el evaluador integrado final. La opción `hybrid` aún funciona si el servicio la expone; no alterar métricas congeladas. |
| `scripts/experimentar_preprocesamiento.py` | `sha256`, `dump`, `load`, `relative`, `semantic_hashes`, `source_hashes`, `split_data`, `score_rankings`, `semantic_rankings`, `evaluate`, `hybrid_report`, `comparison_table`, `validation`, `final_check`, `main`. Corre protocolo `validation` o `final` con varias morfologías y contempla RRF. | **No es enteramente híbrido:** sostiene el experimento morfológico que justifica Snowball. Borrar o mutilar sin reemplazo destruye trazabilidad del informe. |
| `scripts/probar_preprocesamiento.py` | Prueba rápida de normalización/tokens en ejemplos financieros (ejecutable de exploración). | No es dependencia de producción; puede mantenerse para defensa. |
| `scripts/verificar_experimento_preprocesamiento.py` | `verify(output, include_final=False)` y `main()` validan artefactos del experimento. | Protege consistencia de los resultados; no borrar junto con los archivos que verifica sin replantear protocolo. |
| `scripts/verificar_api.py` | `main()` con `--url` comprueba endpoints, modelos y contratos localmente. | Herramienta de smoke test local; referencias al híbrido deben revisarse si se cambia API. |
| `scripts/package_runtime_assets.py` | `package_assets(root, output)` → manifiesto y paquete de corpus/índices para despliegue. | Puede ser necesario para reconstruir una Release. **No eliminar** como «script antiguo». |
| `scripts/regenerar_cache_bge.py` | `regenerate(split, selection=None)` y `main()` producen/actualizan rankings de BGE para validación/test con el modelo fijado. | Necesario para algunos experimentos reproducibles; ejecución intensiva. |
| `scripts/analizar_errores.py` | `read_metrics(model)`, `read_ranking(model)`, `clean(text, limit=240)`, `main()`; compara casos por consulta, puede referirse a híbrido. | Análisis cualitativo; no afecta servicio web, sí defensa. |
| `scripts/comparar_estadisticamente.py` | `load_report(filename)`, `main()` → prueba pareada entre métricas de dos corridas usando `statistics.paired_comparison`. | Proporciona evidencia estadística sin tocar los rankings productivos. |
| `scripts/diagnosticar_metricas.py` | Script de diagnóstico de definiciones/implementación de métricas. | Mantener si se desea poder verificar evaluación histórica. |
| `scripts/resumir_bm25.py` | Consolidación de rejilla BM25 a partir de ficheros de evaluación. | Histórico; no depende el backend de este resumen. |
| `scripts/resumir_resultados_finales.py` | `read_report(model, split)` y `main()` → compila una tabla de métricas comparables. | Soporte de informe y revisión, no recuperador online. |
| `backend/verify_api.py` | `verify(base, cli=None, scope=..., diagnostics=True)`: prueba API desplegada, respuesta de búsqueda real y recursos. CLI con `--no-diagnostics` para producción. | Es el **verificador de despliegue público**. Actualmente verifica también el híbrido por compatibilidad de API. |

### Distinción: script de investigación vs componente de producción

`api.py`, `search_service.py`, `preprocessing.py`, `indexing.py`, los cuatro `retrieval/*.py`, `embedding_models.py`, `runtime.py` y los recursos del build son **críticos para búsquedas**. Scripts de `scripts/` y archivos de `results/` suelen ser preparación, diagnóstico y prueba; eso **no los convierte automáticamente en «código muerto»** porque algunos forman parte de la reproducibilidad, generación de paquetes, integridad o build del frontend.

---

## 5. Frontend y relación con la API

| Archivo | Propósito y comunicación | Si se modifica/elimina |
|---|---|---|
| `frontend/src/main.tsx` | Punto de entrada React; monta `<App/>`. | La UI no arranca. |
| `frontend/src/App.tsx` | Estado/vistas, integración de buscador, resultados, evaluación y acerca; usa hooks. | Cambia navegación y composición de interfaz. |
| `frontend/src/components/SearchForm.tsx` | Recoge query, modelo, top-K y comparación; manda eventos a hooks. | Puede cambiar lo que envía la API; mantener validación. |
| `frontend/src/components/ModelSelect.tsx` | Selector de los **cuatro** modelos disponibles en web. | Alterar el catálogo puede mostrar un modelo no previsto. |
| `frontend/src/components/Results.tsx` | Resultados ordenados, expansión de documento y visualización de IDs/textos. | Afecta lo que se ve, **no** el ranking del servidor. |
| `frontend/src/components/ResultScore.tsx` / `lib/scores.ts` | Presentación/etiquetado de puntuaciones; explica escalas. | No confundir redondeo visual con cambios de score real. |
| `frontend/src/components/Benchmark.tsx` | Vista de evaluación con métricas de test persistidas y comparación histórica. | No recalcula métricas por petición; se sincroniza con datos versionados. |
| `frontend/src/components/About.tsx` | Explicaciones de corpus, sistema y arquitectura. | Contenido informativo. |
| `frontend/src/lib/types.ts` | Tipos/Zod de API, `ACTIVE_MODEL_IDS`, `DEFAULT_MODEL`, `modelId` y `LABELS`. | Contrato de frontend: **híbrido permitido en schema histórico pero filtrado en selector**. |
| `frontend/src/lib/api.ts` | `createApi(base)` y `api`: `fetch`, timeout/cancelación, validación Zod, `health`, `ready`, `models`, `search`, `compare`. | Un cambio de URL o rutas rompe conexión; no toca métricas del motor. |
| `frontend/src/lib/useEngine.ts` | Gestiona salud, readiness, catálogo y estados de conexión. | Puede indicar conexión errónea si se confunde `/health` con `/ready`. |
| `frontend/src/lib/useSearch.ts` | Ejecuta/cancela consultas y comparaciones, mantiene estados de carga/error. | Afecta UI/experiencia, no cálculo de BGE/BM25. |
| `frontend/src/lib/benchmark.ts` + `src/data/benchmark.json` | Define métricas y carga datos **ya medidos** de experimentos. | Cambiar valores a mano falsea evidencia; usar `benchmark:sync` y `benchmark:check`. |
| `frontend/src/lib/useDockMotion.ts` | Movimiento/posicionamiento visual del buscador y scroll. | UX solamente. |
| `frontend/src/styles.css`, `refinement.css` | Paleta y diseño responsivo. | Sin impacto matemático en recuperación. |
| `frontend/vite.config.ts`, `tsconfig.json`, `frontend/vercel.json` | Compilación, TypeScript y despliegue frontend. | Un cambio puede romper build aunque los algoritmos sigan correctos. |

**Flujo HTTP exacto:** `api.models()` carga catálogo; `api.health()` indica que responde el proceso; `api.ready()` exige recursos completos; `api.search(query, model, top_k)` manda `POST /search`; `api.compare(query, models, top_k)` manda `POST /search/compare`. `frontend/src/lib/types.ts` comprueba `results[i].doc_id`, `rank`, `score`, `text`, `preview`, y recuento coherente. `VITE_API_URL` se **inyecta al compilar**; no se cambia en ejecución una vez generado `dist`.

**No mezclar:** el navegador **no descarga FAISS, los pesos BGE ni todo el corpus**. Recibe los textos del *top-K* solicitado a través de JSON. `elapsed_ms` proviene del backend y no equivale a latencia total de red o render.

---

## 6. Reconstrucción, ejecución local y producción

### 6.1 Requisitos reales

- Windows + PowerShell y VS Code; Python **3.11** para desarrollo del repositorio, Node.js compatible con la versión de Vite (documentación del frontend: Node 22.12+; configuración de build desplegada: Node 24), Git y conexión inicial.
- GPU/CUDA **opcional**: acelera creación de embeddings, pero los modelos también pueden funcionar en CPU. El despliegue utiliza PyTorch CPU de forma explícita.
- Datos FiQA, índice léxico con Snowball, FAISS BGE y pesos del encoder. **No se incluyen en Git normal.**
- Para instalar PyTorch con CUDA, consultar compatibilidad de versión/CUDA del equipo antes de fijar el índice de paquetes; el README documenta un entorno específico.

### 6.2 Copiar, preparar y ejecutar (PowerShell, dos terminales)

```powershell
# Terminal 1 — raíz del repositorio
 git clone https://github.com/Cesarbmm/ProyectoRI.git
 cd ProyectoRI
 py -3.11 -m venv .venv
 .\.venv\Scripts\Activate.ps1
 python -m pip install --upgrade pip
 python -m pip install -r requirements.txt
 python -m pip install -e .
 Copy-Item .env.example .env
```

**Preparación si NO tienes los artefactos** (requiere descarga, memoria y tiempo; no repetir durante la defensa si ya están preparados):

```powershell
python scripts/preparar_datos.py
python scripts/auditar_corpus.py
python scripts/construir_indice.py --rebuild --morphology stemming
python scripts/construir_indice_semantico.py --name semantic_bge --encoder bge --batch-size 16
```

El último comando usa como salida `data/processed/semantic_bge/`; **no agregar `--force` si no se desea sobrescribir un índice existente**. Para demostraciones es preferible reutilizar los artefactos originales. Las versiones exactas del entorno Windows/CUDA se documentan en `requirements-lock.txt`, pero no son una receta universal para CPU Linux.

```powershell
# Terminal 1 — API local (con .venv activo)
python -m uvicorn ri_fiqa.api:app --host 127.0.0.1 --port 8000 --reload --env-file .env

# Terminal 2 — frontend, desde la raíz del repositorio
cd frontend
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Abrir <http://127.0.0.1:5173>. Si no existe `frontend/.env.local`, usar `VITE_API_URL=http://127.0.0.1:8000`. **No usar `localhost` como URL del backend en un frontend público remoto.**

### 6.3 Variables y su dueño

| Variable | Dónde | Efecto |
|---|---|---|
| `RI_DEVICE=auto|cpu|cuda` | `.env` backend local | Selección de dispositivo para inferencia. |
| `RI_CORS_ORIGINS=...` | Backend | Lista de orígenes permitidos para el navegador; no es URL de consulta. |
| `RI_PROJECT_ROOT=...` | Backend opcional | Ruta que contiene `data/raw/` y `data/processed/`. |
| `VITE_API_URL=...` | `.env.local` frontend o Vercel build | URL pública de FastAPI consumida por React. Se incorpora al bundle. |
| `HF_TOKEN` | Opcional para acceso a Hub | No se necesita normalmente para modelos públicos; **nunca** subir secretos al repo. |
| `RI_CORS_ORIGIN_REGEX` | Backend en Vercel | Permite previews de origen restringido de esa cuenta. |
| `VERCEL_SUPPORT_LARGE_FUNCTIONS=1` | Vercel backend | Habilita empaquetado grande según configuración documentada. |
| `RI_RUNTIME_DIAGNOSTICS=1|0` | Vercel Preview/Production | Endpoints de diagnóstico solo Preview; desactivados en Production. |
| `RI_RUNTIME_DIR` | Adaptador backend opcional | Ruta alternativa de paquete de recursos en despliegue. |

### 6.4 Scripts de prueba y construcción (sin modificar fuente)

```powershell
# En raíz (con .venv)
python -m unittest discover -s tests -v
python scripts/verificar_api.py --url http://127.0.0.1:8000

# En frontend/
npm test
npm run benchmark:check
npm run build
npm run test:e2e
```

Para pruebas E2E con corpus y modelo reales, deben estar el backend y recursos completos disponibles. Las cifras históricas reportadas en el repo son **108 tests backend y 42 frontend**, además de Playwright, pero **no se certificó una nueva ejecución** al elaborar esta guía.

### 6.5 Comandos orientados a producción

El backend publicado NO se despliega con el mismo entorno `.venv` de Windows. Usa `backend/pyproject.toml`, `backend/uv.lock`, Python 3.12 y Torch CPU:

```bash
# En Linux, desde backend/ y con uv instalado
uv sync --frozen --no-dev
uv run --frozen python prepare_runtime.py
RI_RUNTIME_DIAGNOSTICS=1 uv run --frozen uvicorn main:app --port 8100
```

Para comprobar el **servidor ya publicado** (requiere red):

```powershell
python backend/verify_api.py https://fiqa-api.vercel.app --no-diagnostics --report build/public-api.json
```

`npm run build` produce un frontend estático en `frontend/dist/`; no es un servidor de recuperación. En Vercel el frontend se sirve por separado y la API recibe búsquedas reales. No se requiere administrar un servidor Linux permanente por cuenta propia.

---

## 7. Despliegue real: GitHub, Vercel y artefactos

```text
GitHub / rama main
   | fuente, docs, manifests y resultados de referencia
   +----------------------------+
   |                            |
   v                            v
Proyecto Vercel fiqa         Proyecto Vercel fiqa-api
Root frontend/               Root backend/
React/Vite (build)           Python 3.12 + FastAPI + CPU Torch
VITE_API_URL --------------> /search, /models, /ready...
                                |
                       prepare_runtime.py (BUILD)
                                |
                      descarga Release verificada
                      + pesos BGE verificados por hash
                                |
                       Function con recursos completos
```

**Archivos exactos:** `backend/main.py` adapta el `app` de `ri_fiqa.api` a Vercel, fuerza CPU y modo offline de Hugging Face en la ejecución, configura CORS/diagnóstico y añade comprobación de integridad. `backend/prepare_runtime.py` descarga la Release congelada, verifica SHA-256 de cada archivo, obtiene pesos BGE de una revisión fija y copia el paquete Python. `backend/assets-manifest.json` fija corpus, índice FAISS, dimensiones, hashes y revisión BGE; `backend/vercel.json` declara Function, build y límites; `backend/pyproject.toml` y `uv.lock` fijan dependencias Linux/CPU. `backend/verify_api.py` hace pruebas públicas y diagnósticos en Preview.

**Detalle crítico para defensa:** el repositorio documenta que **la integración automática de GitHub con Vercel no estaba conectada** en el despliegue verificado. Los despliegues se realizaron con **Vercel CLI** sobre commits; **un `git push` por sí solo NO implica que se despliegue automáticamente** hasta que se configure la Git Login Connection/integración. No afirmar CI/CD automático si no se ha verificado su habilitación posterior.

**Reproducibilidad:** el backend carga corpus completo (57.638) e índice (57.600×768). `prepare_runtime.py` valida hashes y `IndexFlatIP`. El frontend no cambia modelos ni métricas al desplegar; el modelo se carga **offline durante inferencia**, porque los pesos fueron obtenidos en build. Una petición puede sufrir *cold start* (carga inicial) y el plan tiene límites de CPU/RAM/capacidad. **No se reporta benchmark de concurrencia masiva ni SLA**; optimización bajo alta carga no fue objeto de este trabajo.

**¿Qué pasa al hacer push?** El commit cambia GitHub y la documentación/código versionado. Si existiera integración Git automática activa, Vercel podría construir un nuevo despliegue; **en el estado verificado**, se necesitaba despliegue por CLI. Cambiar fuente de Python o el encoder podría requerir crear una nueva Release de artefactos, actualizar `assets-manifest.json` y reconstruir la Function; no basta un `git push`.

---
## 8. Estudio específico: embeddings, FAISS y alternativas

### 8.1 ¿Dónde están BGE, MiniLM y E5 exactamente?

**Archivo:** `src/ri_fiqa/embedding_models.py` → variable `MODEL_SPECS`:

```python
MODEL_SPECS = {
    "minilm": EmbeddingProfile(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        query_prompt=None, document_prompt=None),
    "bge": EmbeddingProfile(
        model_id="BAAI/bge-base-en-v1.5",
        query_prompt="Represent this sentence for searching relevant passages: ",
        document_prompt=""),
    "e5": EmbeddingProfile(
        model_id="intfloat/e5-base-v2",
        query_prompt="query: ", document_prompt="passage: "),
}
```

- **MiniLM:** 384 dimensiones; evaluado en `validation`, MAP@1000 **0.333443**; menor tamaño de vectores y potencial menor latencia/memoria. **No es el modelo activo.**
- **BGE base v1.5:** 768 dimensiones; MAP de validación **0.364793** con su instrucción; mejor calidad que MiniLM en el experimento (**+9.40% relativo**). Fue elegido aun con más costo. En test final MAP **0.347148**.
- **BGE sin instrucción:** MAP validación **0.354656**. La diferencia con instrucción tiene p exploratoria ~0.1521: se conserva el perfil recomendado, **sin sostener que el prompt cause una mejora significativa**.
- **E5 base v2:** perfil de encoder presente en código, pero **no se dispone de una evaluación comparable**. No inventar una métrica para él.

**Dónde se construye el embedding documental:** `scripts/construir_indice_semantico.py::main()`:

```python
spec = MODEL_SPECS[args.encoder]
model = SentenceTransformer(spec.model_id, device=device)
encoder = configure_encoder(model, spec.query_prompt, spec.document_prompt)
# por lotes de documentos no vacíos:
embeddings = encoder.encode_document(valid_texts, normalize_embeddings=True, ...)
```

**Dónde se construye el embedding de consulta:** `src/ri_fiqa/retrieval/semantic.py::SemanticRetriever.search_many()`:

```python
embeddings = self.encoder.encode_query(
    textos, batch_size=batch_size,
    convert_to_numpy=True,
    normalize_embeddings=True, show_progress_bar=False,
)
vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
faiss.normalize_L2(vectors)
scores, positions = self.index.search(vectors, k)
```

**Dónde se decide el encoder activo al consultar:** `src/ri_fiqa/search_service.py::_get_semantic()` lee `data/processed/semantic_bge/metadata.json`, extrae `metadata['model_id']` y sus prompts, carga el índice precomputado y valida `model.get_embedding_dimension() == faiss_index.d`. **La API no elige dinámicamente BGE/MiniLM por cambiar el selector frontend**: la configuración debe concordar con los artefactos.

**Razón de conservar 38 documentos vacíos:** el corpus mantiene 57.638 IDs para integridad y comparación con BEIR; no es viable obtener embeddings significativos de texto inexistente. FAISS excluye **solo sus vectores**, registra 57.600 IDs y los asocia a textos originales. El índice léxico mantiene 57.638 IDs, incluso si algunos no tienen postings. Eliminar físicamente los vacíos **cambiaría el universo `N`, medias de longitud, IDs/artefactos, reproducción y podría afectar puntuaciones**, aunque probablemente no agreguen coincidencias.

### 8.2 Índice FAISS en producción: tipo y ubicación exacta

**Índice:** `faiss.IndexFlatIP(768)`; se crea en `scripts/construir_indice_semantico.py::main()` con `faiss.IndexFlatIP(dimension)`, se llena con `vector_index.add(vectors)` y se guarda con `faiss.write_index` en `data/processed/semantic_bge/index.faiss`. **Se carga** en `SearchService._get_semantic()` mediante `faiss.read_index`; se consulta con `SemanticRetriever.search_many()` usando `index.search`.

**Equivalencia:** para vectores normalizados `||q||=||d||=1`, `cos(q,d)=q·d`; por eso `IndexFlatIP` es búsqueda exacta por coseno tras normalización. Con `IndexFlatL2`, la distancia cuadrática entre vectores unitarios sería `||q-d||² = 2-2(q·d)`; idealmente da **el mismo orden** (menor L2 frente a mayor coseno), pero devuelve **scores distintos** y hay posibles diferencias numéricas de empates. No comparar scores de un índice con los del otro.

**Costo:** 57.600 × 768 × 4 bytes (`float32`) = **176.947.200 bytes ≈ 168,75 MiB** solo para vectores. El encoder, corpus original, índices léxicos, índices de metadatos y runtime elevan la memoria total. En Vercel Preview se reportó un pico de ~1,26 GB con modelos cargados. **Flat no se seleccionó por ser «el más rápido»**: el corpus era de tamaño manejable y se quería evaluar BGE sin introducir pérdida adicional por búsqueda aproximada.

### 8.3 Tabla para defender los índices FAISS

| Índice | Búsqueda y complejidad orientativa | Memoria | Ventaja | Desventaja; cuándo tendría sentido |
|---|---|---|---|---|
| **`IndexFlatIP` — actual** | Exacta, compara N vectores; ~`O(N·d)` por consulta. | ~`4d` bytes/vector. | Coseno exacto sobre vectores unitarios, sin entrenamiento. | Costo lineal de consulta; muy apropiado como baseline y corpus moderado. |
| `IndexFlatL2` | Exacta ~`O(N·d)`; minimiza distancia L2². | ~`4d`. | Simple y reproducible; en vectores unitarios casi idéntico orden al IP. | Scores/distancias cambian; obliga revisar interfaces/métricas. |
| **`IndexHNSWFlat`** | Aproximada, búsqueda sobre grafo; sublineal **frecuentemente**, sin garantía universal `O(log N)`. | Más que Flat, aprox. `4d +` enlaces por vector. | Menor latencia potencial en corpus grande; no necesita entrenar centroides. | Más memoria y parámetros (`M`, `efConstruction`, `efSearch`); el ranking puede variar. |
| **`IndexIVFFlat`** | Aproximada: escanea `nprobe` de `nlist` listas; costo condicionado a su distribución. | `4d +` IDs/estructuras. | Filtra candidatos, puede acelerar búsqueda. | Requiere entrenar centroide/quantizer y calibrar `nlist`, `nprobe`; pérdida de recall si insuficiente. |
| **`IndexPQ`** | Compara códigos comprimidos; puede recorrer N códigos pero **la distancia es aproximada por cuantización**. | Aproximadamente `ceil(M·nbits/8)` bytes/vector + tablas. | Reduce muchísimo memoria. | Cuantización introduce error; entrenamiento, selección de subcuantizadores. |
| **`IndexIVFPQ`** | Pruning IVF + vectores comprimidos PQ. | Muy inferior a Flat, según `M`, bits e IDs. | Alta escala con memoria acotada. | Dos fuentes de error (listas + compresión); más complejidad y experimentación. |

`N` = documentos indexados; `d` = dimensiones; `M` = parámetros de HNSW o número de subcuantizadores de PQ según contexto. Las cotas de índices aproximados son **orientativas**, no una garantía de latencia para FiQA. Ver [Faiss indexes](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes) y [Guidelines to choose an index](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index).

### 8.4 ¿Cómo se investigaría una migración a otros índices?

**No editar directamente el índice de producción.** Crear una rama y una carpeta de índice distinta; conservar BGE y los mismos documentos/consultas/qrels, y cambiar solo el índice. Capturar `latency p50/p95`, memoria y `recall@k` de vecinos **frente a Flat**, además de MAP/NDCG de FiQA; repetir con múltiples configuraciones. Ejemplos **ilustrativos para un script aislado**, no sustituciones directas de código productivo:

```python
import faiss
import numpy as np

d = 768
xb = np.asarray(vectores_documentales_normalizados, dtype='float32')

flat_ip = faiss.IndexFlatIP(d)  # Configuración vigente
flat_l2 = faiss.IndexFlatL2(d)  # L2²; al normalizar, ranking teórico equivalente
hnsw = faiss.IndexHNSWFlat(d, 32, faiss.METRIC_INNER_PRODUCT)
hnsw.hnsw.efConstruction = 200
hnsw.hnsw.efSearch = 64

quantizer = faiss.IndexFlatIP(d)
ivf = faiss.IndexIVFFlat(quantizer, d, 256, faiss.METRIC_INNER_PRODUCT)
ivf.train(xb)       # ENTRENAMIENTO DEL ÍNDICE, no del encoder BGE
ivf.nprobe = 16

pq = faiss.IndexPQ(d, 48, 8, faiss.METRIC_INNER_PRODUCT)
pq.train(xb)        # d=768 divisible por 48; entrenar códigos PQ

# Los siguientes add son solo para un índice elegido y ya entrenado si lo requiere:
# index.add(xb)
# faiss.write_index(index, 'data/processed/semantic_bge_EXPERIMENTO/index.faiss')
```

**Ubicaciones que habría que cambiar y validar conjuntamente:**

1. `scripts/construir_indice_semantico.py::main` — constructor FAISS, entrenamiento si aplica, `faiss.write_index`, metadatos `faiss_index`.
2. `src/ri_fiqa/search_service.py::_get_semantic` — carga FAISS, dimensión/cantidad y configuración de parámetros de búsqueda cuando proceda.
3. `src/ri_fiqa/retrieval/semantic.py::SemanticRetriever.search_many` — conserva `encode_query` pero interpreta `scores`; evaluar orden ascendente L2 o descendente IP de la clase concreta. La implementación actual **ordena siempre los scores de forma descendente**: con L2 podría ser incorrecta sin adaptación.
4. `src/ri_fiqa/runtime.py::inspect_assets` — comprueba literalmente `metadata['faiss_index'] == 'IndexFlatIP'`; otro índice daría `/ready` no listo.
5. `backend/assets-manifest.json`, `backend/prepare_runtime.py`, `backend/main.py` — nuevos archivos/hashes y Release; comprobar dimensiones, IDs, recursos y despliegue.
6. `tests/test_semantic.py`, `tests/test_runtime.py`, `tests/test_vercel_assets.py`, `backend/verify_api.py`, `results/` — ajustar validaciones/medir pérdida de ranking sin sobrescribir métricas oficiales.

**Conclusión para defensa:** Flat se eligió porque **permite atribuir las diferencias observadas al encoder y al corpus**, sin confundirlas con la calidad de una búsqueda de vecinos aproximada; no demuestra ser el índice más rápido.

---

## 9. Posibles preguntas del docente y cambios que pueden realizarse

> Todas las rutas son **exactas** en la revisión analizada. Los fragmentos son ejemplos de *qué se tocaría* en un experimento posterior, **no instrucciones para alterar los resultados de la entrega**. Cambios de modelo/índice requieren reindexación, metadatos, tests y un experimento aparte.

| Qué pide cambiar | Archivo · símbolo exacto | Cambio orientativo | Beneficios posibles | Riesgo para calidad / velocidad / memoria | Dificultad |
|---|---|---|---|---|---|
| BM25 `k1/b` | `src/ri_fiqa/config.py` · `SELECTED_CONFIG` | `bm25_k1=1.2, bm25_b=0.5` en **rama de prueba**, sin tocar fijo. | Mejor para otros corpus. | MAP puede subir o bajar; memoria igual, costo similar. | Baja para probar; media para validar. |
| Snowball ↔ baseline/WordNet | `config.py` · `RetrievalConfig.morphology`; `preprocessing.py` · `TextPreprocessor.process` | `morphology='lemmatization'` y **reconstruir** índice correspondiente. | Preservar más forma lingüística. | Cambia vocabulario/postings, rankings; WordNet requiere recurso; costo de construcción. | Media. |
| Stopwords protegidas | `preprocessing.py` · `PROTECTED_TERMS`, `STOPWORDS` | Añadir solo término justificado. | Evitar perder negaciones o identificadores. | Puede aumentar índice o afectar recall/precisión; reindexar. | Media. |
| Tokenizador léxico | `preprocessing.py` · `TOKEN_PATTERN`, `normalize` | Adaptar decimales, símbolos o términos compuestos. | Mejor consistencia en consultas especiales. | Cambia totalmente términos/IDF; exige reindexación. | Media. |
| Jaccard | `retrieval/jaccard.py` · `JaccardRetriever.search` | Cambiar scoring sería un modelo diferente. | Experimento de similitud. | Métricas dejan de ser comparables al Jaccard binario original. | Media. |
| TF-IDF IDF | `retrieval/tfidf.py` · `_prepare` | Fórmula de `idf` distinta. | Explorar pesos. | Recalcular normas; cambios de ranking; velocidad casi igual. | Media. |
| BM25 fórmula | `retrieval/bm25.py` · `BM25Retriever.__init__`, `search` | Ajustar definición de IDF/saturación. | Explorar otra variante. | Rehacer evaluación y justificar nueva definición. | Media/alta. |
| BGE → MiniLM | `embedding_models.py` · `MODEL_SPECS`; `config.py` · `semantic_index`; `scripts/construir_indice_semantico.py::main`; `search_service.py::_get_semantic` | Crear **otro** índice, 384 D, y selección coherente. | Menor RAM y coste de embeddings. | En FiQA validación MAP fue inferior (0.333443 vs 0.364793); hashes/build incompatibles. | Alta. |
| E5 o encoder nuevo | `embedding_models.py` · `MODEL_SPECS`; `configure_encoder`; scripts | Perfil + prompts correctos + nuevo índice y evaluación. | Posible mejor calidad/costo. | No hay métrica actual; memoria/latencia indeterminadas. | Alta. |
| Prefijo BGE | `embedding_models.py` · `MODEL_SPECS['bge'].query_prompt`; `metadata.json` persistido | Hacer ablación solo de consultas para estudio. | Comparar estilo de query encoder. | Puede alterar calidad; experimento actual no significativo. | Media. |
| FAISS Flat ↔ HNSW/IVF/PQ | `scripts/construir_indice_semantico.py::main` + `runtime.inspect_assets` | Constructor y entrenamiento del índice + rebuild. | Menor latencia o memoria potenciales a escala. | Pérdida de recall aproximado y cambios de infraestructura. | Alta. |
| Top-K por defecto | `src/ri_fiqa/api.py` · `SearchRequest.top_k`, `CompareRequest.top_k`; `SearchForm.tsx` | Ajustar **ambas capas** y tests. | Mayor cantidad de documentos mostrados. | Más payload/latencia; API actual permite 1..20. | Baja/Media. |
| Modelo predeterminado | `src/ri_fiqa/api.py::models`; `SearchRequest.model`; `frontend/src/lib/types.ts::DEFAULT_MODEL`; `SearchService.search` | Elegir p. ej. BM25 **solo en experimento de UI**. | Menor latencia de primera búsqueda. | Calidad media menor; requiere contratos consistentes. | Media. |
| Cache / memoria | `search_service.py` · `_get_index`, `_get_semantic`, `_get_document_texts` | Carga diferida o políticas de caché. | Mejor cold start / menos memoria a costa de CPU. | Errores por recurso no cargado; concurrencia. | Alta. |
| API y respuestas | `api.py` · modelos Pydantic, `execute`, `search`, `compare`; `frontend/src/lib/types.ts`, `api.ts` | Nueva propiedad o ruta **con versionado**. | Funcionalidad de clientes. | Rompe contrato actual si se hace sin compatibilidad. | Alta. |
| CORS/despliegue | `.env`, `backend/main.py`, `docs/DESPLIEGUE.md` | Orígenes específicos/autorizados. | Acceso de nuevo cliente. | Permisos mal configurados o inseguridad. | Baja/Media. |
| LLM generativo | **No hay archivo ni función actual** | Requeriría crear componente/servicio de generación y otro contrato. | Respuestas sintetizadas con citas. | Más costo, latencia y riesgo de alucinación; **fuera del proyecto entregado**. | Muy alta. |
| Prompt de sistema LLM | **No existe** | No hay variable que comentar o descomentar. | N/A. | No confundir con prompt de BGE. | No aplicable. |
| RRF histórico | `retrieval/fusion.py::weighted_rrf`, `config.py::rrf_*`, `search_service.py::rank_many` | Ajustar en rama experimental. | Combinar señales léxicas/semánticas. | Ventaja pequeña no demostrada; más inferencia. | Alta si se cambia/retira contrato. |

### 9.1 Fragmentos de configuración para explicar en clase (NO activar en entrega)

```python
# src/ri_fiqa/config.py — CONFIGURACIÓN ACTUAL, NO MODIFICAR:
SELECTED_CONFIG = RetrievalConfig(morphology="stemming", bm25_k1=0.8, bm25_b=0.75)

# Ejemplo didáctico; NO sustituir el valor anterior ni usar test para elegir:
# EXPERIMENTO_LEMMA = RetrievalConfig(morphology="lemmatization", bm25_k1=0.8, bm25_b=0.75)
# EXPERIMENTO_BM25 = RetrievalConfig(morphology="stemming", bm25_k1=1.2, bm25_b=0.5)
```

```python
# src/ri_fiqa/embedding_models.py — entrada de perfil, no selector del servicio:
# MODEL_SPECS["minilm"].model_id == "sentence-transformers/all-MiniLM-L6-v2"
# MODEL_SPECS["bge"].model_id == "BAAI/bge-base-en-v1.5"

# CUIDADO: seleccionar otro perfil cambia dimensión/espacio semántico:
# no usar el mismo index.faiss ni los doc_ids/metadata sin reconstrucción.
```

### 9.2 Guía de «comentar/descomentar» segura

**Lo que sí se puede comentar como ayuda:** alternativas documentadas en bloques `# Posible mejora (NO ACTIVA): ...` junto a `SELECTED_CONFIG`, `MODEL_SPECS`, constructor `IndexFlatIP`, `PROTECTED_TERMS` y parámetros HTTP. **Lo que NO se debe introducir:** dos constructores alternativos `IndexFlatIP`/`HNSW` listos para comentar/descomentar sin entrenamiento y actualización de metadata; dos `SELECTED_CONFIG` activos; cambios de dispositivo/encoder por hardcodeo; prompts generativos inventados.

Una estrategia de defensa más segura es **anotar ejemplos de uso en comentarios, sin alterar ninguna instrucción ejecutable** y mostrar la configuración en tiempo real con `/models`, `metadata.json` y los comandos de esta guía.

---
## 10. Comandos útiles para demostración — copiar/pegar

**Preparación:** ejecutar estos ejemplos en PowerShell **desde la raíz** con `.venv` activo y corpus/índices existentes; donde se indique, iniciar API. Los comandos de solo lectura son preferibles durante una defensa.

### 10.1 Salud, readiness, modelos, parámetros

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/models | ConvertTo-Json -Depth 6
# API pública, si no está ejecutándose localmente:
Invoke-RestMethod https://fiqa-api.vercel.app/models | ConvertTo-Json -Depth 6
```

**Explica:** `/health` puede devolver OK mientras `/ready` informa 503 si faltan corpus o índices; `models` expone la configuración final. `/models` puede incluir el híbrido como compatibilidad histórica, aunque la web solo muestra cuatro.

### 10.2 Búsqueda real por API y salida estructurada

```powershell
$body = @{ query='What is the difference between APR and APY?'; model='bge'; top_k=3 } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/search -ContentType 'application/json' -Body $body
$r | Select-Object query,model,count,elapsed_ms
$r.results | Select-Object rank,doc_id,score,preview | Format-Table -Wrap
$r.results[0].text
```

Cambiar únicamente `$body` para otro modelo `jaccard`, `tfidf`, `bm25` o `bge`. El `score` y `elapsed_ms` son los que devolvió el backend, **no los calcula el navegador**.

### 10.3 Comparar dos modelos sin fusionarlos

```powershell
$body = @{ query='What is the difference between APR and APY?'; models=@('bm25','bge'); top_k=3 } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/search/compare -ContentType 'application/json' -Body $body
$r.rankings | ForEach-Object { "MODELO: $($_.model)"; $_.results | Select-Object rank,doc_id,score,preview | Format-Table -Wrap }
```

**Defensa:** son dos rankings separados, no un único ranking RRF.

### 10.4 Búsqueda Python sin API ni navegador

```powershell
python scripts/buscar.py --model jaccard --query 'What is APR?' --top 3
python scripts/buscar.py --model tfidf --query 'What is APR?' --top 3
python scripts/buscar.py --model bm25 --query 'What is APR?' --top 3
python scripts/buscar.py --model bge --query 'What is APR?' --top 3 --json
python scripts/buscar.py --model bge --interactive
```

**Defensa:** `scripts/buscar.py` usa el mismo `SearchService` del backend; elimina la UI de la ecuación para demostrar que el motor funciona solo.

### 10.5 Auditar corpus original e inspeccionar un documento por ID

```powershell
# Comprobar tamaño e inspeccionar tres primeros registros
python -c "from datasets import load_from_disk; d=load_from_disk('data/raw/corpus'); print('Documentos:',len(d)); print([(r['_id'],(r['text'] or '')[:140]) for r in d.select(range(3))])"

# Inspeccionar un doc_id conocido; recorrer el corpus una sola vez para esta demo
python -c "from datasets import load_from_disk; d=load_from_disk('data/raw/corpus'); x=next(r for r in d if str(r['_id'])=='263225'); print('ID:',x['_id']); print('TEXTO:',x['text'])"

# Consultas/qrels (solo evaluación offline)
python -c "from datasets import load_from_disk; q=load_from_disk('data/raw/queries'); r=load_from_disk('data/raw/qrels'); print('Consultas:',len(q)); print('Qrels:',{k:len(r[k]) for k in r.keys()})"

# Resultados de auditoría ya guardados (sin ejecutar nada costoso)
Get-Content results/auditoria_fiqa.json -Raw | ConvertFrom-Json | Select-Object -ExpandProperty corpus | Format-List
```

### 10.6 Inspeccionar índice invertido y una palabra

```powershell
python scripts/construir_indice.py --term interest --morphology stemming

# Inspección directa de estadísticas y postings, sin reconstrucción
python -c "from ri_fiqa.indexing import InvertedIndex; i=InvertedIndex.load('data/processed/inverted_index_stemming.json.gz'); print('Documentos:',i.num_documents,'Vocabulario:',i.vocabulary_size,'Tokens:',i.total_tokens); print('DF interest:',i.document_frequency('interest')); print('Postings muestra:',list(i.get_postings('interest').items())[:5])"
```

**Defensa:** para Jaccard se leen coincidencias; TF-IDF combina `tf` y `df`; BM25 añade saturación y longitudes. **Un índice, tres rankings distintos.**

### 10.7 Mostrar Snowball y configuración BM25 actual

```powershell
python -c "from ri_fiqa.config import SELECTED_CONFIG as c; print(c); print('Índice léxico:',c.lexical_index)"
python -c "from ri_fiqa.preprocessing import TextPreprocessor,PreprocessConfig; t=TextPreprocessor(PreprocessConfig(morphology='stemming')); print(t.process('What is considered a business expense on a business trip?'))"

# Datos de experimento ya persistidos (no recalcula nada)
Get-Content results/preprocessing_v1/selection_frozen.json -Raw
Get-Content results/preprocessing_v1/comparison_validation.csv
```

### 10.8 Mostrar exactamente qué índice FAISS y qué encoder están en disco

```powershell
python -c "import faiss; i=faiss.read_index('data/processed/semantic_bge/index.faiss'); print('Clase:',type(i).__name__,'Vectores:',i.ntotal,'Dimensiones:',i.d,'Metric:',i.metric_type)"
Get-Content data/processed/semantic_bge/metadata.json -Raw | ConvertFrom-Json | Select-Object model_id,encoder_profile,query_prompt,faiss_index,dimension,normalization,original_corpus_size,indexed_documents,excluded_empty_documents | Format-List
Get-Content data/processed/semantic_bge/doc_ids.json -TotalCount 10
```

**Defensa:** clase `IndexFlatIP` e índice con 57.600 vectores de 768 D. No afirmar que FAISS almacena el documento completo: conserva representación y el mapeo de IDs; el texto se obtiene de `data/raw/corpus`.

### 10.9 Métricas finales congeladas (más seguro que recalcular en exposición)

```powershell
Get-Content results/preprocessing_v1/final_test/comparison_test.csv
Get-Content results/preprocessing_v1/final_test/stemming_bm25_test.json -Raw | ConvertFrom-Json | Select-Object -ExpandProperty aggregate
Get-Content results/service_bge_test_metrics.json -Raw | ConvertFrom-Json | Select-Object -ExpandProperty aggregate
# Tabla principal también integrada al frontend
Get-Content frontend/src/data/benchmark.json -Raw | ConvertFrom-Json | Select-Object split,queries,current
```

### 10.10 Demo de MiniLM sin destruir BGE (OPCIONAL, no ejecutar en exposición)

```powershell
# Construye SOLO un índice piloto e independiente, NO sustituye semantic_bge
python scripts/construir_indice_semantico.py --name semantic_minilm_piloto --encoder minilm --limit 100 --batch-size 16 --device cpu
```

Esto crea **un índice incompleto** y no es aceptable como artefacto de producción ni como prueba de calidad en FiQA test. La defensa puede limitarse a mostrar `MODEL_SPECS` y las métricas de validación ya guardadas.

---

## 11. Preguntas probables del docente (respuesta breve y defendible)

1. **¿Por qué FiQA y no inventar documentos?** Dataset público BEIR con corpus, consultas y qrels; permite evaluación reproducible de los cuatro métodos sobre la misma colección.
2. **¿Por qué 57.638 documentos pero 57.600 vectores?** Hay 38 textos vacíos; se preserva el corpus/ID, pero no se genera embedding de contenido vacío.
3. **¿Para qué sirve un índice invertido?** Mapea término→documentos/frecuencia y evita examinar todos los textos para cada palabra en recuperación léxica.
4. **¿Cada método léxico tiene un preprocesamiento diferente?** No: **los tres comparten `TextPreprocessor` Snowball** y el índice; lo distinto es la función de puntuación.
5. **¿Por qué BGE no aplica Snowball?** El encoder preentrenado espera el texto procesado por su tokenizer neuronal; sustituirlo por raíces cambiaría su entrada y el experimento.
6. **¿Qué aporta Jaccard?** Baseline interpretable de solapamiento; muestra límites de coincidencia binaria.
7. **¿Qué aporta TF-IDF?** Peso por frecuencia y rareza; coseno compara vectores sin depender directamente de su magnitud.
8. **¿Por qué IDF suavizada?** Evita degeneraciones numéricas y conserva peso mínimo a términos frecuentes (`log((N+1)/(df+1))+1`).
9. **¿Qué aporta BM25?** Saturación de TF y normalización de longitud, útiles para documentos de tamaños diferentes.
10. **¿Por qué `k1=.8, b=.75`?** Se buscaron nueve pares en validación para el índice Snowball y se congeló el elegido antes de test.
11. **¿Stemming o lematización?** Snowball redujo el vocabulario y mejoró MAP de los tres léxicos en esta colección; solo se comparó WordNet nominal, no toda lematización posible.
12. **¿Por qué BGE frente a MiniLM?** Mayor MAP de validación (0.364793 vs 0.333443), aceptando 768 vs 384 D y más memoria/costo.
13. **¿Por qué `IndexFlatIP`?** Exactitud y simplicidad para 57.600 vectores; no se hizo comparación experimental de velocidad con HNSW/IVF.
14. **¿Producto interno equivale a coseno?** Sí, **si** ambos vectores son unitarios por normalización L2.
15. **¿Hugging Face recibe la consulta de cada usuario?** No en el despliegue: el encoder se carga localmente en la Function desde pesos predescargados; consultas se codifican dentro del backend.
16. **¿Qué significa top-K?** Cantidad de documentos devueltos, API 1..20; no es `candidate_depth=1000` usado en evaluaciones.
17. **¿Cómo sabe el frontend qué es relevante?** No decide relevancia: renderiza el orden y scores dados por el backend. Las métricas offline usan qrels.
18. **¿Qué es MAP?** Media de AP por consulta; valora recuperar relevantes en buenas posiciones. Una AP cero también cuenta.
19. **¿Qué significa Recall@100?** Porcentaje de relevantes *etiquetados* recuperados en las 100 primeras posiciones.
20. **¿BGE gana siempre?** No; en consultas muy dependientes de terminología exacta BM25/TF-IDF pueden ganar. El promedio favorece BGE.
21. **¿Se genera una respuesta con IA?** No; devuelve fragmentos/textos completos de documentos. No hay LLM ni prompt de sistema, solo encoder de embeddings.
22. **¿Qué significa `RAG` aquí?** Solo el componente de recuperación que podría usarse como contexto para un generador futuro; la fase generativa **no está implementada**.
23. **¿Comparar modelos es fusionarlos?** No; compare devuelve rankings separados. RRF opcional combina rankings y hoy está oculto en la web.
24. **¿Por qué dos proyectos Vercel?** Separan build estático ligero del backend Python pesado, permiten despliegues/rollback independientes.
25. **¿Un push despliega automáticamente?** **No en el estado de despliegue documentado:** se usó Vercel CLI y la conexión Git automática seguía pendiente.
26. **¿Por qué `/ready` además de `/health`?** Health solo indica que el proceso responde; ready comprueba archivos, configuración y hashes en producción.
27. **¿Dónde están los documentos?** En dataset almacenado localmente en runtime `data/raw/corpus`; el índice FAISS guarda vectores y la tabla de IDs, no respuestas completas.
28. **¿Se entrena BGE?** No hay fine-tuning; se usa preentrenado. La operación `ivf.train` sería entrenamiento del índice de clustering, **no del encoder**.
29. **¿Por qué no eliminar todo el híbrido ahora?** La web no lo expone, pero API, scripts, pruebas y métricas históricas aún dependen de él; hacerlo sin cambiar nada es contradictorio.
30. **¿Cómo mejoraría un proyecto futuro?** Evaluar por pasajes, cross-encoder/reranking, otros embeddings y ANN con pruebas pareadas; no atribuirles mejoras aún no medidas.

---

## 12. Auditoría del híbrido, código no usado y plan seguro de limpieza

### 12.1 Inventario exacto de dependencias híbridas

| Componente | Referencia actual | ¿Se puede borrar sin más? |
|---|---|---|
| `src/ri_fiqa/retrieval/fusion.py::weighted_rrf` | Lo llama `SearchService.rank_many` y `scripts/experimentar_preprocesamiento.py`. | **No**, hay imports y función de API activable. |
| `src/ri_fiqa/search_service.py` | `MODELS` incluye `hybrid`, branch `search`/`rank_many`. | **No**, rompería solicitudes existentes. |
| `src/ri_fiqa/config.py` | `rrf_k`, `rrf_semantic_weight`. | **No** sin actualizar consumidores, diagnósticos y experimento. |
| `src/ri_fiqa/api.py` | `ModelName`, `SearchRequest`, `CompareRequest`, `MODEL_INFO` aceptan híbrido. | **No** sin cambiar el contrato HTTP. |
| `src/ri_fiqa/preprocessing_experiment.py` | `MODELS` incluye híbrido para selección histórica global. | **No** sin alterar interpretación del experimento morfológico. |
| `scripts/evaluar_hibrido.py` | CLI histórica que fusiona TREC existentes. | **Candidato a archivar/eliminar** si no lo invocan scripts/tests/documentación obligatorios. |
| `scripts/experimentar_preprocesamiento.py` | Funciones `hybrid_report`, validación y resultados por variante. | **No borrar todo**: contiene selección central de Snowball. |
| `scripts/evaluar_final.py`, `scripts/verificar_api.py`, `backend/verify_api.py` | `hybrid` contemplado en modelos/validación. | **No** sin revisar pruebas y contrato. |
| `scripts/analizar_errores.py` | Menciones al modelo híbrido en investigación histórica. | Revisar; preservar utilidad académica si hay referencias. |
| `tests/test_fusion.py`, `tests/test_search_service.py`, `tests/test_api.py`, `tests/test_morphology_experiment.py`, `tests/test_preprocessing_protocol.py` | Pruebas directas o indirectas de fusión y protocolo. | **No** mientras el código/contrato se mantengan. |
| `frontend/src/lib/types.ts` | `modelId` y `LABELS` incluyen híbrido histórico, pero `ACTIVE_MODEL_IDS` lo excluye. | **No** cambiar a ciegas; valida respuestas históricas. |
| `frontend/src/data/benchmark.json`, `frontend/src/components/Benchmark.tsx` | Resultados históricos de híbrido en evaluación. | **No** si se preserva evidencia del informe. |
| `frontend/scripts/sync-benchmark.mjs` y `results/service_hybrid_*`, `results/preprocessing_v1/*hybrid*` | Dependencias de sincronización de tablas/protocolo; revisar rutas reales antes de tocar. | **No** borrar resultados mientras alguien los lea/verifique. |
| `backend/main.py` | En Preview, `measure_all_models` itera cinco sistemas y reporta RRF. | **No**, pruebas de despliegue esperan ese estado. |

**Conclusión verificable:** el híbrido **no está muerto en backend**; está **deshabilitado como opción de interfaz**, pero accesible por contrato/API y usado en investigación, tests y evidencias. Por tanto, la frase «eliminar cualquier resto del híbrido sin alterar API ni resultados» **no es realizable en sentido literal**. La única limpieza potencialmente compatible con API intacta es archivar **scripts CLI puramente históricos sin consumidores**, después de comprobar llamadas, tests y documentación; no eliminar `fusion.py` ni los identificadores de API.

### 12.2 Clasificación de candidatos a «código muerto»

- **No confirmado como muerto:** todos los módulos del motor; RRF; `preprocessing_experiment.py`; `backend/prepare_runtime.py`; `backend/verify_api.py`; scripts que sostienen resultados reproducibles. No confundir «no llamado en la petición HTTP» con «innecesario para el proyecto».
- **Obsoleto de muy bajo riesgo:** comentario `# MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"` en `scripts/construir_indice_semantico.py` no ejecuta nada y duplica la configuración real de `MODEL_SPECS`. Es solo comentario, no se ganó rendimiento al retirarlo.
- **Potencialmente redundantes como herramientas CLI:** `scripts/buscar_jaccard.py` frente a `scripts/buscar.py`, `scripts/evaluar_jaccard.py` frente a `scripts/evaluar_modelos.py`, `scripts/evaluar_hibrido.py` si se acuerda conservar investigación mediante resultados estáticos. La redundancia no prueba inutilidad: revisar *imports*, documentación, ejecución y pruebas antes de decidir.
- **Datos históricos:** `results/hybrid*`, `results/preprocessing_v1/*hybrid*`, `results/estadistica_bge_vs_rrf.json` no son código; forman parte de la evidencia. Mejor conservarlos en Git o archivarlos explícitamente; no usarlos para recalcular métricas de producción.
- **Dependencias «sobrantes» no confirmadas:** `numpy`, `datasets`, `nltk`, `scikit-learn`, `faiss-cpu`, `sentence-transformers`, `torch`, `fastapi` tienen uso activo. `ir-measures` se usa para verificar métricas fuera del runtime de producción. **No se identificó una dependencia segura de desinstalar solo por retirar un CLI híbrido**, pues RRF usa biblioteca estándar y `SearchResult`.

### 12.3 Plan de limpieza seguro por etapas

1. **Congelar estado y evidencia:** rama `chore/auditoria-defensa`, SHA base, `git status --short`, copia de `results/` y manifiestos; no modificar producción `main` a ciegas.
2. **Auditoría estática:** buscar `hybrid|weighted_rrf|fusion|rrf_` en `src`, `scripts`, `tests`, `backend`, `frontend`, `docs`, `results` con `rg`/`git grep`. Crear matriz **productivo / pruebas / experimentación / evidencia / documentación**.
3. **Establecer invariantes:** mismo `/health`, `/ready`, `/models`, `/search`, `/search/compare`, misma configuración Snowball/0.8/0.75/BGE/FlatIP, mismos resultados para consultas de regresión, mismos cuatro modelos visibles y mismas métricas del benchmark.
4. **Fase comentarios solamente:** añadir `# Posible mejora (NO ACTIVA)` junto a parámetros y constructor FAISS; **nunca** modificar líneas ejecutables. Revisar `git diff --check` y pruebas.
5. **Proponer eliminación individual:** empezar únicamente con `scripts/evaluar_hibrido.py` si no tiene consumidores y la reproducción histórica continúa cubierta por resultados/versionado. **No borrar `fusion.py`, `MODELS`, API ni benchmark.** Registrar candidatos no eliminables con razón.
6. **Verificar después de CADA cambio:** `python -m unittest discover -s tests -v`, `npm test`, `npm run benchmark:check`, `npm run build`, pruebas HTTP/e2e si recursos están disponibles, y comparación de `results` congelados; no aceptar actualizaciones automáticas de métricas como parte de un cleanup.
7. **Validar despliegue si se toca un archivo empaquetado:** inspeccionar `backend/prepare_runtime.py`, manifiesto, Preview de Vercel y suite pública. Descartar cualquier cambio que altere RAM/contrato/rankings sin autorización.
8. **Entrega de auditoría:** README o informe de limpieza con archivos tocados, motivo, resultados de tests y ejemplos de regresión. Nunca informar «sin cambios» si no se midió.

**Estado de ejecución de esta fase:** se elaboró documentación y plan; **no se borró código ni se alteraron algoritmos, endpoints, métricas, índices o artefactos productivos**. Se prepararon **comentarios de defensa no ejecutables en siete archivos de código** y su contenido ejecutable se verificó sin cambios; **no se ejecutó una nueva batería de pruebas** en esta sesión por no contar con el runtime completo. El prompt de Codex complementario permite continuar la auditoría y limpieza en un clon con recursos y pruebas.

---

## 13. Resumen para una exposición de cinco minutos del código

1. **Entrada:** React recoge texto y selector (4 modelos), envía JSON a FastAPI.
2. **Enrutamiento:** FastAPI valida, `SearchService` decide retriever, reutiliza cachés.
3. **Léxico:** un índice invertido + preprocesador común Snowball; Jaccard/TF-IDF/BM25 cambian solo la puntuación.
4. **Semántico:** BGE produce embedding de query; FAISS `IndexFlatIP` recupera vecinos exactos en 57.600 vectores; mapeo IDs.
5. **Salida:** se adjuntan textos originales, ranking, score y tiempo; no se redactan respuestas con un LLM.
6. **Evidencia:** test 648 qrels, MAP: 0.0386 / 0.1412 / 0.2103 / **0.3471**. El híbrido quedó como experimento, fuera de la UI.
7. **Despliegue:** frontend estático + API Python en dos proyectos Vercel; pesos BGE y corpus precargados/verificados; no se descarga Hugging Face en cada consulta.

---

## 14. Fuentes para profundizar y comprobar decisiones

- [Repositorio y README (versión revisada)](https://github.com/Cesarbmm/ProyectoRI/tree/1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23) — código y scripts exactos de esta revisión.
- [Despliegue documentado](https://github.com/Cesarbmm/ProyectoRI/blob/1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23/docs/DESPLIEGUE.md), [backend en Vercel](https://github.com/Cesarbmm/ProyectoRI/blob/1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23/backend/README.md).
- [Experimentación morfológica](https://github.com/Cesarbmm/ProyectoRI/blob/1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23/docs/EXPERIMENTOS_PREPROCESAMIENTO.md), [resultados de test](https://github.com/Cesarbmm/ProyectoRI/blob/1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23/results/preprocessing_v1/final_test/comparison_test.csv).
- [Faiss: índices](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes), [criterios de elección](https://github.com/facebookresearch/faiss/wiki/Guidelines-to-choose-an-index), [index factory](https://github.com/facebookresearch/faiss/wiki/The-index-factory).
- [BAAI/bge-base-en-v1.5](https://huggingface.co/BAAI/bge-base-en-v1.5), [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2).

**Documento complementario:** `PROMPT_CODEX_AUDITORIA_Y_COMENTARIOS.md`, listo para copiar a Codex, exige auditoría, comentarios mínimos, protección del contrato, tests y reporte de cualquier eliminación bloqueada.