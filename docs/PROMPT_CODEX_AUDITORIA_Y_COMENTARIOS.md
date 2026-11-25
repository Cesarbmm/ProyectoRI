# Prompt para Codex — Auditoría, comentarios estratégicos y limpieza segura de FiQA

**Usar este prompt desde la raíz del repositorio `Cesarbmm/ProyectoRI`, preferentemente en una rama nueva.**

```text
Actúa como ingeniero senior de Python, FastAPI, Recuperación de Información y auditoría de repositorios, con criterios de seguridad de cambios y reproducibilidad científica.

CONTEXTO
- Repositorio: https://github.com/Cesarbmm/ProyectoRI
- Proyecto FiQA / BEIR de recuperación documental, YA TERMINADO Y DESPLEGADO.
- SHA de referencia del estudio: 1a9c4f9cced7fe1c8a2d7481a88129ba0e2b0f23. Compara con el HEAD actual antes de trabajar.
- Frontend React/Vite en Vercel; backend FastAPI, BGE, FAISS y tres retrievers léxicos.
- Modelos web: Jaccard, TF-IDF, BM25 y BGE + FAISS. BGE predeterminado.
- Configuración congelada: Snowball inglés, BM25 k1=0.8, b=0.75, BGE BAAI/bge-base-en-v1.5, FAISS IndexFlatIP con 57.600 vectores de 768 D.
- Corpus FiQA 57.638 documentos, 38 vacíos; test 648 consultas y resultados académicos congelados.
- RRF híbrido está OCULTO EN FRONTEND, PERO SIGUE PRESENTE EN LA API, EN PRUEBAS Y EN EL EXPERIMENTO MORFOLÓGICO HISTÓRICO.
- No hay LLM ni RAG generativo; solo recuperación/ranking. No inventes prompt de sistema, generación ni microservicios.
- Documento de contexto: ESTUDIO_PROYECTO.md si existe (verifica siempre contra código, no lo des por infalible).

OBJETIVO
Producir una auditoría estática completa, añadir SOLO comentarios pedagógicos estratégicos que ayuden a explicar qué se podría modificar y, por separado, identificar si hay scripts exclusivamente históricos de fusión que se puedan archivar o borrar sin efectos. NO desarrollar funciones ni alterar el resultado actual.

RESTRICCIONES INNEGOCIABLES
1. No cambiar comportamiento observable, orden de ranking, puntuaciones, IDs, parámetros congelados, tiempo de inferencia por lógica nueva, endpoints, esquemas JSON, modelos disponibles por API, ni cuatro modelos visibles en frontend.
2. No cambiar hashes, Release, index.faiss, doc_ids.json, metadata.json, pesos BGE, corpus, qrels, benchmark.json ni archivos results/ históricos.
3. No eliminar ningún test para hacer que una refactorización pase. No modificar expectativas de tests ni métricas para adaptarlas a un cambio accidental.
4. No borrar código de RRF que todavía usa SearchService, la API, el experimento de Snowball, el frontend de evaluación o las pruebas.
5. No renombrar clases, funciones, archivos públicos o variables importadas.
6. No convertir parámetros activos en toggles de comentar/descomentar que podrían crear índices inconsistentes. Los ejemplos son comentarios NO ACTIVOS.
7. No realizar push a main, desplegar Vercel ni ejecutar comando destructivo. Crear rama, commits separados solo después de pruebas.
8. Si una petición de eliminación entra en conflicto con preservar la API o los resultados, CONSIDERARLA BLOQUEADA y explicarlo; no inventes compatibilidad.

FASE A — INVENTARIO Y AUDITORÍA SOLO LECTURA
A1. Ejecuta git status --short, git rev-parse HEAD y obtén árbol actual. No sobrescribas cambios de trabajo.
A2. Lee completamente:
    src/ri_fiqa/api.py, config.py, embedding_models.py, preprocessing.py,
    indexing.py, search_service.py, runtime.py, evaluation.py,
    preprocessing_experiment.py, statistics.py, retrieval/*.py;
    backend/main.py, backend/prepare_runtime.py, backend/verify_api.py,
    backend/assets-manifest.json, backend/pyproject.toml;
    scripts/*.py; frontend/src/lib/*.ts; frontend/src/components/*;
    frontend/src/data/benchmark.json; docs/DESPLIEGUE.md y README.md.
A3. Usa rg / git grep para encontrar referencias y pruebas:
    rg -n -i 'hybrid|weighted_rrf|rrf_|fusion|semantic_bge|IndexFlatIP|MODEL_SPECS|SELECTED_CONFIG' src scripts tests backend frontend docs results README.md
A4. Produce una MATRIZ con archivo, símbolo, importadores/consumidores, uso en producción, uso experimental, uso en pruebas, uso histórico, certeza de estar muerto y propuesta (conservar/archivar/borrar).
A5. Identifica los cambios mínimos seguros; no asumas que «script no invocado desde FastAPI» equivale a código muerto.
A6. Identifica los bloques donde sería más útil dejar comentarios de defensa, pero limita el total a aproximadamente 6–12 comentarios útiles.

FASE B — SOLO COMENTARIOS, SIN VARIAR CÓDIGO EJECUTABLE
En los puntos que efectivamente existen y están vigentes, añade mensajes breves, en español, como:
  # Posible mejora (NO ACTIVA): comparar BM25 con otros k1/b únicamente en validation.
  # Riesgo: modificar k1/b cambia los rankings del experimento congelado.

  # Posible mejora (NO ACTIVA): MiniLM reduce dimensionalidad (384 vs 768 de BGE).
  # Requiere nuevo índice, metadata, manifests, evaluación y pruebas.

  # Posible mejora (NO ACTIVA): IndexHNSWFlat/IndexIVFFlat para grandes corpus.
  # No sustituir FlatIP aquí: requieren ajuste, nueva indexación y pruebas de recall.

  # Posible mejora (NO ACTIVA): probar WordNet nominal.
  # El preprocesamiento de documentos y consultas debe coincidir; reindexar.

  # El prefijo de BGE es de codificación de consulta; NO es un prompt de LLM generativo.

Ubicaciones sugeridas: config.py SELECTED_CONFIG; preprocessing.py TextPreprocessor.process;
embedding_models.py MODEL_SPECS; scripts/construir_indice_semantico.py junto a
faiss.IndexFlatIP(dimension); search_service.py _get_semantic y rank_many;
api.py junto a SearchRequest/top_k; runtime.py inspect_assets.
No agregar comentarios repetitivos en todas las líneas ni dos variantes de código operativo para alternar manualmente. NO modificar el resto del texto del archivo innecesariamente.

FASE C — LIMPIEZA SELECTIVA DE SCRIPTS HISTÓRICOS DE HÍBRIDO
El usuario quiere retirar scripts de experimentos híbridos si se puede sin afectar el sistema. APLICA ESTAS CONDICIONES:
C1. Prioriza investigar scripts/evaluar_hibrido.py (CLI dedicada a combinar rankings TREC) y otros scripts cuyo ÚNICO propósito sea esa fusión.
C2. Antes de borrar, demuestra con búsqueda de referencias que no es importado, ejecutado por pruebas/CI, README, otro script o proceso de despliegue. Inspecciona scripts/experimentar_preprocesamiento.py: NO LO BORRES, pues incluye el experimento de morfología con selección científica basada también en RRF.
C3. MANTÉN src/ri_fiqa/retrieval/fusion.py, SearchService.MODELS, API ModelName y branch híbrida, frontend benchmark y tests mientras sigan siendo parte del contrato/API y de la reproducibilidad.
C4. MANTÉN cualquier resultado histórico results/*hybrid* y evidencia de selección, salvo decisión explícita posterior autorizada; no elimines datos de prueba científicos.
C5. Si el script histórico aislado se puede archivar sin perder scripts de reproducción obligatoria, muévelo a docs/legacy/ o bórralo en commit APARTE, indicando qué método de reproducción se conserva. Si el usuario exigiera «eliminar todo el híbrido», para y explica qué contratos y pruebas habrían de cambiar: no lo hagas en este encargo.
C6. No desinstales dependencias hasta demostrar con herramientas de análisis/imports y tests que nadie las usa. RRF depende casi exclusivamente de librerías estándar, por lo que no presupongas ahorro de dependencias.

FASE D — PRUEBAS / REGRESIÓN (OBLIGATORIAS ANTES DE COMMIT)
- git diff --check
- Python: python -m unittest discover -s tests -v
- Frontend: cd frontend; npm test; npm run benchmark:check; npm run build
- Si hay recursos completos: python scripts/verificar_api.py --url http://127.0.0.1:8000
- Si hay red y permiso: python backend/verify_api.py https://fiqa-api.vercel.app --no-diagnostics --report build/verify-after-comments.json (esto solo consulta API; no despliega)
- Comparar salidas de regresión real para los cuatro modelos ante `What is the difference between APR and APY?`; NO reescribir datos de benchmarks.
- Asegurar compatibilidad API: /health, /ready, /models, /search, /search/compare. Mantener respuestas de híbrido en API histórica.
- No afirmar que todo pasó si falta corpus, índice, pesos o red: reportar qué se ejecutó, qué se omitió y por qué; no hacer commit destructivo si no hay garantía suficiente.

ENTREGABLES DE CODEX
1. AUDITORIA_CODIGO_FIQA.md: matriz exacta, código muerto confirmado vs aparente, dependencias, diffs, resultados de tests.
2. Comentarios breves y estratégicos en archivos apropiados SIN cambiar ninguna instrucción ejecutable.
3. Un plan separado de limpieza: archivos que se conservan, se pueden archivar y eliminaciones bloqueadas.
4. Si el script aislado es demostrablemente removible, cleanup en commit separado y reversible; de lo contrario NO eliminarlo.
5. Resumen final con SHA, archivos modificados, resultados de pruebas, cualquier limitación/no ejecutado, confirmación explícita de que no cambió API/funcionalidad/métricas.

ORDEN OBLIGATORIO DE TRABAJO
Primero AUDITAR, luego SOLO COMENTARIOS, después TESTEAR, y únicamente al final considerar limpieza de scripts sin consumidores. Si no es posible probar cambios, entrega el informe y el diff propuesto, NO supongas que la limpieza es segura.
```

## Comandos iniciales en Codex / terminal

```powershell
git status --short
git switch -c chore/auditoria-defensa-fiqa
git rev-parse HEAD
rg -n -i "hybrid|weighted_rrf|rrf_|fusion" src scripts tests backend frontend docs results README.md
```

**Resultado seguro esperado:** la auditoría y los comentarios no cambian rankings, API ni métricas; los archivos híbridos que aún constituyen contrato o evidencia **no se eliminan automáticamente**. La eliminación literal de todo RRF requeriría un proyecto de cambio de contrato, no una limpieza sin comportamiento nuevo.