"""Embedding providers for AI assistant - abstraction over OpenAI-compatible HTTP endpoints and Ollama.

The OpenAI-compatible adapter is one class with two configured instances (today:
KISSKI and THL myLab); the Ollama adapter is separate because it uses Ollama's
native /api/embed endpoint to set ``options.num_ctx`` (which the OpenAI-compat
shim drops). The active provider is chosen at runtime via the admin panel
(DB settings, see get_embedding_provider).
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
    multiple deployments (KISSKI, THL myLab, etc.) are different instances of
    this same class.
    """

    _BATCH_SIZE = 100

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from langfuse.openai import OpenAI
        # 60s timeout: covers a local-Ollama cold-start model load on the first
        # request after a provider switch. Warm calls (KISSKI or warm Ollama)
        # return in well under a second. Chat callers wrap this in to_thread
        # so the event loop stays free even at the worst case.
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


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding client using Ollama's native /api/embed API.

    Uses the native endpoint (not OpenAI-compat) so we can pass options.num_ctx
    - the OpenAI-compat /v1/embeddings endpoint ignores Modelfile parameters.
    """

    # 600-char chunks ~ 240 tokens each; batch of 5 ~ 1200 tokens < 2048 limit -> safe
    _BATCH_SIZE = 5
    # nomic-bert context_length=2048 tokens; German BERT subword tokenizer ~2-3 chars/token
    # -> 1000 chars ~ 400-500 tokens, safely within limit
    _NUM_CTX = 2048

    def __init__(self, base_url: str, model: str) -> None:
        from langfuse import Langfuse
        base = base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self._embed_url = base + "/api/embed"
        self._model = model
        self._langfuse = Langfuse()

    # Safety net only - chunker now produces <=600 char chunks, this should never trigger
    _MAX_CHARS = 700

    def _truncate(self, text: str) -> str:
        if len(text) <= self._MAX_CHARS:
            return text
        cut = text[:self._MAX_CHARS].rsplit(None, 1)[0]
        logger.debug("Ollama embed: truncated {} → {} chars", len(text), len(cut))
        return cut

    def embed(self, texts: list[str]) -> list[list[float]]:
        import json
        import urllib.request
        import urllib.error
        results: list[list[float]] = []
        truncated = [self._truncate(t) for t in texts]
        for i in range(0, len(truncated), self._BATCH_SIZE):
            batch = truncated[i: i + self._BATCH_SIZE]
            payload = json.dumps({
                "model": self._model,
                "input": batch,
                "options": {"num_ctx": self._NUM_CTX},
            }).encode()
            generation = self._langfuse.generation(
                name="ollama-embed",
                model=self._model,
                model_parameters={"num_ctx": self._NUM_CTX},
                input=batch,
            )
            for attempt in range(2):
                try:
                    req = urllib.request.Request(
                        self._embed_url,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        data = json.loads(resp.read())
                    batch_results = data["embeddings"]
                    results.extend(batch_results)
                    generation.end(
                        output=f"{len(batch_results)} embedding(s), dim={len(batch_results[0]) if batch_results else 0}",
                        usage={"input": sum(len(t) for t in batch), "unit": "CHARACTERS"},
                    )
                    break
                except urllib.error.HTTPError as e:
                    body = e.read().decode(errors="replace")
                    logger.warning("Ollama embed HTTP {}: lens={} body={}", e.code, [len(t) for t in batch], body)
                    if attempt == 0:
                        time.sleep(3)
                    else:
                        generation.end(level="ERROR", status_message=f"HTTP {e.code}: {body}")
                        raise RuntimeError(f"Ollama embedding request failed: {e} - {body}") from e
                except Exception as e:
                    if attempt == 0:
                        logger.warning("Ollama embed batch {}/{} failed: {} - retrying in 3s", i, len(texts), e)
                        time.sleep(3)
                    else:
                        generation.end(level="ERROR", status_message=str(e))
                        raise RuntimeError(f"Ollama embedding request failed: {e}") from e

        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Return the currently-active embedding provider.

    Reads the ``embedding`` feature route from the admin tab. Ollama endpoints
    are detected by base_url (``11434`` or ``ollama`` in the host); they use
    the native ``/api/embed`` endpoint so we can pass ``options.num_ctx``,
    which the OpenAI-compat shim drops on Ollama.

    Changing the route requires a reindex, so a silent fallback would corrupt
    the index — when no route is configured we raise.
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

    is_ollama = "11434" in base_url or "ollama" in base_url.lower()
    if is_ollama:
        return OllamaEmbeddingProvider(base_url=base_url, model=model)

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
