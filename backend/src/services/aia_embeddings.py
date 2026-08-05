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

from src.limits import AIA_EMBEDDING_BATCH_SIZE

# Wie oft ein zu grosser Stapel hoechstens halbiert wird, bevor der Aufruf
# aufgibt. 3 reicht von 1000 bis 125 herunter und deckt jeden Anbieter ab, der
# eine Eingabegrenze in dieser Groessenordnung hat. Die Schranke ist wichtig,
# damit ein dauerhaft kaputter Endpunkt nicht hunderte Anfragen absetzt.
_MAX_SHRINKS = 3
# Pause vor dem zweiten Versuch, wenn das Kontingent des Anbieters voll ist.
_RATE_LIMIT_PAUSE_SECONDS = 3

# Vom Endpunkt gelernte Stapelgroessen, Schluessel ist (base_url, model).
# Der Provider wird pro Upload neu gebaut, das Gedaechtnis lebt im Worker-
# Prozess. Sonst wuerde jede Quelle die Grenze neu ertasten und dabei Aufrufe
# am geteilten Rate-Limit verbrennen. Eingetragen wird nur eine Groesse, die der
# Endpunkt wirklich angenommen hat, damit eine voruebergehende Stoerung den Wert
# nicht dauerhaft nach unten zieht.
_learned_batch_size: dict[tuple[str, str], int] = {}


def _is_rate_limited(e: Exception) -> bool:
    """True, wenn die Absage am vollen Kontingent liegt und nicht an der Groesse.

    Der Unterschied entscheidet ueber die Reaktion: bei "zu gross" hilft ein
    kleinerer Stapel, beim Rate-Limit macht Halbieren alles schlimmer, weil aus
    einer Anfrage zwei werden. Die Zeichenpruefung faengt Proxys ab, die den
    Statuscode nur in den Text schreiben.
    """
    if getattr(e, "status_code", None) == 429:
        return True
    text = str(e).lower()
    return "429" in text or "rate limit" in text


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

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        from langfuse.openai import OpenAI
        # 60s timeout: covers cold-start model loads on the first request after
        # a provider switch. Warm calls return in well under a second. Chat
        # callers wrap this in to_thread so the event loop stays free.
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        self._model = model
        self._key = (base_url, model)

    def _request(self, batch: list[str]) -> list[list[float]]:
        """Ein Aufruf gegen den Endpunkt. Eigene Methode, damit die Stapel-Logik
        in ``embed`` ohne echtes Netz pruefbar ist."""
        response = self._client.embeddings.create(model=self._model, input=batch)
        return [item.embedding for item in response.data]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts, so wenige Aufrufe wie moeglich.

        Die Stapelgroesse ist keine Einstellung, sondern wird am Endpunkt
        gemessen. Start ist der fuer myLab qwen3-embedding-4b gemessene Wert
        (1000 geht, 2000 laeuft in ein 502). Lehnt ein anderer Anbieter das ab,
        halbiert der Aufruf und merkt sich die Groesse, die durchging.
        """
        size = _learned_batch_size.get(self._key, AIA_EMBEDDING_BATCH_SIZE)
        results: list[list[float]] = []
        pending = list(texts)
        shrinks = 0

        while pending:
            batch = pending[:size]
            try:
                vectors = self._request(batch)
            except Exception as e:
                if _is_rate_limited(e):
                    logger.warning(
                        "Embedding: Kontingent voll bei {} Eingaben ({}), neuer Versuch in {}s",
                        len(batch), e, _RATE_LIMIT_PAUSE_SECONDS,
                    )
                    time.sleep(_RATE_LIMIT_PAUSE_SECONDS)
                    try:
                        vectors = self._request(batch)
                    except Exception as e2:
                        raise RuntimeError(f"Embedding request failed: {e2}") from e2
                elif size > 1 and shrinks < _MAX_SHRINKS:
                    shrinks += 1
                    size = max(1, size // 2)
                    logger.warning(
                        "Embedding: Endpunkt lehnt {} Eingaben ab ({}), neuer Versuch mit {}",
                        len(batch), e, size,
                    )
                    continue
                else:
                    raise RuntimeError(f"Embedding request failed: {e}") from e

            results.extend(vectors)
            pending = pending[len(batch):]
            if _learned_batch_size.get(self._key) != size:
                _learned_batch_size[self._key] = size

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
