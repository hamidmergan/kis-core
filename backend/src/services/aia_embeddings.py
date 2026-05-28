"""Embedding provider for the AI assistant.

Single class targeting any OpenAI-compatible ``/v1/embeddings`` endpoint. The
active provider (base URL, API key, model) is chosen at runtime via the admin
panel and stored in the ``providers`` + ``feature_routes`` tables (see
``get_embedding_provider``).
"""

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

    @property
    def model_name(self) -> str:
        """Configured model name - used for fingerprint metadata and logs."""
        return getattr(self, "_model", "")


class OpenAICompatEmbeddingProvider(EmbeddingProvider):
    """Embedding client for any OpenAI-compatible /v1/embeddings endpoint.

    A single instance is parameterised by ``base_url`` / ``api_key`` / ``model``;
    multiple deployments are different instances of this same class.
    """

    _BATCH_SIZE = 100

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from langfuse.openai import OpenAI
        # 60s timeout: covers cold-start model loads on the first request after
        # a provider switch. Warm calls return in well under a second. Chat
        # callers wrap this in to_thread so the event loop stays free.
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        self._model = model

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
                        logger.warning("Embedding batch {}/{} failed (attempt 1): {} - retrying in 3s", i, len(texts), e)
                        time.sleep(3)
                    else:
                        raise RuntimeError(f"Embedding request failed: {e}") from e
        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Return the currently-active embedding provider.

    Reads the ``embedding`` feature route from the admin panel. Changing the
    route requires a reindex, so a silent fallback would corrupt the index —
    when no route is configured we raise.
    """
    from src.services import feature_router
    try:
        binding = feature_router.resolve("embedding")
    except feature_router.FeatureNotConfigured as e:
        raise RuntimeError(
            "Kein Embedding-Anbieter aktiv. Bitte im Admin-Bereich unter 'KI' den "
            "Anbieter für das Feature 'Embedding' setzen. (" + str(e) + ")"
        )

    provider = binding.provider
    base_url = provider["base_url"].rstrip("/")
    model = binding.model or ""

    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return OpenAICompatEmbeddingProvider(
        base_url=base_url,
        api_key=provider.get("api_key") or "not-needed",
        model=model,
    )


def compute_fingerprint(provider: EmbeddingProvider) -> str:
    """Embed a fixed sentinel string and return the vector as a JSON string.

    The fingerprint is stored alongside indexed sources so we can detect
    model drift (different model -> different fingerprint).
    """
    vector = provider.embed_one("KIS Tutor Embedding Fingerprint v1")
    return json.dumps(vector)
