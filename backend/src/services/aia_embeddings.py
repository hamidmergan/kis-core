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
# Wie oft eine Zeitueberschreitung mit GLEICHER Groesse wiederholt wird, bevor der
# Aufruf doch kleiner schneidet. Eins, denn jeder Versuch kostet die volle
# Zeitschranke. Der eine Versuch faengt den blossen Aussetzer ab, ohne die
# Stapelgroesse wegen einer Stoerung zu verlieren.
_MAX_TIMEOUT_RETRIES = 1

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


def _is_timeout(e: Exception) -> bool:
    """True, wenn die Gegenstelle gar nicht geantwortet hat.

    Dritte Absage-Art neben "zu gross" und "Kontingent voll", und die teuerste:
    sie kostet jedes Mal die volle Zeitschranke. Halbieren hilft hier NIE, denn die
    Groesse ist nicht das Problem. Ohne diese Unterscheidung wurde eine haengende
    Gegenstelle als "zu gross" gelesen und dieselbe Anfrage viermal geschickt, was
    die Quellenchips minutenlang aufhielt.
    """
    if type(e).__name__ in ("APITimeoutError", "APIConnectionError", "TimeoutError"):
        return True
    text = str(e).lower()
    return "timed out" in text or "timeout" in text or "connection error" in text


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

    def __init__(self, base_url: str, api_key: str, model: str, *,
                 timeout: float = 60.0, retry_on_timeout: bool = True) -> None:
        from langfuse.openai import OpenAI
        # 60s timeout: covers cold-start model loads on the first request after
        # a provider switch. Warm calls return in well under a second. Chat
        # callers wrap this in to_thread so the event loop stays free.
        # ``timeout`` ist absenkbar fuer Aufrufer, denen ein Ergebnis nur solange
        # nuetzt, wie jemand darauf wartet (Quellenchips).
        # max_retries=0 ist tragend, nicht kosmetisch: der SDK-Standard ist 2, also
        # wartete ein Aufruf mit "60s Zeitschranke" in Wahrheit dreimal 60s, bevor
        # er ueberhaupt als Fehler ankam. Die Wiederhol-Regel gehoert in ``embed``,
        # wo sie zaehlbar und im Log sichtbar ist.
        self._client = OpenAI(api_key=api_key, base_url=base_url,
                              timeout=timeout, max_retries=0)
        self._model = model
        self._key = (base_url, model)
        self._retry_on_timeout = retry_on_timeout

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

        Drei Absagen, drei Antworten: "zu gross" wird sofort kleiner versucht,
        "Kontingent voll" nach einer Pause gleich gross, "keine Antwort" erst einmal
        gleich gross und erst danach kleiner. Die dritte Regel ist der Grund dieser
        Aufteilung: eine Zeitschranke sofort als Groessenproblem zu lesen kostet jede
        Wiederholung die volle Wartezeit, ohne dass sich die Anfrage aendert. Ganz auf
        das Schneiden zu verzichten waere aber auch falsch, sonst scheitert ein Upload
        an jedem Anbieter, der 1000 Eingaben nicht in der Zeit schafft.
        """
        size = _learned_batch_size.get(self._key, AIA_EMBEDDING_BATCH_SIZE)
        results: list[list[float]] = []
        pending = list(texts)
        shrinks = 0
        timeout_retries = 0
        darf_lernen = True

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
                else:
                    if _is_timeout(e):
                        # Wer auf ein Ergebnis wartet, bekommt hier sofort die Absage:
                        # ein zweiter Versuch kostet nochmal die volle Schranke und die
                        # Antwort geht auch ohne Chips raus.
                        if not self._retry_on_timeout:
                            raise RuntimeError(f"Embedding request failed: {e}") from e
                        # Im Hintergrund erst gleiche Groesse noch einmal. War es nur ein
                        # Aussetzer, ist der Upload damit durch, ohne die Stapelgroesse
                        # wegen einer Stoerung zu verlieren.
                        if timeout_retries < _MAX_TIMEOUT_RETRIES:
                            timeout_retries += 1
                            logger.warning(
                                "Embedding: Gegenstelle antwortet nicht bei {} Eingaben ({}), "
                                "gleiche Groesse noch einmal",
                                len(batch), e,
                            )
                            continue
                        # Zweimal zu langsam heisst: vielleicht IST der Stapel zu gross
                        # fuer diese Gegenstelle. Jetzt darf doch geschnitten werden,
                        # sonst scheitert ein Upload an jedem langsameren Anbieter.
                    if size > 1 and shrinks < _MAX_SHRINKS:
                        shrinks += 1
                        # Die naechste Anfrage MUSS kleiner werden als die gerade abgelehnte.
                        # Die gelernte Groesse liegt oft weit ueber dem Stapel (1000 gelernt,
                        # 6 Zeilen geschickt); halbierte man nur sie, ginge dieselbe Anfrage
                        # unveraendert noch dreimal raus und jede Wiederholung waere reine
                        # Wartezeit. Deshalb notfalls am Stapel selbst halbieren.
                        size = max(1, size // 2)
                        if size >= len(batch):
                            # Notschnitt: die gelernte Groesse lag ueber dem Stapel, das
                            # Halbieren haette die Anfrage nicht veraendert. Am Stapel
                            # selbst schneiden, aber NICHTS daraus lernen. Dass 3 von 6
                            # Chip-Zeilen durchgehen, sagt nichts ueber die Grenze der
                            # Gegenstelle, wuerde aber den naechsten Upload mit 1000
                            # Chunks in hunderte Dreier-Anfragen zerlegen.
                            size = max(1, len(batch) // 2)
                            darf_lernen = False
                        logger.warning(
                            "Embedding: Endpunkt lehnt {} Eingaben ab ({}), neuer Versuch mit {}",
                            len(batch), e, size,
                        )
                        continue
                    raise RuntimeError(f"Embedding request failed: {e}") from e

            results.extend(vectors)
            pending = pending[len(batch):]
            # Das Kontingent fuer Zeitschranken gilt je Stapel, nicht je Aufruf. Sonst
            # wuerde ein Aussetzer beim ersten von fuenfzig Stapeln einen ganzen Upload
            # am dreissigsten Stapel scheitern lassen.
            timeout_retries = 0
            if darf_lernen and _learned_batch_size.get(self._key) != size:
                _learned_batch_size[self._key] = size

        return results


def get_embedding_provider(*, timeout: float = 60.0,
                           retry_on_timeout: bool = True) -> EmbeddingProvider:
    """Return the currently-active embedding provider.

    Reads the ``embedding`` feature route from the admin panel. Changing the
    route requires a reindex, so a silent fallback would corrupt the index —
    when no route is configured we raise.

    ``timeout`` / ``retry_on_timeout`` trennen zwei Arten von Aufrufern. Der Upload
    laeuft im Hintergrund und darf auf eine kalt startende Gegenstelle warten. Die
    Quellenchips laufen, waehrend jemand vor dem fertigen Text sitzt: dort ist eine
    kurze Schranke ohne zweiten Versuch richtig, denn die Antwort geht auch ohne
    Chips raus (siehe AIA_ATTRIBUTION_EMBED_TIMEOUT_SECONDS).
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
        timeout=timeout,
        retry_on_timeout=retry_on_timeout,
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
    (vLLM, e.g. e5-mistral) return slightly different vectors on every
    call (non-deterministic), so a float-based fingerprint never matches itself
    and the reindex warning would be permanently stuck — even right after a
    successful reindex.

    This PROBES the provider (one sentinel embed). Prefer ``fingerprint_from_dim``
    whenever a real embedding (hence the dimension) is already at hand — e.g. during
    ingest — to avoid the extra call.
    """
    dim = len(provider.embed_one("KIS Tutor Embedding Fingerprint v1"))
    return fingerprint_from_dim(provider, dim)
