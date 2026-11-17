
from pathlib import Path
from datasets import load_dataset, load_from_disk

# Directorio raíz del proyecto.
BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw"


def cargar_o_descargar(nombre, repositorio, config=None, split=None):
    """Obtiene un dataset desde disco o Hugging Face."""
    destino = RAW_DIR / nombre

    if destino.exists():
        print(f"[LOCAL] Cargando {nombre}")
        return load_from_disk(str(destino))

    print(f"[DESCARGA] Obteniendo {nombre}")

    opciones = {}
    if config is not None:
        opciones["name"] = config
    if split is not None:
        opciones["split"] = split

    dataset = load_dataset(repositorio, **opciones)
    dataset.save_to_disk(str(destino))

    print(f"[OK] Guardado en {destino}")
    return dataset


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Corpus: documentos que serán indexados.
    corpus = cargar_o_descargar(
        "corpus", "BeIR/fiqa",
        config="corpus", split="corpus"
    )

    # Queries: consultas asociadas al benchmark.
    queries = cargar_o_descargar(
        "queries", "BeIR/fiqa",
        config="queries", split="queries"
    )

    # Qrels: juicios de relevancia.
    qrels = cargar_o_descargar(
        "qrels", "BeIR/fiqa-qrels"
    )

    print("\n=== RESUMEN DE FIQA ===")
    print(f"Documentos: {len(corpus):,}")
    print(f"Consultas:  {len(queries):,}")

    for split in ("train", "validation", "test"):
        print(f"Qrels {split}: {len(qrels[split]):,}")

    print("\n=== COLUMNAS ===")
    print("Corpus:", corpus.column_names)
    print("Queries:", queries.column_names)
    print("Qrels:", qrels["test"].column_names)

    # Los identificadores de documentos y consultas deben
    # coincidir con las referencias presentes en qrels.
    doc_ids = set(corpus["_id"])
    query_ids = set(queries["_id"])

    print("\n=== INTEGRIDAD REFERENCIAL ===")
    for split in ("train", "validation", "test"):
        registros = qrels[split]

        docs_invalidos = sum(
            str(fila["corpus-id"]) not in doc_ids
            for fila in registros
        )
        queries_invalidas = sum(
            str(fila["query-id"]) not in query_ids
            for fila in registros
        )

        print(
            f"{split}: documentos inexistentes={docs_invalidos}, "
            f"consultas inexistentes={queries_invalidas}"
        )

    print("\n=== EJEMPLOS ===")
    doc = corpus[0]
    print("Documento ID:", doc["_id"])
    print("Texto:", doc["text"][:200])

    query = queries[0]
    print("\nConsulta ID:", query["_id"])
    print("Consulta:", query["text"])

    print("\nDatos preparados correctamente.")


if __name__ == "__main__":
    main()
