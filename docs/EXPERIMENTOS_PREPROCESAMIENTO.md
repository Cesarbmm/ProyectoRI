# Experimentos independientes de preprocesamiento en FiQA

Se comparan tres configuraciones sobre el corpus completo de 57.638 documentos:
`baseline`, `stemming` y `lemmatization`. Los índices experimentales y las corridas
se guardan separados de los resultados históricos. Las tablas y la selección
congelada están en `results/preprocessing_v1/`.

## Transformaciones y alcance

Las tres variantes comparten exactamente la normalización, tokenización y lista
de stopwords originales. Después del filtrado de stopwords:

- `baseline`: devuelve los tokens originales; sigue siendo el valor por defecto
  de `PreprocessConfig()` y permite cargar los índices antiguos sin migrarlos.
- `stemming`: aplica `nltk.stem.snowball.SnowballStemmer("english")`.
- `lemmatization`: aplica `nltk.stem.WordNetLemmatizer().lemmatize`, con POS nominal
  fijo (`pos="n"`). Es una variante conservadora, sin etiquetador contextual;
  por ejemplo, `banks → bank`, pero `running → running`. No representa todas las
  posibles variantes de lematización con spaCy o con análisis de POS.

Solo se transforman tokens alfabéticos que no pertenecen a `PROTECTED_TERMS`.
Se conservan negaciones y términos protegidos como `us`, `interest`, `will` y
`may`, además de números, decimales, porcentajes y tokens como `401k`. Las siglas
alfabéticas restantes pueden cambiar: por ejemplo, Snowball transforma `apy`
en `api`; es un riesgo de conflación que debe valorarse junto con las métricas.
Un caché acotado evita repetir el análisis de palabras; no usa etiquetas ni
aprende del corpus. Las consultas usan siempre el preprocesador persistido en
su propio índice, igual que los documentos.

