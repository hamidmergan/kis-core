"""Embedding providers for KI Tutor – abstraction layer over KISSKI and future local models."""

import json
import time
from abc import ABC, abstractmethod

from loguru import logger


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts and return a list of embedding vectors."""
        ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class KisskiEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible embedding client pointing at KISSKI /v1/embeddings."""

    _BATCH_SIZE = 100

    def __init__(self) -> None:
        from openai import OpenAI
        from src.config import Settings
        s = Settings()
        self._client = OpenAI(api_key=s.kisski_api_key, base_url=s.kisski_base_url)
        self._model = s.kisski_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i: i + self._BATCH_SIZE]
            for attempt in range(2):
                try:
                    response = self._client.embeddings.create(
                        model=self._model,
                        input=batch,
                    )
                    results.extend(item.embedding for item in response.data)
                    break
                except Exception as e:
                    if attempt == 0:
                        logger.warning("Embedding batch {}/{} failed (attempt 1): {} – retrying in 3s", i, len(texts), e)
                        time.sleep(3)
                    else:
                        raise RuntimeError(f"Embedding request failed: {e}") from e
        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider.

    Currently only 'kisski' is supported.
    # TODO: add LocalEmbeddingProvider branch when local model support is added.
    """
    from src.config import Settings
    provider = Settings().tutor_embedding_provider
    if provider == "kisski":
        return KisskiEmbeddingProvider()
    raise ValueError(f"Unknown tutor_embedding_provider: {provider!r}")


def compute_fingerprint(provider: EmbeddingProvider) -> str:
    """Embed a fixed sentinel string and return the vector as a JSON string.

    The fingerprint is stored alongside indexed sources so we can detect
    model drift (different model → different fingerprint).
    """
    vector = provider.embed_one("KIS Tutor Embedding Fingerprint v1")
    return json.dumps(vector)
