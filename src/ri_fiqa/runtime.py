
"""Comprobación estructural de los recursos del motor FiQA."""

import json
from pathlib import Path

from ri_fiqa.config import SELECTED_CONFIG, RetrievalConfig
from ri_fiqa.embedding_models import MODEL_SPECS


def inspect_assets(
    project_root: Path,
    semantic_index: str = SELECTED_CONFIG.semantic_index,
    config: RetrievalConfig = SELECTED_CONFIG,
) -> dict:
    """Comprueba recursos sin cargar PyTorch, datasets ni FAISS."""

    root = Path(project_root)

    semantic_dir = (
        root / "data" / "processed" / semantic_index
    )

    paths = {
        "corpus": root / "data" / "raw" / "corpus",
        "inverted_index": (
            root / "data" / "processed"
            / config.lexical_index
        ),
        "faiss_index": semantic_dir / "index.faiss",
        "document_ids": semantic_dir / "doc_ids.json",
        "semantic_metadata": semantic_dir / "metadata.json",
    }

    components = {}

    for name, path in paths.items():
        if name == "corpus":
            components[name] = path.is_dir()
        else:
            components[name] = (
                path.is_file() and path.stat().st_size > 0
            )

    # Nota de defensa: /ready exige BGE, 768 D, normalización L2 e IndexFlatIP.
    # Otro índice o encoder requeriría regenerar artefactos y actualizar esta validación.
    components["metadata_consistent"] = False

    if components["semantic_metadata"]:
        try:
            with paths["semantic_metadata"].open(
                encoding="utf-8"
            ) as file:
                metadata = json.load(file)

            original = metadata["original_corpus_size"]
            processed = metadata["processed_documents"]
            indexed = metadata["indexed_documents"]
            empty = metadata["excluded_empty_documents"]

            expected = MODEL_SPECS["bge"]

            components["metadata_consistent"] = all([
                isinstance(original, int) and original > 0,
                isinstance(processed, int),
                isinstance(indexed, int) and indexed > 0,
                isinstance(empty, int) and empty >= 0,
                processed == original,
                indexed + empty == processed,
                metadata.get("model_id") == expected.model_id,
                metadata.get("query_prompt")
                    == expected.query_prompt,
                metadata.get("document_prompt")
                    == expected.document_prompt,
                metadata.get("dimension") == 768,
                metadata.get("normalization") == "L2",
                metadata.get("faiss_index") == "IndexFlatIP",
            ])

        except (OSError, ValueError, KeyError, TypeError):
            components["metadata_consistent"] = False

    is_ready = all(components.values())

    return {
        "status": "ready" if is_ready else "not_ready",
        "semantic_index": semantic_index,
        "lexical_preprocessing": config.morphology,
        "components": components,
    }
