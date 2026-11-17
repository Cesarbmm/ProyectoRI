
import unittest

from ri_fiqa.preprocessing import (
    TextPreprocessor,
    PreprocessConfig,
)


class TestTextPreprocessor(unittest.TestCase):

    def setUp(self):
        self.processor = TextPreprocessor()

    def test_normalizacion(self):
        tokens = self.processor.process(
            "BANK bank Bank"
        )
        self.assertEqual(
            tokens, ["bank", "bank", "bank"]
        )

    def test_stopwords(self):
        tokens = self.processor.process(
            "the bank and the investor"
        )
        self.assertEqual(
            tokens, ["bank", "investor"]
        )

    def test_sin_eliminar_stopwords(self):
        processor = TextPreprocessor(
            PreprocessConfig(remove_stopwords=False)
        )
        tokens = processor.process("the bank")
        self.assertEqual(tokens, ["the", "bank"])

    def test_terminos_financieros(self):
        tokens = self.processor.process(
            "401(k) and 10.5% APR/APY"
        )
        self.assertIn("401k", tokens)
        self.assertIn("10.5%", tokens)
        self.assertIn("apr", tokens)
        self.assertIn("apy", tokens)

    def test_negaciones(self):
        tokens = self.processor.process(
            "No, this isn't a safe investment"
        )
        self.assertIn("no", tokens)
        self.assertIn("not", tokens)

    def test_documento_vacio(self):
        self.assertEqual(
            self.processor.process(""), []
        )
        self.assertEqual(
            self.processor.process(None), []
        )

    def test_terminos_protegidos(self):
        tokens = self.processor.process(
            "Bill amount and interest"
        )
        self.assertIn("bill", tokens)
        self.assertIn("amount", tokens)
        self.assertIn("interest", tokens)


if __name__ == "__main__":
    unittest.main()
