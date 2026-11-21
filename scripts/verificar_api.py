
"""Smoke test HTTP del backend FiQA completo."""

import argparse
import sys

import httpx
from ri_fiqa.config import SELECTED_CONFIG


MODELS = (
    "jaccard",
    "tfidf",
    "bm25",
    "bge",
    "hybrid",
)

QUERY = "What is the difference between APR and APY?"


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
    )

    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    try:
        with httpx.Client(
            base_url=base_url,
            timeout=120,
        ) as client:

            # 1. Comprobar el proceso.
            response = client.get("/health")
            response.raise_for_status()

            assert response.json()["status"] == "ok"
            print("[OK] /health")

            # 2. Comprobar los recursos.
            response = client.get("/ready")
            response.raise_for_status()

            assert response.json()["status"] == "ready"
            assert response.json()["lexical_preprocessing"] == SELECTED_CONFIG.morphology
            print("[OK] /ready")

            # 3. Comprobar los modelos.
            response = client.get("/models")
            response.raise_for_status()

            available = {
                model["id"]
                for model in response.json()["models"]
            }

            assert available == set(MODELS)
            assert response.json()["lexical_configuration"] == {
                "morphology": SELECTED_CONFIG.morphology,
                "bm25_k1": SELECTED_CONFIG.bm25_k1,
                "bm25_b": SELECTED_CONFIG.bm25_b,
            }
            print("[OK] /models")

            # 4. Ejecutar búsquedas reales.
            for model in MODELS:
                response = client.post(
                    "/search",
                    json={
                        "query": QUERY,
                        "model": model,
                        "top_k": 3,
                    },
                )

                response.raise_for_status()
                data = response.json()

                assert data["model"] == model
                assert data["count"] == 3
                assert len(data["results"]) == 3

                ranks = [
                    item["rank"]
                    for item in data["results"]
                ]

                assert ranks == [1, 2, 3]

                assert all(
                    item["doc_id"] and item["text"]
                    for item in data["results"]
                )

                # Regresión basada en una búsqueda
                # previamente verificada sobre FiQA.
                if model == "bge":
                    assert (
                        data["results"][0]["doc_id"]
                        == "263225"
                    )

                print(
                    f"[OK] /search {model:<8} "
                    f"{data['elapsed_ms']:.2f} ms"
                )

            # 5. Comparar modelos.
            response = client.post(
                "/search/compare",
                json={
                    "query": QUERY,
                    "models": [
                        "bm25", "bge", "hybrid"
                    ],
                    "top_k": 3,
                },
            )

            response.raise_for_status()
            data = response.json()

            assert [
                result["model"]
                for result in data["rankings"]
            ] == ["bm25", "bge", "hybrid"]

            print("[OK] /search/compare")

            # 6. Verificar entrada inválida.
            response = client.post(
                "/search",
                json={
                    "query": QUERY,
                    "model": "unknown",
                },
            )

            assert response.status_code == 422
            print("[OK] Validación HTTP 422")

            # 7. Comprobar CORS preflight.
            response = client.options(
                "/search",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers":
                        "content-type",
                },
            )

            assert response.status_code == 200
            assert (
                response.headers.get(
                    "access-control-allow-origin"
                )
                == "http://localhost:5173"
            )

            print("[OK] CORS")

    except (
        httpx.HTTPError,
        AssertionError,
        KeyError,
        TypeError,
    ) as exc:
        print(f"\n[ERROR] Verificación fallida: {exc}")
        return 1

    print("\nBACKEND FIQA: VERIFICACIÓN COMPLETADA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
