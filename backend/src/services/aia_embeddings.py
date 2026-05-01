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
        self._client = OpenAI(api_key=api_key, base_url=base_url)
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

    def __init__(self) -> None:
        from src.config import Settings
        from src.services.runtime_models import get_model
        from langfuse import Langfuse
        s = Settings()
        base = s.local_provider_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self._embed_url = base + "/api/embed"
        self._model = get_model("local_embedding_model")
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


# ── Factory functions per admin-panel slot ─────────────────────────────────

def _make_primary_embedding_provider() -> OpenAICompatEmbeddingProvider:
    """Build an OpenAI-compat embedding provider against the primary slot
    (today: KISSKI/GWDG)."""
    from src.config import Settings
    from src.services.runtime_models import get_model
    s = Settings()
    return OpenAICompatEmbeddingProvider(
        base_url=s.primary_provider_base_url,
        api_key=s.primary_provider_api_key,
        model=get_model("primary_embedding_model"),
    )


def _make_fallback_embedding_provider() -> OpenAICompatEmbeddingProvider:
    """Build an OpenAI-compat embedding provider against the fallback slot
    (today: THL myLab)."""
    from src.config import Settings
    from src.services.runtime_models import get_model
    s = Settings()
    base = (s.fallback_provider_base_url or "").rstrip("/")
    if not base:
        raise RuntimeError("Fallback embedding base URL not configured")
    # The fallback endpoint is open/unauthenticated within the TH network — any non-empty key works.
    return OpenAICompatEmbeddingProvider(
        base_url=f"{base}/v1",
        api_key="ignored",
        model=get_model("fallback_embedding_model"),
    )


def get_embedding_provider() -> EmbeddingProvider:
    """Return the currently-active embedding provider.

    Exactly one of the three admin toggles must be enabled. No env-var fallback:
    the admin explicitly picks a provider and any change requires a reindex,
    so a silent fallback would corrupt the index.
    """
    from src import database as db
    if db.get_setting("primary_embedding_enabled", "").lower() == "true":
        return _make_primary_embedding_provider()
    if db.get_setting("fallback_embedding_enabled", "").lower() == "true":
        return _make_fallback_embedding_provider()
    if db.get_setting("local_embedding_enabled", "").lower() == "true":
        return OllamaEmbeddingProvider()
    raise RuntimeError(
        "Kein Embedding-Anbieter aktiv. Bitte im Admin-Bereich unter 'Embeddings (KI-Assistent)' "
        "genau einen Anbieter aktivieren."
    )


def compute_fingerprint(provider: EmbeddingProvider) -> str:
    """Embed a fixed sentinel string and return the vector as a JSON string.

    The fingerprint is stored alongside indexed sources so we can detect
    model drift (different model -> different fingerprint).
    """
    vector = provider.embed_one("KIS Tutor Embedding Fingerprint v1")
    return json.dumps(vector)
