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

    # Chunks (input texts) per embedding request. Higher = fewer requests against
    # the shared GWDG rate limit (2/s, 15/min for the whole university). Measured
    # safe on myLab qwen3-embedding-4b: 1000 OK (~13s), 2000 → 502. Each chunk is
    # tiny (~300 tok, well under the model's 40k/input limit), so a full 1000-batch
    # is fine. NOTE: the ingest loop's _EMBED_BATCH must be >= this to take effect.
    _BATCH_SIZE = 1000

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


def fingerprint_from_dim(provider: EmbeddingProvider, dim: int) -> str:
    """Serialize the embedding-space identity ``{model, dim}`` from an ALREADY-known
    dimension — the byte-identical string ``compute_fingerprint`` produces, but with NO
    API call. The ingest path uses this: it gets ``dim`` for free as ``len(vector)`` from
    the chunk vectors it embeds anyway, so no separate probe embed is needed.
    Keep this serialization in lock-step with ``compute_fingerprint`` (same keys/order),
    or every already-indexed workspace would suddenly read as "stale → reindex"."""
    return json.dumps({"model": provider.model_name, "dim": dim}, sort_keys=True)


def compute_fingerprint(provider: EmbeddingProvider) -> str:
    """Return a stable identity of the embedding space: model name + dimension.

    Stored alongside indexed sources/workspaces so we can detect model drift
    (a different model -> a different fingerprint -> "needs reindex").

    We embed a fixed sentinel ONLY to learn the provider's true output
    dimension; we deliberately do NOT hash the raw floats. Real providers
    (vLLM/KISSKI e.g. e5-mistral) return slightly different vectors on every
    call (non-deterministic), so a float-based fingerprint never matches itself
    and the reindex warning would be permanently stuck — even right after a
    successful reindex.

    This PROBES the provider (one sentinel embed). Prefer ``fingerprint_from_dim``
    whenever a real embedding (hence the dimension) is already at hand — e.g. during
    ingest — to avoid the extra call.
    """
    dim = len(provider.embed_one("KIS Tutor Embedding Fingerprint v1"))
    return fingerprint_from_dim(provider, dim)
