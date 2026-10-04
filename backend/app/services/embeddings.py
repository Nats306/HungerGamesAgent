"""Local embedding model (Sentence Transformers).

We use `intfloat/multilingual-e5-small` (384 dims, ~120 MB, runs on CPU). It is multilingual, so a
question asked in Spanish still finds English passages. E5 models expect the prefixes
"query: " and "passage: ", which this wrapper adds automatically.
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings

from app.core.config import get_settings


class E5Embeddings(Embeddings):
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy import, keep it lazy

        self.model = SentenceTransformer(model_name, device="cpu")
        self._uses_prefix = "e5" in model_name.lower()

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self._uses_prefix:
            texts = [f"passage: {t}" for t in texts]
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        if self._uses_prefix:
            text = f"query: {text}"
        return self._encode([text])[0]


_override: Embeddings | None = None


def set_embeddings(embeddings: Embeddings | None) -> None:
    """Swap the embedding model (used by tests)."""
    global _override
    _override = embeddings


@lru_cache
def _default_embeddings() -> Embeddings:
    return E5Embeddings(get_settings().embedding_model)


def get_embeddings() -> Embeddings:
    return _override or _default_embeddings()
