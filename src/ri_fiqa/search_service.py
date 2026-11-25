
"""Servicio unificado de recuperación de información."""

import json

from dataclasses import dataclass
from pathlib import Path

from datasets import load_from_disk

from ri_fiqa.config import SELECTED_CONFIG, RetrievalConfig
from ri_fiqa.preprocessing import PreprocessConfig
from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.retrieval.common import SearchResult
from ri_fiqa.retrieval.jaccard import JaccardRetriever
from ri_fiqa.retrieval.tfidf import TfidfRetriever
from ri_fiqa.retrieval.bm25 import (
    BM25Config,
    BM25Retriever,
)
from ri_fiqa.retrieval.fusion import weighted_rrf


@dataclass(frozen=True, slots=True)
class SearchHit:
    """Documento recuperado con información para mostrar."""

    rank: int
    doc_id: str
    score: float
    text: str
    preview: str


class SearchService:
    """Interfaz única de acceso a los recuperadores."""

    MODELS = ("jaccard", "tfidf", "bm25", "bge", "hybrid")

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        inverted_index=None,
        semantic_retriever=None,
        document_texts=None,
        device: str = "auto",
        config: RetrievalConfig = SELECTED_CONFIG,
    ):
        if device not in ("auto", "cpu", "cuda"):
            raise ValueError("Dispositivo no válido.")

        self.root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )

        self.config = config
        self.device = device

        # Cachés: se cargan cuando son necesarias.
        self._inverted_index = inverted_index
        self._lexical_models = {}
        self._semantic_retriever = semantic_retriever
        self._document_texts = document_texts

    def _get_index(self):
        """Carga el índice invertido una sola vez."""

        if self._inverted_index is None:
            path = (
                self.root / "data" / "processed"
                / self.config.lexical_index
            )

            if not path.is_file():
                raise FileNotFoundError(
                    f"Índice invertido no encontrado: {path}"
                )

            self._inverted_index = InvertedIndex.load(path)

        if self._inverted_index.preprocessor.config != PreprocessConfig(
            morphology=self.config.morphology
        ):
            raise RuntimeError("El preprocesamiento del índice no coincide con el servicio.")
        return self._inverted_index

    def _get_lexical(self, model: str):
        """Obtiene el modelo léxico solicitado."""

        if model not in ("jaccard", "tfidf", "bm25"):
            raise ValueError("Modelo léxico desconocido.")

        if model not in self._lexical_models:
            index = self._get_index()

            if model == "jaccard":
                retriever = JaccardRetriever(index)

            elif model == "tfidf":
                retriever = TfidfRetriever(index)

            else:
                retriever = BM25Retriever(
                    index,
                    BM25Config(
                        k1=self.config.bm25_k1,
                        b=self.config.bm25_b,
                    ),
                )

            self._lexical_models[model] = retriever

        return self._lexical_models[model]

    def _get_semantic(self):
        """Carga BGE y FAISS solo cuando se necesitan."""

        if self._semantic_retriever is not None:
            return self._semantic_retriever

        # Importaciones diferidas para modelos neuronales.
        import faiss
        import torch

        from sentence_transformers import SentenceTransformer
        from ri_fiqa.embedding_models import configure_encoder
        from ri_fiqa.retrieval.semantic import SemanticRetriever

        folder = (
            self.root / "data" / "processed"
            / self.config.semantic_index
        )

        metadata_path = folder / "metadata.json"
        ids_path = folder / "doc_ids.json"
        index_path = folder / "index.faiss"

        for path in (metadata_path, ids_path, index_path):
            if not path.is_file():
                raise FileNotFoundError(
                    f"Recurso semántico no encontrado: {path}"
                )

        with metadata_path.open(
            encoding="utf-8"
        ) as file:
            metadata = json.load(file)

        # Impedir el uso accidental de un índice piloto.
        if (
            metadata["processed_documents"]
            != metadata["original_corpus_size"]
        ):
            raise ValueError(
                "El índice semántico está incompleto."
            )

        with ids_path.open(encoding="utf-8") as file:
            doc_ids = json.load(file)

        # Nota de defensa: el encoder y FAISS deben provenir del mismo build.
        # No intercambiar índice MiniLM/BGE: pueden cambiar dimensión y scores.
        faiss_index = faiss.read_index(str(index_path))

        if (
            faiss_index.ntotal
            != metadata["indexed_documents"]
        ):
            raise ValueError(
                "Los vectores no coinciden con los metadatos."
            )

        if self.device == "auto":
            device = (
                "cuda" if torch.cuda.is_available()
                else "cpu"
            )
        else:
            device = self.device

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA no está disponible.")

        model = SentenceTransformer(
            metadata["model_id"],
            device=device,
        )

        if model.get_embedding_dimension() != faiss_index.d:
            raise ValueError(
                "Dimensiones incompatibles del encoder."
            )

        encoder = configure_encoder(
            model,
            query_prompt=metadata.get("query_prompt"),
            document_prompt=metadata.get("document_prompt"),
        )

        self._semantic_retriever = SemanticRetriever(
            encoder,
            faiss_index,
            doc_ids,
        )

        return self._semantic_retriever

    def _get_document_texts(self):
        """Acceso a textos originales mediante sus IDs."""

        if self._document_texts is None:
            corpus_path = (
                self.root / "data" / "raw" / "corpus"
            )

            corpus = load_from_disk(str(corpus_path))

            self._document_texts = {
                str(row["_id"]): row["text"] or ""
                for row in corpus
            }

        return self._document_texts

    def search(
        self,
        query: str,
        model: str = "bge",
        top_k: int = 5,
    ) -> list[SearchHit]:
        """Ejecuta una búsqueda y devuelve resultados comunes."""

        if model not in self.MODELS:
            raise ValueError(
                f"Modelo desconocido: {model}. "
                f"Opciones: {', '.join(self.MODELS)}"
            )

        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                "La consulta debe contener texto."
            )

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 1 <= top_k <= self.config.candidate_depth
        ):
            raise ValueError(
                "top_k debe estar entre 1 y 1000."
            )

        if model in ("jaccard", "tfidf", "bm25"):
            results = self._get_lexical(model).search(
                query,
                top_k=top_k,
            )

        elif model == "bge":
            results = self._get_semantic().search(
                query,
                top_k=top_k,
            )

        else:
            results = self.rank_many(
                [query],
                model=model,
                top_k=top_k,
            )[0]

        documents = self._get_document_texts()

        hits = []

        for rank, result in enumerate(results, start=1):
            if result.doc_id not in documents:
                raise ValueError(
                    f"Documento inexistente: {result.doc_id}"
                )

            text = documents[result.doc_id]
            clean = " ".join(text.split())

            preview = clean[:280]

            if len(clean) > 280:
                preview += "..."

            hits.append(
                SearchHit(
                    rank=rank,
                    doc_id=result.doc_id,
                    score=result.score,
                    text=text,
                    preview=preview,
                )
            )

        return hits


    def rank_many(
        self,
        queries: list[str],
        model: str = "bge",
        top_k: int = 1000,
        batch_size: int = 32,
    ) -> list[list[SearchResult]]:
        """Recupera rankings para varias consultas."""
    
        if model not in self.MODELS:
            raise ValueError(f"Modelo desconocido: {model}")
    
        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 1 <= top_k <= self.config.candidate_depth
        ):
            raise ValueError("top_k fuera del rango permitido.")
    
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size <= 0
        ):
            raise ValueError("batch_size debe ser positivo.")
    
        if not isinstance(queries, list):
            raise TypeError("queries debe ser una lista.")
    
        if any(
            not isinstance(query, str) or not query.strip()
            for query in queries
        ):
            raise ValueError("Las consultas no pueden estar vacías.")
    
        if not queries:
            return []
    
        if model in ("jaccard", "tfidf", "bm25"):
            retriever = self._get_lexical(model)
    
            return [
                retriever.search(query, top_k=top_k)
                for query in queries
            ]
    
        if model == "bge":
            return self._get_semantic().search_many(
                queries,
                top_k=top_k,
                batch_size=batch_size,
            )
    
        # Híbrido: exactamente 1000 candidatos por modelo.
        depth = self.config.candidate_depth
    
        bm25 = self._get_lexical("bm25")
        semantic = self._get_semantic()
    
        lexical_rankings = [
            bm25.search(query, top_k=depth)
            for query in queries
        ]
    
        semantic_rankings = semantic.search_many(
            queries,
            top_k=depth,
            batch_size=batch_size,
        )
    
        combined = []
    
        for lexical_results, semantic_results in zip(
            lexical_rankings, semantic_rankings
        ):
            fused = weighted_rrf(
                bm25_ids=[
                    result.doc_id for result in lexical_results
                ],
                semantic_ids=[
                    result.doc_id for result in semantic_results
                ],
                k=self.config.rrf_k,
                semantic_weight=self.config.rrf_semantic_weight,
                top_k=top_k,
            )
    
            combined.append(fused)
    
        return combined
