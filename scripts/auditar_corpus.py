
from pathlib import Path
from collections import Counter
from datasets import load_from_disk
import hashlib
import json

# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "raw"
RESULTS_DIR = BASE_DIR / "results"

SPLITS = ("train", "validation", "test")


def estadisticas(valores):
    """Calcula estadísticas descriptivas y percentiles."""
    if not valores:
        return {}

    datos = sorted(valores)
    n = len(datos)

    def percentil(p):
        posicion = (n - 1) * p / 100
        inferior = int(posicion)
        superior = min(inferior + 1, n - 1)
        fraccion = posicion - inferior

        valor = datos[inferior] + fraccion * (
            datos[superior] - datos[inferior]
        )
        return round(valor, 2)

    return {
        "minimo": datos[0],
        "promedio": round(sum(datos) / n, 2),
        "mediana_p50": percentil(50),
        "p90": percentil(90),
        "p99": percentil(99),
        "maximo": datos[-1],
    }


def auditar_textos(dataset):
    """Analiza documentos o consultas sin modificarlos."""
    ids = set()
    ids_duplicados = 0
    textos_vacios = 0
    titulos_vacios = 0

    longitudes = []
    longitudes_por_id = []
    huellas = Counter()

    for fila in dataset:
        identificador = str(fila["_id"])
        texto = (fila["text"] or "").strip()
        titulo = (fila.get("title") or "").strip()

        if identificador in ids:
            ids_duplicados += 1
        ids.add(identificador)

        if not texto:
            textos_vacios += 1
        else:
            huella = hashlib.sha256(
                texto.encode("utf-8")
            ).hexdigest()
            huellas[huella] += 1

        if not titulo:
            titulos_vacios += 1

        # Medición aproximada por espacios.
        # Todavía NO estamos tokenizando para el índice.
        cantidad_palabras = len(texto.split())
        longitudes.append(cantidad_palabras)
        longitudes_por_id.append(
            (cantidad_palabras, identificador)
        )

    textos_duplicados = sum(
        cantidad - 1
        for cantidad in huellas.values()
        if cantidad > 1
    )

    mas_largos = sorted(
        longitudes_por_id, reverse=True
    )[:5]

    return {
        "total": len(dataset),
        "ids_duplicados": ids_duplicados,
        "textos_vacios": textos_vacios,
        "titulos_vacios": titulos_vacios,
        "textos_duplicados": textos_duplicados,
        "longitud_palabras": estadisticas(longitudes),
        "cinco_mas_largos": [
            {"id": doc_id, "palabras": longitud}
            for longitud, doc_id in mas_largos
        ],
    }


def auditar_qrels(dataset):
    """Analiza los juicios de relevancia por consulta."""
    relaciones = Counter()
    relevantes = Counter()
    puntuaciones = Counter()

    pares_vistos = set()
    pares_duplicados = 0

    for fila in dataset:
        query_id = str(fila["query-id"])
        doc_id = str(fila["corpus-id"])
        score = int(fila["score"])

        par = (query_id, doc_id)
        if par in pares_vistos:
            pares_duplicados += 1
        pares_vistos.add(par)

        relaciones[query_id] += 1
        puntuaciones[score] += 1

        if score > 0:
            relevantes[query_id] += 1

    cantidades_relevantes = [
        relevantes.get(query_id, 0)
        for query_id in relaciones
    ]

    return {
        "total_relaciones": len(dataset),
        "consultas_con_qrels": len(relaciones),
        "consultas_con_relevantes": len(relevantes),
        "consultas_sin_relevantes": (
            len(relaciones) - len(relevantes)
        ),
        "pares_duplicados": pares_duplicados,
        "distribucion_scores": dict(puntuaciones),
        "relevantes_por_consulta": estadisticas(
            cantidades_relevantes
        ),
    }


def main():
    print("=== AUDITORÍA DEL CORPUS FIQA ===")

    corpus = load_from_disk(str(DATA_DIR / "corpus"))
    queries = load_from_disk(str(DATA_DIR / "queries"))
    qrels = load_from_disk(str(DATA_DIR / "qrels"))

    reporte = {
        "corpus": auditar_textos(corpus),
        "queries": auditar_textos(queries),
        "qrels": {},
    }

    for split in SPLITS:
        reporte["qrels"][split] = auditar_qrels(
            qrels[split]
        )

    print("\n--- CORPUS ---")
    datos = reporte["corpus"]

    print(f"Documentos: {datos['total']:,}")
    print(f"IDs duplicados: {datos['ids_duplicados']}")
    print(f"Textos vacíos: {datos['textos_vacios']}")
    print(f"Títulos vacíos: {datos['titulos_vacios']}")
    print(f"Textos repetidos: {datos['textos_duplicados']}")
    print("Longitudes:", datos["longitud_palabras"])
    print("Documentos más largos:", datos["cinco_mas_largos"])

    print("\n--- CONSULTAS ---")
    datos = reporte["queries"]

    print(f"Consultas: {datos['total']:,}")
    print(f"IDs duplicados: {datos['ids_duplicados']}")
    print(f"Textos vacíos: {datos['textos_vacios']}")
    print(f"Consultas repetidas: {datos['textos_duplicados']}")
    print("Longitudes:", datos["longitud_palabras"])

    print("\n--- QRELS ---")
    for split, datos in reporte["qrels"].items():
        print(f"\n{split.upper()}")
        print(f"Relaciones: {datos['total_relaciones']}")
        print(f"Consultas evaluables: {datos['consultas_con_qrels']}")
        print(f"Pares duplicados: {datos['pares_duplicados']}")
        print(f"Scores: {datos['distribucion_scores']}")
        print(
            "Relevantes por consulta:",
            datos["relevantes_por_consulta"]
        )

    # Persistir resultados para futuras decisiones.
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    destino = RESULTS_DIR / "auditoria_fiqa.json"

    with destino.open("w", encoding="utf-8") as archivo:
        json.dump(
            reporte, archivo,
            indent=2, ensure_ascii=False
        )

    print(f"\n[OK] Auditoría guardada en: {destino}")

    ##

    ids_vacios = {
        str(doc["_id"])
        for doc in corpus
        if not (doc["text"] or "").strip()
    }   

    print("\n--- DOCUMENTOS VACÍOS EN QRELS ---")
    
    for split in SPLITS:
        afectados = [
            fila for fila in qrels[split]
            if str(fila["corpus-id"]) in ids_vacios
            and fila["score"] > 0
        ]
    
        print(
            f"{split}: {len(afectados)} relaciones relevantes "
            "referencian documentos vacíos"
        )


if __name__ == "__main__":
    main()
