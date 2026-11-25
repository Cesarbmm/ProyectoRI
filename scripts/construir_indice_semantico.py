
"""Genera embeddings FiQA y construye un índice FAISS."""

import argparse
import json
import os

from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import faiss
import numpy as np
import torch

from datasets import load_from_disk
from sentence_transformers import SentenceTransformer

from ri_fiqa.embedding_models import (
    MODEL_SPECS,
    configure_encoder,
)


BASE_DIR = Path(__file__).resolve().parents[1]

CORPUS_PATH = BASE_DIR / "data" / "raw" / "corpus"

PROCESSED_DIR = BASE_DIR / "data" / "processed"

# MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def main():
    parser = argparse.ArgumentParser(
        description="Construye el índice vectorial FiQA."
    )

    parser.add_argument(
        "--name", default="semantic_minilm"
    )

    parser.add_argument(
        "--batch-size", type=int, default=32
    )

    parser.add_argument(
        "--limit", type=int, default=None,
        help="Cantidad inicial de documentos para pruebas."
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto"
    )

    parser.add_argument(
        "--force", action="store_true",
        help="Permite reemplazar un índice existente."
    )

    parser.add_argument(
        "--encoder",
        choices=MODEL_SPECS,
        default="minilm",
        help="Modelo de embeddings utilizado."
    )

    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("batch-size debe ser positivo.")

    if args.limit is not None and args.limit <= 0:
        parser.error("limit debe ser positivo.")

    if not args.name.replace("_", "").isalnum():
        parser.error("name solo admite letras, números y _.")

    output_dir = PROCESSED_DIR / args.name

    index_path = output_dir / "index.faiss"
    ids_path = output_dir / "doc_ids.json"
    metadata_path = output_dir / "metadata.json"

    if any(
        p.exists()
        for p in (index_path, ids_path, metadata_path)
    ) and not args.force:
        parser.error(
            "Ya existe un índice con ese nombre. "
            "Usa otro --name o especifica --force."
        )

    if args.device == "auto":
        device = (
            "cuda" if torch.cuda.is_available()
            else "cpu"
        )
    else:
        device = args.device

    if device == "cuda" and not torch.cuda.is_available():
        parser.error(
            "CUDA no está disponible en PyTorch."
        )

    print("[1/4] Cargando corpus y encoder...")

    corpus = load_from_disk(str(CORPUS_PATH))

    spec = MODEL_SPECS[args.encoder]

    model = SentenceTransformer(
        spec.model_id,
        device=device,
    )

    encoder = configure_encoder(
        model,
        query_prompt=spec.query_prompt,
        document_prompt=spec.document_prompt,
    )

    dimension = model.get_sentence_embedding_dimension()

    if dimension is None:
        raise RuntimeError(
            "No se pudo obtener la dimensión del encoder."
        )

    print("Modelo:", spec.model_id)
    print("Dispositivo:", device)
    print("Dimensión:", dimension)
    print("Máximo tokens:", model.max_seq_length)

    total = (
        min(args.limit, len(corpus))
        if args.limit is not None
        else len(corpus)
    )

    # Búsqueda exacta por producto interno.
    # Posible mejora (NO ACTIVA): comparar HNSW/IVF/PQ con el FlatIP exacto.
    # Requiere reindexar, ajustar entrenamiento/parámetros y medir recall/latencia.
    # Cambiar el constructor sin actualizar metadata y /ready rompería el runtime.
    vector_index = faiss.IndexFlatIP(dimension)

    doc_ids = []
    empty_documents = 0

    print("[2/4] Generando embeddings...")

    started = perf_counter()

    for start in range(0, total, args.batch_size):
        end = min(start + args.batch_size, total)

        # Los datasets permiten recuperar columnas
        # mediante slicing sin convertir todo a una lista.
        batch = corpus[start:end]

        valid_ids = []
        valid_texts = []

        for doc_id, text in zip(
            batch["_id"], batch["text"]
        ):
            text = (text or "").strip()

            if not text:
                empty_documents += 1
                continue

            valid_ids.append(str(doc_id))
            valid_texts.append(text)

        if valid_texts:
            embeddings = encoder.encode_document(
                valid_texts,
                batch_size=args.batch_size,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

            vectors = np.ascontiguousarray(
                embeddings, dtype=np.float32
            )

            if (
                vectors.ndim != 2
                or vectors.shape[1] != dimension
            ):
                raise RuntimeError(
                    "Dimensiones de embeddings incorrectas."
                )

            faiss.normalize_L2(vectors)

            vector_index.add(vectors)
            doc_ids.extend(valid_ids)

        if end % 2000 < args.batch_size or end == total:
            print(f"    Procesados {end:,}/{total:,}")

    elapsed = perf_counter() - started

    print("[3/4] Verificando índice...")

    if vector_index.ntotal != len(doc_ids):
        raise RuntimeError(
            "Inconsistencia entre vectores e IDs."
        )

    if len(doc_ids) != len(set(doc_ids)):
        raise RuntimeError(
            "Se encontraron IDs duplicados."
        )

    print("Documentos procesados:", total)
    print("Embeddings generados:", vector_index.ntotal)
    print("Documentos vacíos:", empty_documents)
    print(f"Tiempo de generación: {elapsed:.2f} s")

    print("[4/4] Guardando índice y metadatos...")

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "dataset": "BeIR/fiqa",
        "corpus_fingerprint": corpus._fingerprint,
        "model_id": spec.model_id,
        "encoder_profile": args.encoder,
        "query_prompt": spec.query_prompt,
        "document_prompt": spec.document_prompt,
        "device_used": device,
        "dimension": dimension,
        "max_seq_length": model.max_seq_length,
        "normalization": "L2",
        "similarity": "cosine",
        "faiss_index": "IndexFlatIP",
        "original_corpus_size": len(corpus),
        "processed_documents": total,
        "indexed_documents": len(doc_ids),
        "excluded_empty_documents": empty_documents,
        "batch_size": args.batch_size,
        "embedding_seconds": elapsed,
        "torch_version": version("torch"),
        "sentence_transformers_version": version(
            "sentence-transformers"
        ),
        "faiss_version": version("faiss-cpu"),
    }

    temp_index = output_dir / "index.faiss.tmp"
    faiss.write_index(vector_index, str(temp_index))
    os.replace(temp_index, index_path)

    for path, content in (
        (ids_path, doc_ids),
        (metadata_path, metadata),
    ):
        temporary = path.with_name(
            path.name + ".tmp"
        )

        with temporary.open(
            "w", encoding="utf-8"
        ) as file:
            json.dump(
                content, file,
                indent=2, ensure_ascii=False
            )

        os.replace(temporary, path)

    print("\n[OK] Índice guardado en:", output_dir)


if __name__ == "__main__":
    main()
