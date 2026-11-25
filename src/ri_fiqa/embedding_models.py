
"""Configuraciones de encoders para recuperación semántica."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingProfile:
    model_id: str
    query_prompt: str | None
    document_prompt: str | None


MODEL_SPECS = {
    "minilm": EmbeddingProfile(
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        query_prompt=None,
        document_prompt=None,
    ),
    "bge": EmbeddingProfile(
        model_id="BAAI/bge-base-en-v1.5",
        query_prompt=(
            "Represent this sentence for searching "
            "relevant passages: "
        ),
        document_prompt="",
    ),
    "e5": EmbeddingProfile(
        model_id="intfloat/e5-base-v2",
        query_prompt="query: ",
        document_prompt="passage: ",
    ),
}


# Posible mejora (NO ACTIVA): MiniLM usa 384 D frente a los 768 D de BGE.
# Cambiar encoder requiere reconstruir FAISS, metadata y hashes del despliegue.
# El query_prompt de BGE NO es un prompt de un LLM generativo.

class PromptedEncoder:
    """Aplica instrucciones distintas a consultas y documentos."""

    def __init__(
        self,
        model,
        query_prompt: str,
        document_prompt: str,
    ):
        self.model = model
        self.query_prompt = query_prompt
        self.document_prompt = document_prompt

    def encode_query(self, texts, **kwargs):
        return self.model.encode_query(
            texts,
            prompt=self.query_prompt,
            **kwargs,
        )

    def encode_document(self, texts, **kwargs):
        return self.model.encode_document(
            texts,
            prompt=self.document_prompt,
            **kwargs,
        )


def configure_encoder(
    model,
    query_prompt=None,
    document_prompt=None,
):
    """Mantiene compatibilidad con índices MiniLM existentes."""

    if query_prompt is None and document_prompt is None:
        return model

    if query_prompt is None or document_prompt is None:
        raise ValueError(
            "La configuración de prompts está incompleta."
        )

    return PromptedEncoder(
        model,
        query_prompt=query_prompt,
        document_prompt=document_prompt,
    )
