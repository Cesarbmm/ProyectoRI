
import unittest

from fastapi.testclient import TestClient

from ri_fiqa.api import app, get_search_service, get_readiness
from ri_fiqa.search_service import SearchHit
from ri_fiqa.config import SELECTED_CONFIG, RetrievalConfig
from ri_fiqa.indexing import InvertedIndex
from ri_fiqa.preprocessing import PreprocessConfig, TextPreprocessor
from ri_fiqa.search_service import SearchService


class FakeSearchService:

    def __init__(self):
        self.calls = []

    def search(self, query, model="bge", top_k=5):
        self.calls.append((query, model, top_k))

        return [
            SearchHit(
                rank=1,
                doc_id="d1",
                score=0.75,
                text="Document about financial investments.",
                preview="Document about financial investments.",
            )
        ]


class MissingIndexService:

    def search(self, query, model="bge", top_k=5):
        raise FileNotFoundError("Índice ausente.")


class TestAPI(unittest.TestCase):

    def setUp(self):
        self.fake = FakeSearchService()

        app.dependency_overrides[get_search_service] = (
            lambda: self.fake
        )

        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["status"], "ok"
        )

    def test_models(self):
        response = self.client.get("/models")

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["default_model"], "bge")
        self.assertEqual(data["lexical_configuration"]["morphology"], SELECTED_CONFIG.morphology)
        self.assertEqual(data["lexical_configuration"]["bm25_b"], SELECTED_CONFIG.bm25_b)

        self.assertEqual(
            {model["id"] for model in data["models"]},
            {"jaccard", "tfidf", "bm25", "bge", "hybrid"},
        )

    def test_search_returns_documents(self):
        response = self.client.post(
            "/search",
            json={
                "query": "What is APR?",
                "model": "bge",
                "top_k": 3,
            },
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()

        self.assertEqual(data["model"], "bge")
        self.assertEqual(data["count"], 1)
        self.assertEqual(
            data["results"][0]["doc_id"], "d1"
        )

        self.assertEqual(
            self.fake.calls[-1],
            ("What is APR?", "bge", 3),
        )

    def test_whitespace_query_is_rejected(self):
        response = self.client.post(
            "/search",
            json={
                "query": "   ",
                "model": "bm25",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_unknown_model_is_rejected(self):
        response = self.client.post(
            "/search",
            json={
                "query": "retirement",
                "model": "unknown",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_invalid_top_k_is_rejected(self):
        for value in (0, 21, True):
            with self.subTest(value=value):
                response = self.client.post(
                    "/search",
                    json={
                        "query": "retirement",
                        "top_k": value,
                    },
                )

                self.assertEqual(
                    response.status_code, 422
                )

    def test_compare_models(self):
        response = self.client.post(
            "/search/compare",
            json={
                "query": "investment",
                "models": ["bm25", "bge"],
                "top_k": 2,
            },
        )

        self.assertEqual(response.status_code, 200)

        rankings = response.json()["rankings"]

        self.assertEqual(len(rankings), 2)

        self.assertEqual(
            [ranking["model"] for ranking in rankings],
            ["bm25", "bge"],
        )

    def test_compare_rejects_duplicate_models(self):
        response = self.client.post(
            "/search/compare",
            json={
                "query": "investment",
                "models": ["bge", "bge"],
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_cors_local_frontend(self):
        response = self.client.get(
            "/models",
            headers={
                "Origin": "http://localhost:5173"
            },
        )

        self.assertEqual(
            response.headers.get(
                "access-control-allow-origin"
            ),
            "http://localhost:5173",
        )

    def test_missing_index_returns_503(self):
        app.dependency_overrides[get_search_service] = (
            lambda: MissingIndexService()
        )

        response = self.client.post(
            "/search",
            json={"query": "retirement"},
        )

        self.assertEqual(response.status_code, 503)

    
    def test_api_applies_morphology_to_documents_and_queries(self):
        index = InvertedIndex(TextPreprocessor(PreprocessConfig(morphology="stemming")))
        index.add_document("d", "bank investments")
        service = SearchService(
            config=RetrievalConfig(morphology="stemming"), inverted_index=index,
            document_texts={"d": "bank investments"},
        )
        app.dependency_overrides[get_search_service] = lambda: service
        for model in ("jaccard", "tfidf", "bm25"):
            response = self.client.post("/search", json={"query": "banks", "model": model})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["results"][0]["doc_id"], "d")


    def test_ready_success(self):
        app.dependency_overrides[get_readiness] = lambda: {
            "status": "ready",
            "components": {"faiss_index": True},
        }
    
        response = self.client.get("/ready")
    
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["status"],
            "ready",
        )
    
    
    def test_ready_unavailable(self):
        app.dependency_overrides[get_readiness] = lambda: {
            "status": "not_ready",
            "components": {"faiss_index": False},
        }
    
        response = self.client.get("/ready")
    
        self.assertEqual(response.status_code, 503)
        self.assertFalse(
            response.json()["components"]["faiss_index"]
        )
    
    
    def test_cors_preflight(self):
        response = self.client.options(
            "/search",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    
        self.assertEqual(response.status_code, 200)
    
        self.assertEqual(
            response.headers.get(
                "access-control-allow-origin"
            ),
            "http://localhost:5173",
        )
    


if __name__ == "__main__":
    unittest.main()
