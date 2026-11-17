
"""Ejecuta consultas sobre FiQA mediante Jaccard."""

import argparse
from pathlib import Path

from datasets import load_from_disk

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.jaccard import JaccardRetriever


BASE_DIR = Path(__file__).resolve().parents[1]

INDEX_PATH = (
    BASE_DIR / "data" / "processed"
    / "inverted_index_stopwords.json.gz"
)

CORPUS_PATH = BASE_DIR / "data" / "raw" / "corpus"


def main():
    parser = argparse.ArgumentParser(
        description="Búsqueda de documentos FiQA con Jaccard."
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Consulta en lenguaje natural."
    )

    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Cantidad máxima de resultados."
    )

    args = parser.parse_args()

    if not INDEX_PATH.exists():
        parser.error(
            "Índice no encontrado. "
            "Ejecuta primero construir_indice.py"
        )

    # Cargamos el índice ya construido.
    index = InvertedIndex.load(INDEX_PATH)
    retriever = JaccardRetriever(index)

    # Ejecutamos la consulta.
    results = retriever.search(
        args.query,
        top_k=args.top
    )

    print("\n=== BÚSQUEDA JACCARD ===")
    print("Consulta:", args.query)
    print(
        "Tokens:",
        index.preprocessor.process(args.query)
    )
    print(f"Resultados encontrados: {len(results)}")

    if not results:
        print("No se encontraron coincidencias.")
        return

    # Cargar textos únicamente para visualizarlos.
    corpus = load_from_disk(str(CORPUS_PATH))

    posiciones = {
        str(doc_id): posicion
        for posicion, doc_id in enumerate(corpus["_id"])
    }

    for rank, result in enumerate(results, start=1):
        documento = corpus[posiciones[result.doc_id]]

        texto = " ".join(
            (documento["text"] or "").split()
        )

        fragmento = texto[:250]
        if len(texto) > 250:
            fragmento += "..."

        print(f"\n--- RESULTADO {rank} ---")
        print(f"Documento ID: {result.doc_id}")
        print(f"Jaccard: {result.score:.4f}")
        print(f"Texto: {fragmento}")


if __name__ == "__main__":
    main()
