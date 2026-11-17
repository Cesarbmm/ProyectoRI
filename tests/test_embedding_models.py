
import unittest

from ri_fiqa.embedding_models import (
    MODEL_SPECS,
    configure_encoder,
)


class FakeModel:
    def __init__(self):
        self.calls = []

    def encode_query(self, texts, **kwargs):
        self.calls.append(("query", texts, kwargs))
        return "query_vectors"

    def encode_document(self, texts, **kwargs):
        self.calls.append(("document", texts, kwargs))
        return "document_vectors"


class TestEmbeddingModels(unittest.TestCase):

    def test_bge_prompts(self):
        model = FakeModel()
        spec = MODEL_SPECS["bge"]

        encoder = configure_encoder(
            model,
            spec.query_prompt,
            spec.document_prompt,
        )

        encoder.encode_query(["What is APR?"])
        encoder.encode_document(["APR is..."])

        self.assertEqual(
            model.calls[0][2]["prompt"],
            spec.query_prompt,
        )

        self.assertEqual(
            model.calls[1][2]["prompt"],
            "",
        )

    def test_e5_prompts(self):
        model = FakeModel()
        spec = MODEL_SPECS["e5"]

        encoder = configure_encoder(
            model,
            spec.query_prompt,
            spec.document_prompt,
        )

        encoder.encode_query(["retirement"])
        encoder.encode_document(["Savings advice"])

        self.assertEqual(
            model.calls[0][2]["prompt"],
            "query: ",
        )

        self.assertEqual(
            model.calls[1][2]["prompt"],
            "passage: ",
        )

    def test_minilm_compatibility(self):
        model = FakeModel()

        encoder = configure_encoder(
            model,
            None,
            None,
        )

        self.assertIs(encoder, model)

    def test_explicit_empty_prompt(self):
        model = FakeModel()
    
        encoder = configure_encoder(
            model,
            query_prompt="",
            document_prompt="",
        )
    
        encoder.encode_query(["retirement"])
    
        self.assertEqual(
            model.calls[0][2]["prompt"],
            "",
        )    


if __name__ == "__main__":
    unittest.main()