Referencias de implementación: [Snowball en NLTK](https://www.nltk.org/api/nltk.stem.snowball.html)
y [WordNetLemmatizer](https://www.nltk.org/api/nltk.stem.wordnet.html).

## Protocolo fijado antes de evaluar

1. Se reconstruye un índice completo por configuración y se evalúan Jaccard,
   TF-IDF y BM25 con las mismas 500 consultas de `validation`, profundidad 1.000
   y las funciones de evaluación existentes. No se eliminan consultas sin
   aciertos ni documentos vacíos del índice léxico.
2. Para **cada configuración**, incluido el baseline, se evalúa la misma rejilla:
   `k1 ∈ {0.8, 1.2, 1.6}`, `b ∈ {0.5, 0.75, 0.9}`. Se maximiza MAP@1000 de BM25;
   los empates favorecen menor `k1` y luego menor `b`.
3. El BM25 óptimo de cada configuración se combina con el mismo BGE usando RRF
   fijo: `k=10`, peso semántico `0.9`, 1.000 candidatos de cada recuperador. No se
   busca otra configuración RRF. Así se mide el efecto del preprocesamiento sin
   confundirlo con otra optimización del híbrido.
4. Se reutilizan los rankings BGE completos ya existentes, leídos por su columna
   de posición. Se exige que tengan exactamente los mismos IDs de consulta,
   1.000 documentos válidos por consulta y que reproduzcan **todas** las métricas
   históricas por consulta. Se comprueba el fingerprint del corpus y se guardan
   los hashes de los rankings, métricas, FAISS, IDs y metadatos. No se ejecutan
   cambios sobre el encoder, prompts, embeddings ni índice FAISS.
5. El criterio global principal es la **media de MAP@1000 de los cuatro modelos
   afectados**: Jaccard, TF-IDF, BM25 e híbrido, con igual peso. Se evita elegir un
   modelo distinto para cada técnica. BGE es constante; incluirlo con igual peso
   cambiaría la escala, pero no el orden de las configuraciones.
6. Para promover una variante se exige incremento global positivo y `p<0.05`
   tras Holm sobre las dos comparaciones frente al baseline. Además, ningún
   modelo puede perder más de un **2% relativo** en ninguna de las cuatro
   métricas: MAP@1000, NDCG@10, MRR@10 y Recall@100. Las pérdidas menores también
   se muestran. Entre las variantes admisibles se elige la de mayor MAP global;
   si ninguna lo cumple, se conserva el baseline.

`protocol.json` se escribe antes de reconstruir los índices y ejecutar las
corridas léxicas. Registra IDs, fingerprints, versión de Python, paquetes,
WordNet, hashes de fuentes y recursos, semilla y reglas. El commit base identifica
el repositorio anterior a los cambios; los hashes de fuentes identifican el
código del experimento que se estaba ejecutando. La integración de servicio y
documentación se completa después.

## Análisis estadístico

La unidad pareada es la consulta, nunca un documento ni una combinación
consulta-modelo tratada como observación independiente. Para el criterio global
se calcula por consulta la media de AP@1000 entre los cuatro modelos.

Se reutiliza `paired_comparison`: 10.000 remuestreos bootstrap de consultas para
el IC95% de la diferencia de medias y 10.000 permutaciones pareadas de signos
para una prueba bilateral, semilla `20261120`. Se informa delta absoluto,
relativo, intervalo, p sin ajustar, p Holm y consultas que mejoran/empeoran.
Los 32 contrastes por modelo y métrica forman una familia Holm secundaria
separada. La comparación directa stemming/lematización es exploratoria.

La optimización de BM25 y estos contrastes comparten `validation`: los intervalos
son condicionales a los hiperparámetros elegidos y no corrigen todo el sesgo de
selección de la rejilla. Por tanto, son evidencia exploratoria, no una prueba
confirmatoria independiente. El repositorio ya contiene evaluaciones históricas
de `test`; este trabajo mantiene esos archivos intactos y no los utiliza como
entrada de la selección nueva.

## Congelación y comprobación final

`selection_frozen.json` contiene una única configuración, los parámetros BM25,
RRF y hashes de los índices y artefactos de validación. Solo después se permite
el comando `final`. Este verifica la integridad de los artefactos, registra el
hash de la selección y abre los qrels de las 648 consultas de `test`.

Se evalúan únicamente los tres modelos léxicos y el híbrido de la configuración
ganadora. BGE se verifica usando su ranking constante. No se prueban las
configuraciones perdedoras en `test` ni se reajustan parámetros. La carpeta final
no puede sobrescribirse ni reutilizarse para repetir esa comprobación. Las
métricas de `test` son descriptivas y no vuelven a alimentar la selección.

## Reproducción (PowerShell)

Usar el entorno y recursos originales descritos en el README:

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
python -m nltk.downloader wordnet
python -m unittest discover -s tests -v
python -m pip check

# Usar una carpeta NUEVA: el experimento no sobrescribe corridas anteriores.
python scripts/experimentar_preprocesamiento.py validation --output results/preprocessing_reproduction

# Revisar selection_frozen.json; a partir de aquí no se ajusta ningún parámetro.
python scripts/experimentar_preprocesamiento.py final --output results/preprocessing_reproduction
python scripts/verificar_experimento_preprocesamiento.py --output results/preprocessing_reproduction --include-final
```

Se requieren los rankings históricos locales
`results/service_bge_validation_top1000.trec` y
`results/service_bge_test_top1000.trec`, además de corpus, consultas, qrels y
`data/processed/semantic_bge/`. Los `.trec`, datos e índices están excluidos de
Git. Si faltan los rankings BGE, pueden transferirse desde la ejecución original
o reconstruirse desde el BGE existente, sin volver a indexar los documentos.
**Solo si falta el archivo correspondiente**, ejecutar:

```powershell
# Antes de validation:
python scripts/regenerar_cache_bge.py validation
# Solo después de congelar la selección y antes de la comprobación final:
python scripts/regenerar_cache_bge.py test --selection results/preprocessing_reproduction/selection_frozen.json
```

El regenerador rechaza archivos existentes y exige reproducir las métricas BGE
históricas por consulta. Si otra combinación de hardware/dependencias altera el
ranking, falla explícitamente: para una reproducción exacta se necesita el
caché original. No reemplaza las métricas históricas ni cambia BGE.

Los índices experimentales se crean bajo
`data/processed/<nombre_de_carpeta_de_resultados>/`. Para reconstruir un índice
de servicio con una configuración explícita:

```powershell
python scripts/construir_indice.py --morphology baseline
python scripts/construir_indice.py --morphology stemming
python scripts/construir_indice.py --morphology lemmatization
```

Cada variante usa su archivo independiente. `--rebuild` solo es necesario para
reemplazar deliberadamente el índice correspondiente. Sin `--morphology`, se
construye/carga la configuración final de `SELECTED_CONFIG`.

## Integración

`RetrievalConfig.morphology` determina el índice léxico y los parámetros BM25
del servicio; el preprocesador se recupera de sus metadatos. Un índice cuya
configuración no coincide con el servicio produce un error accionable.
FastAPI comparte la configuración de `SearchService`; `/models` publica
`lexical_configuration`, y `/ready` usa el archivo de la variante elegida y
publica `lexical_preprocessing`. El contrato de `/search` se mantiene.

Las configuraciones opcionales se pueden usar desde Python mediante
`TextPreprocessor(PreprocessConfig(morphology="stemming"))`, o con una instancia
de `SearchService(config=RetrievalConfig(...))` para un índice compatible.
Cambiar la morfología por sí solo no vuelve a optimizar BM25: los parámetros
congelados de cada variante están en las corridas de validación.

## Resultados obtenidos en validation

Cada fila contiene las mismas 500 consultas; BM25 e híbrido usan el BM25 óptimo
de su propia variante. BGE permanece fijo (MAP@1000 `0.364793`).

| Configuración | Modelo | MAP@1000 | NDCG@10 | MRR@10 | Recall@100 |
|---|---|---:|---:|---:|---:|
| baseline | Jaccard | 0.031967 | 0.040350 | 0.046754 | 0.183571 |
| baseline | TF-IDF | 0.135135 | 0.169452 | 0.205611 | 0.436119 |
| baseline | BM25 | 0.201641 | 0.242940 | 0.300387 | 0.512084 |
| baseline | Híbrido | 0.367619 | 0.428095 | 0.498736 | 0.746710 |
| stemming | Jaccard | 0.036627 | 0.044179 | 0.054581 | 0.193780 |
| stemming | TF-IDF | 0.160702 | 0.194794 | 0.233544 | 0.467618 |
| stemming | BM25 | 0.225097 | 0.268281 | 0.329800 | 0.545169 |
| stemming | Híbrido | 0.366856 | 0.426318 | 0.495902 | 0.750821 |
| lemmatization | Jaccard | 0.032319 | 0.039573 | 0.046954 | 0.194060 |
| lemmatization | TF-IDF | 0.144829 | 0.177643 | 0.212808 | 0.463266 |
| lemmatization | BM25 | 0.218227 | 0.256492 | 0.323317 | 0.526921 |
| lemmatization | Híbrido | 0.366977 | 0.426094 | 0.498097 | 0.751155 |

| Configuración | Mejor k1 | Mejor b | MAP global | Cambio global | IC95% del delta vs baseline | p Holm global |
|---|---:|---:|---:|---:|---|---:|
| baseline | 1.2 | 0.50 | 0.184091 | — | — | — |
| stemming | 0.8 | 0.75 | **0.197320** | **+7.19%** | [0.007031, 0.019717] | **0.000200** |
| lemmatization | 0.8 | 0.75 | 0.190588 | +3.53% | [0.001691, 0.011629] | 0.009999 |

La elección única es **stemming (Snowball)**: ambas variantes superan el criterio
global y cumplen los límites de pérdida, pero Snowball obtiene el mayor MAP
global. En la comparación directa exploratoria, lematización menos stemming
produce delta `−0.006732`, IC95% `[−0.012224, −0.001720]`, p bilateral sin ajuste
`0.011799`. No se confunde este contraste exploratorio con una validación
confirmatoria en datos independientes.

La mejora de Snowball se concentra en TF-IDF y BM25: MAP relativo `+18.92%` y
`+11.63%`, con p Holm secundaria `0.015998` y `0.027897`, respectivamente. Jaccard
mejora `14.58%`, pero su IC95% del delta MAP incluye cero y p Holm es `1.0`.
En la media global por consulta, 256 consultas mejoran, 214 empeoran y 30 quedan
iguales: el aumento de la media no implica mejorar todas las consultas.

**El híbrido no mejora en MAP con ninguna de las dos técnicas.** Snowball pierde
`0.2076%` relativo en MAP, `0.4151%` en NDCG y `0.5683%` en MRR, mientras Recall@100
sube de `0.746710` a `0.750821`. Su delta MAP es `−0.000763`, IC95%
`[−0.003773, 0.002441]`, p bilateral `0.645235` y p Holm secundaria `1.0`.
Estas pérdidas son menores que el límite prefijado del 2%, por lo que no bloquean
la configuración global ganadora. No se afirma equivalencia estadística ni
mejora del híbrido. Si el único objetivo fuera maximizar MAP del híbrido en
validation, el baseline seguiría siendo la mejor de estas tres opciones.

| Índice | Documentos | Vocabulario | Tokens | Postings |
|---|---:|---:|---:|---:|
| baseline | 57,638 | 82,080 | 3,902,367 | 2,925,759 |
| stemming | 57,638 | 61,738 | 3,902,367 | 2,766,580 |
| lemmatization | 57,638 | 75,640 | 3,902,367 | 2,847,435 |

Snowball reduce el vocabulario aproximadamente un 24.78%, frente al 7.85% de
WordNet. El número de tokens se conserva: cambia la equivalencia entre formas,
no el filtrado. Es coherente con que Snowball permita más coincidencias léxicas
y aumente Recall@100 en los tres recuperadores léxicos. La fusión dominada por
BGE puede reordenar documentos relevantes de forma desfavorable pese a esa
mejora léxica. Esta interpretación explica los resultados observados; no demuestra
que cada conflación particular sea beneficiosa.

Se conserva el baseline como configuración opcional y como índice histórico. La
configuración de servicio final es `morphology="stemming"`, `k1=0.8`, `b=0.75`;
RRF sigue con `k=10`, peso BGE `0.9`. Los resultados completos, con precisión sin
redondear, parámetros y métricas por consulta, están en
[`results/preprocessing_v1`](../results/preprocessing_v1/).

## Comprobación final en test

La selección se congeló antes de abrir los qrels de test. Se ejecutó una única
comprobación de Snowball sobre las 648 consultas, conservando `k1=0.8`, `b=0.75`
y RRF fijo. No se evaluaron las variantes descartadas ni se reajustó nada.

| Modelo con Snowball | MAP@1000 | NDCG@10 | MRR@10 | Recall@100 |
|---|---:|---:|---:|---:|
| Jaccard | 0.038587 | 0.048740 | 0.068289 | 0.202817 |
| TF-IDF | 0.141153 | 0.173773 | 0.216036 | 0.491186 |
| BM25 | 0.210294 | 0.254969 | 0.315262 | 0.545683 |
| Híbrido | 0.349604 | 0.408076 | 0.485991 | 0.743390 |

Estos valores son descriptivos. El híbrido queda ligeramente por debajo de su
MAP histórico (`0.350006`), mientras los tres modelos léxicos superan sus MAP
históricos. Esto no cambia la elección global ya congelada. BGE conserva su MAP
`0.347148`; sus hashes permanecen idénticos. Las métricas por consulta y el
registro de integridad están en
[`final_test`](../results/preprocessing_v1/final_test/).

## Verificación realizada

- `python -m unittest discover -s tests`: **104 pruebas correctas**; incluye
  configuración persistida, carga de índices antiguos, simetría consulta-documento,
  protección de términos, selección/estadística, aislamiento de splits, integridad
  de la congelación y API. BGE y el híbrido reciben siempre la consulta original.
- `python -m pip check`: sin dependencias rotas. Se añadió NLTK 3.9.2 al manifiesto
  y al lock existente, y se declararon las dependencias de API/pruebas HTTP.
- `python -m compileall -q src scripts/experimentar_preprocesamiento.py scripts/regenerar_cache_bge.py scripts/verificar_experimento_preprocesamiento.py`:
  correcto.
- El evaluador histórico rechaza explícitamente sobrescribir sus resultados de
  validation o test. Las nuevas corridas utilizan exclusivamente su propia carpeta.
- `python scripts/verificar_experimento_preprocesamiento.py --include-final`:
  **40 corridas**, **82.368 valores de métricas por consulta** contrastados con
  `ir-measures` (36 corridas de validation y 4 de test); diferencia máxima **0**.
  El detalle está en `results/preprocessing_v1/verification_with_final.json`.
- `python scripts/verificar_api.py --url http://127.0.0.1:8011` contra Uvicorn
  con los recursos reales y la configuración Snowball: correctos `/health`,
  `/ready`, `/models`, búsquedas de los cinco modelos, `/search/compare`, HTTP 422
  y CORS. El primer resultado BGE de la consulta de regresión se conserva.
- Los hashes SHA-256 de FAISS, IDs y metadatos BGE se comprobaron antes y después
  del experimento; no cambió ningún resultado histórico versionado.
