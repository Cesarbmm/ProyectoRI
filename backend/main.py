"""Vercel adapter. Retrieval algorithms and frozen parameters live in ri_fiqa."""

import hashlib
import json
import os
import resource
import sys
import time
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNTIME = Path(os.getenv("RI_RUNTIME_DIR", str(HERE / "runtime"))).resolve()
sys.path.insert(0, str(HERE))
os.environ["RI_PROJECT_ROOT"] = str(RUNTIME)
os.environ["RI_DEVICE"] = "cpu"
os.environ["HF_HUB_CACHE"] = str(RUNTIME / "hf/hub")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

from ri_fiqa import api as engine_api
from ri_fiqa.runtime import inspect_assets
from fastapi.middleware.cors import CORSMiddleware

app = engine_api.app
# Restrict browser access to the exact configured origins and this project's
# account-scoped Vercel previews. This does not allow arbitrary vercel.app sites.
if os.getenv("RI_CORS_ORIGIN_REGEX"):
    app.user_middleware = [item for item in app.user_middleware if item.cls != CORSMiddleware]
    app.add_middleware(
        CORSMiddleware, allow_origins=engine_api.origins,
        allow_origin_regex=os.environ["RI_CORS_ORIGIN_REGEX"],
        allow_credentials=False, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )


@lru_cache(maxsize=1)
def verify_integrity():
    manifest = json.loads((HERE / "assets-manifest.json").read_text(encoding="utf-8"))
    encoder = manifest["encoder"]
    specs = [(RUNTIME / item["path"], item) for item in manifest["files"]]
    snapshot = RUNTIME / "hf/hub" / ("models--" + encoder["model_id"].replace("/", "--")) / "snapshots" / encoder["revision"]
    specs += [(snapshot / item["path"], item) for item in encoder["files"]]
    for path, item in specs:
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            return False
        with path.open("rb") as file:
            if hashlib.file_digest(file, "sha256").hexdigest() != item["sha256"]:
                return False
    return True


def readiness():
    status = inspect_assets(RUNTIME)
    try:
        status["components"]["verified_full_runtime"] = verify_integrity()
    except (OSError, ValueError, KeyError):
        status["components"]["verified_full_runtime"] = False
    if not all(status["components"].values()):
        status["status"] = "not_ready"
    status.update({"corpus_documents": 57638, "indexed_documents": 57600})
    return status


app.dependency_overrides[engine_api.get_readiness] = readiness


def memory():
    pages = int(Path("/proc/self/statm").read_text().split()[1])
    rss = pages * os.sysconf("SC_PAGE_SIZE")
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return {"rss_bytes": rss, "peak_rss_bytes": max(rss, peak)}


@app.middleware("http")
async def measure(request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    print(json.dumps({"event": "fiqa_request", "path": request.url.path,
                      "status": response.status_code,
                      "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                      **memory()}), flush=True)
    return response


if os.getenv("RI_RUNTIME_DIAGNOSTICS") == "1":
    @app.get("/runtime")
    def diagnostics():
        service = engine_api.get_search_service()
        report = json.loads((RUNTIME / "build-report.json").read_text())
        return {**report, **memory(), "device": service.device,
                "loaded_lexical_models": sorted(service._lexical_models),
                "semantic_loaded": service._semantic_retriever is not None,
                "loaded_corpus_documents": len(service._document_texts or {}),
                "configuration": {"morphology": service.config.morphology,
                                  "bm25_k1": service.config.bm25_k1,
                                  "bm25_b": service.config.bm25_b,
                                  "rrf_k": service.config.rrf_k,
                                  "bge_weight": service.config.rrf_semantic_weight}}

    @app.post("/runtime/measure")
    def measure_all_models():
        """Measure all five real systems in the same Linux process (Preview only)."""
        service = engine_api.get_search_service()
        results = []
        with engine_api._inference_lock:
            for model in service.MODELS:
                started = time.perf_counter()
                hits = service.search(
                    "What is the difference between APR and APY?", model, 3
                )
                results.append({"model": model, "count": len(hits),
                                "first_doc_id": hits[0].doc_id,
                                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2)})
        return {**diagnostics(), "measured_models": results}
