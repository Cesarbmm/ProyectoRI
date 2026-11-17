
"""Índice invertido con frecuencias de términos para RI."""

import gzip
import json
import os

from collections import Counter
from dataclasses import asdict
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from ri_fiqa.preprocessing import (
    PreprocessConfig,
    TextPreprocessor,
)


class InvertedIndex:
    """Construye y almacena un índice invertido propio."""

    FORMAT_VERSION = 2

    def __init__(
        self,
        preprocessor: TextPreprocessor | None = None
    ):
        self.preprocessor = preprocessor or TextPreprocessor()

        # término -> {documento: frecuencia}
        self.postings: dict[str, dict[str, int]] = {}

        # documento -> cantidad de tokens procesados
        self.doc_lengths: dict[str, int] = {}

        # documento -> cantidad de terminos unicos
        self.doc_unique_terms: dict[str, int] = {}

        self.total_tokens = 0
        self.total_postings = 0

    def add_document(
        self,
        doc_id: str,
        text: str | None
    ) -> None:
        """Indexa un documento preservando su ID original."""

        doc_id = str(doc_id)

        if doc_id in self.doc_lengths:
            raise ValueError(
                f"ID de documento duplicado: {doc_id}"
            )

        # Usamos el preprocesador ya validado.
        tokens = self.preprocessor.process(text)

        # Contamos TF una sola vez por documento.
        frecuencias = Counter(tokens)
        self.doc_unique_terms[doc_id] = len(frecuencias)
        self.doc_lengths[doc_id] = len(tokens)
        self.total_tokens += len(tokens)
        self.total_postings += len(frecuencias)

        # Construcción de las listas de postings.
        for termino, frecuencia in frecuencias.items():
            self.postings.setdefault(termino, {})[
                doc_id
            ] = frecuencia

    def build(
        self,
        documents: Iterable[Mapping]
    ) -> None:
        """Indexa una colección de documentos."""
        for document in documents:
            self.add_document(
                document["_id"],
                document.get("text")
            )

    @property
    def num_documents(self) -> int:
        return len(self.doc_lengths)

    @property
    def vocabulary_size(self) -> int:
        return len(self.postings)

    @property
    def average_document_length(self) -> float:
        if self.num_documents == 0:
            return 0.0

        return self.total_tokens / self.num_documents

    def get_postings(
        self,
        term: str
    ) -> Mapping[str, int]:
        """Retorna los postings sin permitir modificarlos."""
        return MappingProxyType(
            self.postings.get(term, {})
        )

    def document_frequency(self, term: str) -> int:
        """Número de documentos que contienen el término."""
        return len(self.postings.get(term, {}))

    def term_frequency(
        self,
        term: str,
        doc_id: str
    ) -> int:
        """Frecuencia del término en un documento."""
        return self.postings.get(term, {}).get(
            str(doc_id), 0
        )

    def save(self, file_path: str | Path) -> None:
        """Persiste el índice como JSON comprimido."""

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        temporal = path.with_name(path.name + ".tmp")

        payload = {
            "format_version": self.FORMAT_VERSION,
            "preprocess_config": asdict(
                self.preprocessor.config
            ),
            "postings": self.postings,
            "doc_lengths": self.doc_lengths,
            "total_tokens": self.total_tokens,
            "total_postings": self.total_postings,
            "doc_unique_terms": self.doc_unique_terms,
        }

        # Escritura temporal para evitar reemplazar
        # un índice válido por uno incompleto.
        try:
            with gzip.open(
                temporal,
                "wt",
                encoding="utf-8",
                compresslevel=3
            ) as archivo:
                json.dump(
                    payload,
                    archivo,
                    ensure_ascii=False
                )

            os.replace(temporal, path)

        finally:
            if temporal.exists():
                temporal.unlink()

    @classmethod
    def load(
        cls,
        file_path: str | Path
    ) -> "InvertedIndex":
        """Carga el índice y su configuración original."""

        with gzip.open(
            file_path,
            "rt",
            encoding="utf-8"
        ) as archivo:
            payload = json.load(archivo)

        if (
            payload.get("format_version")
            != cls.FORMAT_VERSION
        ):
            raise ValueError(
                "Formato incompatible. Reconstruye el índice."
            )

        config = PreprocessConfig(
            **payload["preprocess_config"]
        )

        index = cls(TextPreprocessor(config))

        index.postings = payload["postings"]
        index.doc_lengths = payload["doc_lengths"]
        index.total_tokens = payload["total_tokens"]
        index.total_postings = payload["total_postings"]
        index.doc_unique_terms = payload["doc_unique_terms"]

        return index
