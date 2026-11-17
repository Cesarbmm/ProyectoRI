
"""Construcción y verificación del índice invertido."""

import argparse
from pathlib import Path
from time import perf_counter

from datasets import load_from_disk

from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.preprocessing import (
    PreprocessConfig,
    TextPreprocessor,
)


BASE_DIR = Path(__file__).resolve().parents[1]

CORPUS_PATH = BASE_DIR / "data" / "raw" / "corpus"

INDEX_PATH = (
    BASE_DIR / "data" / "processed"
    / "inverted_index_stopwords.json.gz"
)


def construir_indice():
    print("[1/3] Cargando corpus FiQA...")

    corpus = load_from_disk(str(CORPUS_PATH))

    preprocessor = TextPreprocessor(
        PreprocessConfig(remove_stopwords=True)
    )

    index = InvertedIndex(preprocessor)

    print("[2/3] Construyendo índice invertido...")

    inicio = perf_counter()
    total = len(corpus)

    for numero, documento in enumerate(corpus, start=1):
        index.add_document(
            documento["_id"],
            documento["text"]
        )

        if numero % 10000 == 0 or numero == total:
            print(
                f"    Procesados {numero:,}/{total:,}"
            )

    tiempo = perf_counter() - inicio

    print("[3/3] Guardando índice comprimido...")
    index.save(INDEX_PATH)

    print(f"\nTiempo de construcción: {tiempo:.2f} s")
    print(f"Archivo: {INDEX_PATH}")

    return index


def mostrar_estadisticas(index):
    print("\n=== ESTADÍSTICAS DEL ÍNDICE ===")

    print(f"Documentos: {index.num_documents:,}")
    print(f"Vocabulario: {index.vocabulary_size:,}")
    print(f"Tokens totales: {index.total_tokens:,}")
    print(f"Postings: {index.total_postings:,}")

    print(
        "Longitud promedio procesada:",
        f"{index.average_document_length:.2f}"
    )

    sin_tokens = sum(
        longitud == 0
        for longitud in index.doc_lengths.values()
    )

    print(f"Documentos sin tokens: {sin_tokens:,}")


def inspeccionar_termino(index, texto):
    tokens = index.preprocessor.process(texto)

    if len(tokens) != 1:
        print(
            "\nIntroduce un término que produzca "
            "exactamente un token."
        )
        return

    termino = tokens[0]
    postings = index.get_postings(termino)

    print(f"\n=== TÉRMINO: {termino} ===")
    print(f"DF: {index.document_frequency(termino):,}")

    # Muestra de postings, NO es un ranking de búsqueda.
    muestra = sorted(
        postings.items(),
        key=lambda item: (-item[1], item[0])
    )[:5]

    for doc_id, frecuencia in muestra:
        print(f"Documento {doc_id}: TF={frecuencia}")


def main():
    parser = argparse.ArgumentParser(
        description="Construye e inspecciona el índice FiQA."
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Reconstruye el índice desde el corpus."
    )

    parser.add_argument(
        "--term",
        default="bank",
        help="Término que se desea inspeccionar."
    )

    args = parser.parse_args()

    if INDEX_PATH.exists() and not args.rebuild:
        print("[LOCAL] Cargando índice existente...")
        index = InvertedIndex.load(INDEX_PATH)
    else:
        index = construir_indice()

    mostrar_estadisticas(index)
    inspeccionar_termino(index, args.term)


if __name__ == "__main__":
    main()
