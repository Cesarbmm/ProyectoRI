
"""API REST del motor de Recuperación de Información FiQA."""

import os

from dataclasses import asdict
from threading import Lock
from time import perf_counter
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from ri_fiqa.search_service import SearchService

from pathlib import Path

from fastapi.responses import JSONResponse
from ri_fiqa.runtime import inspect_assets

# Los identificadores coinciden con SearchService.MODELS.
ModelName = Literal[
    "jaccard",
    "tfidf",
    "bm25",
    "bge",
    "hybrid",
]


# ---------------------------------------------------------
# 1. Esquemas de entrada
# ---------------------------------------------------------

class SearchRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    query: str = Field(min_length=1, max_length=500)
    model: ModelName = "bge"
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        strict=True,
    )


class CompareRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    query: str = Field(min_length=1, max_length=500)

    models: list[ModelName] = Field(
        min_length=2,
        max_length=5,
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        strict=True,
    )

    @field_validator("models")
    @classmethod
    def require_distinct_models(cls, value):
        if len(set(value)) != len(value):
            raise ValueError(
                "No repitas modelos en la comparación."
            )

        return value


# ---------------------------------------------------------
# 2. Esquemas de salida
# ---------------------------------------------------------

class SearchHitOut(BaseModel):
    rank: int
    doc_id: str
    score: float
    text: str
    preview: str


class SearchResponse(BaseModel):
    query: str
    model: ModelName
    count: int
    elapsed_ms: float
    results: list[SearchHitOut]


class ComparisonResponse(BaseModel):
    query: str
    elapsed_ms: float
    rankings: list[SearchResponse]


class ModelInfo(BaseModel):
    id: ModelName
    label: str
    score_type: str


class ModelsResponse(BaseModel):
    default_model: ModelName
    models: list[ModelInfo]


MODEL_INFO = [
    ModelInfo(
        id="jaccard",
        label="Jaccard (binario)",
        score_type="jaccard",
    ),
    ModelInfo(
        id="tfidf",
        label="TF-IDF (coseno)",
        score_type="cosine_tfidf",
    ),
    ModelInfo(
        id="bm25",
        label="BM25",
        score_type="bm25",
    ),
    ModelInfo(
        id="bge",
        label="BGE + FAISS",
        score_type="cosine_embedding",
    ),
    ModelInfo(
        id="hybrid",
        label="Híbrido BM25 + BGE",
        score_type="weighted_rrf",
    ),
]


# ---------------------------------------------------------
# 3. Aplicación y CORS
# ---------------------------------------------------------

app = FastAPI(
    title="FiQA — Motor de Recuperación de Información",
    version="1.0.0",
    description=(
        "API de búsqueda sobre FiQA. "
        "Las puntuaciones no son comparables "
        "entre modelos diferentes."
    ),
)

# Orígenes autorizados del frontend durante el desarrollo.
# En despliegue se configurarán mediante variable de entorno.
origins = [
    origin.strip()
    for origin in os.getenv(
        "RI_CORS_ORIGINS",
        (
            "http://localhost:5173,"
            "http://127.0.0.1:5173,"
            "http://localhost:3000"
        ),
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------
# 4. Servicio compartido
# ---------------------------------------------------------

_service: SearchService | None = None

_service_lock = Lock()
_inference_lock = Lock()



def get_project_root() -> Path:
    """Permite configurar la raíz del proyecto."""
    configured = os.getenv("RI_PROJECT_ROOT")

    if configured:
        return Path(configured).resolve()

    return Path(__file__).resolve().parents[2]


def get_search_service() -> SearchService:
    """Mantiene una instancia del motor por proceso."""

    global _service

    with _service_lock:
        if _service is None:
            _service = SearchService(
                project_root=get_project_root(),
                device=os.getenv("RI_DEVICE", "auto"),
            )

        return _service


def get_readiness() -> dict:
    return inspect_assets(get_project_root())



def execute(
    service: SearchService,
    query: str,
    model: ModelName,
    top_k: int,
) -> SearchResponse:
    """Adapta SearchService al contrato de respuesta HTTP."""

    started = perf_counter()

    try:
        hits = service.search(
            query=query,
            model=model,
            top_k=top_k,
        )

    except (FileNotFoundError, RuntimeError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "El modelo no está disponible. "
                "Verifica los índices y dependencias "
                "del servidor."
            ),
        ) from exc

    return SearchResponse(
        query=query,
        model=model,
        count=len(hits),
        elapsed_ms=round(
            (perf_counter() - started) * 1000,
            2,
        ),
        results=[
            SearchHitOut(**asdict(hit))
            for hit in hits
        ],
    )


# ---------------------------------------------------------
# 5. Endpoints
# ---------------------------------------------------------

@app.get("/health")
def health():
    """Comprueba que la API responde."""
    return {
        "status": "ok",
        "service": "fiqa-ir",
    }


@app.get("/ready")
def ready(status: dict = Depends(get_readiness)):
    """Verifica los archivos y metadatos requeridos."""

    if status["status"] != "ready":
        return JSONResponse(
            status_code=503,
            content=status,
        )

    return status


@app.get("/models", response_model=ModelsResponse)
def models():
    """Devuelve los modelos configurados para la interfaz."""

    return ModelsResponse(
        default_model="bge",
        models=MODEL_INFO,
    )


@app.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    service: SearchService = Depends(get_search_service),
):
    """Ejecuta una búsqueda con el modelo seleccionado."""

    # Protección conservadora de los caches y el encoder
    # mientras implementamos concurrencia avanzada.
    with _inference_lock:
        return execute(
            service,
            body.query,
            body.model,
            body.top_k,
        )


@app.post(
    "/search/compare",
    response_model=ComparisonResponse,
)
def compare(
    body: CompareRequest,
    service: SearchService = Depends(get_search_service),
):
    """Ejecuta una consulta con varios modelos."""

    started = perf_counter()

    with _inference_lock:
        rankings = [
            execute(
                service,
                body.query,
                model,
                body.top_k,
            )
            for model in body.models
        ]

    return ComparisonResponse(
        query=body.query,
        elapsed_ms=round(
            (perf_counter() - started) * 1000,
            2,
        ),
        rankings=rankings,
    )
