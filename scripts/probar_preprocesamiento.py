
from pathlib import Path
from datasets import load_from_disk

from ri_fiqa.preprocessing import (
    TextPreprocessor,
    PreprocessConfig,
)

BASE_DIR = Path(__file__).resolve().parents[1]

queries = load_from_disk(
    str(BASE_DIR / "data" / "raw" / "queries")
)

consulta = queries[0]["text"]

con_stopwords = TextPreprocessor()
sin_stopwords = TextPreprocessor(
    PreprocessConfig(remove_stopwords=False)
)

print("CONSULTA ORIGINAL:")
print(consulta)

print("\nTOKENS CON STOPWORDS ELIMINADAS:")
print(con_stopwords.process(consulta))

print("\nTOKENS SIN ELIMINAR STOPWORDS:")
print(sin_stopwords.process(consulta))
