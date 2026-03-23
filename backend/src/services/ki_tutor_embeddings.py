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


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding client using Ollama's native /api/embed API.

    Uses the native endpoint (not OpenAI-compat) so we can pass options.num_ctx
    — the OpenAI-compat /v1/embeddings endpoint ignores Modelfile parameters.
    """

    # Ollama sums token lengths across all batch inputs against num_ctx → send 1 at a time
    _BATCH_SIZE = 1
    # nomic-bert context_length=2048 tokens; German BERT subword-tokenizer ~2-3 chars/token
    # → 1000 chars ≈ 400-500 tokens, safely within limit
    _NUM_CTX = 2048

    def __init__(self) -> None:
        import urllib.parse
        from src.config import Settings
        s = Settings()
        # Derive base URL without /v1 suffix
        base = s.ollama_base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        self._embed_url = base + "/api/embed"
        self._model = s.ollama_embedding_model

    # nomic-bert: 2048 token ctx, German BERT subword ~2-3 chars/token → 1000 chars ≈ 400-500 tokens
    _MAX_CHARS = 1000

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
                    results.extend(data["embeddings"])
                    break
                except urllib.error.HTTPError as e:
                    body = e.read().decode(errors="replace")
                    logger.warning("Ollama embed HTTP {}: lens={} body={}", e.code, [len(t) for t in batch], body)
                    if attempt == 0:
                        time.sleep(3)
                    else:
                        raise RuntimeError(f"Ollama embedding request failed: {e} – {body}") from e
                except Exception as e:
                    if attempt == 0:
                        logger.warning("Ollama embed batch {}/{} failed: {} – retrying in 3s", i, len(texts), e)
                        time.sleep(3)
                    else:
                        raise RuntimeError(f"Ollama embedding request failed: {e}") from e
        return results


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider."""
    from src.config import Settings
    provider = Settings().tutor_embedding_provider
    if provider == "kisski":
        return KisskiEmbeddingProvider()
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    raise ValueError(f"Unknown tutor_embedding_provider: {provider!r}")


def compute_fingerprint(provider: EmbeddingProvider) -> str:
    """Embed a fixed sentinel string and return the vector as a JSON string.

    The fingerprint is stored alongside indexed sources so we can detect
    model drift (different model → different fingerprint).
    """
    vector = provider.embed_one("KIS Tutor Embedding Fingerprint v1")
    return json.dumps(vector)
