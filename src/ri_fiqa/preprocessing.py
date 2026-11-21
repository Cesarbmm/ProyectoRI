
"""Preprocesamiento textual para modelos léxicos de RI."""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


# Términos que no queremos eliminar en el dominio financiero.
PROTECTED_TERMS = {
    "no", "not", "nor", "never", "without",
    "bill", "amount", "interest", "us",
    "will", "may",
}

STOPWORDS = frozenset(
    ENGLISH_STOP_WORDS - PROTECTED_TERMS
)

# Conserva decimales y porcentajes.
# Divide términos compuestos con / o -.
TOKEN_PATTERN = re.compile(
    r"[a-z0-9]+(?:\.[a-z0-9]+)*(?:%)?"
)


@dataclass(frozen=True)
class PreprocessConfig:
    """Configuración de un experimento de procesamiento."""

    remove_stopwords: bool = True
    morphology: Literal["baseline", "stemming", "lemmatization"] = "baseline"

    def __post_init__(self):
        if self.morphology not in ("baseline", "stemming", "lemmatization"):
            raise ValueError("Morfología desconocida.")


class TextPreprocessor:
    """Normaliza y tokeniza textos en inglés."""

    def __init__(
        self,
        config: PreprocessConfig | None = None
    ):
        self.config = config or PreprocessConfig()
        self._transform = None
        if self.config.morphology == "stemming":
            from nltk.stem.snowball import SnowballStemmer

            self._transform = lru_cache(maxsize=100_000)(
                SnowballStemmer("english").stem
            )
        elif self.config.morphology == "lemmatization":
            from nltk.corpus import wordnet
            from nltk.stem import WordNetLemmatizer

            try:
                wordnet.ensure_loaded()
            except LookupError as exc:
                raise RuntimeError(
                    "Falta WordNet. Ejecuta: python -m nltk.downloader wordnet"
                ) from exc
            # POS nominal fijo: determinista y sin un segundo modelo/tagger.
            self._transform = lru_cache(maxsize=100_000)(
                WordNetLemmatizer().lemmatize
            )

    @staticmethod
    def normalize(text: str | None) -> str:
        """Normaliza caracteres y ciertas expresiones."""

        if not text:
            return ""

        text = unicodedata.normalize("NFKD", text)
        text = "".join(
            char for char in text
            if not unicodedata.combining(char)
        )
        text = text.lower().replace("’", "'")

        # Normalización financiera: 401(k) -> 401k
        text = re.sub(
            r"\b(\d+)\s*\(\s*k\s*\)",
            r"\1k",
            text
        )

        # Preservar el significado de negaciones.
        text = re.sub(r"\bwon't\b", "will not", text)
        text = re.sub(r"\bcan't\b", "can not", text)
        text = re.sub(
            r"\b([a-z]+)n't\b",
            r"\1 not",
            text
        )

        return text

    def process(self, text: str | None) -> list[str]:
        """Devuelve una lista ordenada de tokens."""

        normalized = self.normalize(text)
        tokens = TOKEN_PATTERN.findall(normalized)

        if self.config.remove_stopwords:
            tokens = [
                token for token in tokens
                if token not in STOPWORDS
            ]

        if self._transform is not None:
            tokens = [
                self._transform(token)
                if token.isalpha() and token not in PROTECTED_TERMS
                else token
                for token in tokens
            ]

        return tokens
