"""One door to every AI provider: each call takes a seat, and goes to the fallback when the first choice does not answer."""

from __future__ import annotations

import contextvars
import email.utils
import json
import os
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

import httpx
from loguru import logger

try:
    # The OpenAI SDK 3.x speaks httpx2, a separate package with the same interface as httpx.
    import httpx2 as _sdk_http
except ImportError:  # pragma: no cover - older SDKs use httpx itself
    _sdk_http = httpx

from src.limits import (
    LLM_LARGE_INPUT_CHARS,
    LLM_LARGE_INPUT_SHARE,
    PROVIDER_DOWN_SECONDS,
    PROVIDER_SEAT_WAIT_SECONDS,
)
from src.services import provider_slots

# Every feature counts against one field of its provider, image understanding with the LLM.
FEATURE_BUCKET: dict[str, str] = {
    "chat": "llm",
    "doc_translate": "llm",
    "transcript_translate": "llm",
    "vision": "llm",
    "stt": "stt",
    "tts": "tts",
    "image_gen": "image",
    "image_edit": "image",
    "embedding": "embedding",
    "ocr": "ocr",
}
BUCKETS: tuple[str, ...] = ("llm", "stt", "tts", "image", "embedding", "ocr")

# A voice only exists at its own provider, so speech output never falls back.
NO_FALLBACK_FEATURES = frozenset({"tts"})

# Answers that say the provider cannot serve right now, as opposed to a broken request.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_DOWN_KEY = "kis:provider-down:{}:{}"
# A held seat is renewed every 20 s, so one left unrenewed this long belongs to a process that died.
_SEAT_STALE_SECONDS = provider_slots.HELD_STALE_SECONDS
# A first choice that is not there has to be noticed fast, otherwise the fallback helps nobody.
_CONNECT_TIMEOUT = 10.0
# The body leaves in pieces like the SDK sends it, a single write would have to finish within the write timeout.
_PIECE = 64 * 1024
_MULTIPART_MODEL = re.compile(rb'(name="model"\r\n(?:[^\r\n]+\r\n)*\r\n)(.*?)(\r\n--)', re.S)

_exempt: contextvars.ContextVar[bool] = contextvars.ContextVar("provider_seat_exempt", default=False)

# The rank this process queues with at the door, a worker runs one job at a time and sets it per job.
_rank = 0

try:
    from openai import OpenAIError as _SdkError
except ImportError:  # pragma: no cover - the SDK is always installed in the containers
    _SdkError = Exception


class SeatsFull(provider_slots.ProviderFull, _SdkError):
    """A full provider that the OpenAI SDK passes on as it is, instead of waiting twice more."""


@contextmanager
def seat_exempt():
    """Calls inside take no seat, meant for the Francis chat a person waits for live."""
    token = _exempt.set(True)
    try:
        yield
    finally:
        _exempt.reset(token)


def exempt_this_request() -> None:
    """Frees the rest of the current request from seats, its streaming task inherits the mark."""
    _exempt.set(True)


def seat_rank_for(queue: Optional[str], priority: Optional[int]) -> int:
    """Quick services first, then tools and sources, then long services, continued stages and resumes."""
    if queue == "long" or (queue == "general" and (priority or 0) >= 9):
        return 2
    if queue in ("aia", "aia_ingest", "tts", "screencast"):
        return 1
    return 0


def set_seat_rank(rank: int) -> None:
    """Sets the rank for every call of this process until the next job sets its own."""
    global _rank
    _rank = rank


def _root(base_url: str) -> str:
    """The address without a trailing /v1, the part two providers differ in."""
    url = (base_url or "").rstrip("/")
    return url[:-3] if url.endswith("/v1") else url


@dataclass(frozen=True)
class Target:
    """One provider as the door sees it."""

    provider_id: int
    name: str
    root: str
    api_key: str
    model: str
    caps: dict = field(default_factory=dict, hash=False)

    @classmethod
    def of(cls, provider: dict, model: Optional[str]) -> "Target":
        return cls(
            provider_id=provider.get("id") or 0,
            name=provider.get("name") or "",
            root=_root(provider["base_url"]),
            api_key=provider.get("api_key") or "not-needed",
            model=model or "",
            caps=dict(provider.get("concurrency") or {}),
        )


def fallback_target(feature: str, primary_id: int, primary_model: str = "") -> Optional[Target]:
    """The admin's fallback for this feature, or None when there is none or it cannot serve."""
    if feature in NO_FALLBACK_FEATURES:
        return None
    from src import database as db

    try:
        route = db.get_route(feature) or {}
        fallback_id = route.get("fallback_provider_id")
        if not fallback_id or fallback_id == primary_id:
            return None
        provider = db.get_provider(fallback_id)
    except Exception as e:  # noqa: BLE001 - without the database the call simply has no fallback
        logger.warning("Rückfall für {} nicht lesbar: {}", feature, e)
        return None
    if not provider or not provider.get("enabled") or provider.get("protocol") != "openai_compat":
        return None
    model = (route.get("provider_models") or {}).get(str(fallback_id)) or ""
    if not model or (feature == "embedding" and primary_model and model != primary_model):
        # Another embedding model would put the answers into a different vector space.
        return None
    return Target.of(provider, model)


def _targets(binding) -> tuple[Target, Optional[Target], str]:
    """First choice, the admin's fallback and the field the call counts against, for one binding."""
    primary = Target.of(binding.provider, binding.model)
    second = fallback_target(binding.feature, primary.provider_id, primary.model)
    return primary, second, FEATURE_BUCKET.get(binding.feature, binding.feature)


def transport_for(binding) -> "ProviderTransport":
    """The door for a plain httpx client, used for pictures and speech output."""
    return ProviderTransport(*_targets(binding))


def sdk_clients(binding) -> dict:
    """Both HTTP clients for an OpenAI SDK client, with the SDK's own defaults around the door."""
    from openai import DefaultAsyncHttpxClient, DefaultHttpxClient

    targets = _targets(binding)
    return {
        "http_client": DefaultHttpxClient(transport=SdkTransport(*targets)),
        "async_http_client": DefaultAsyncHttpxClient(transport=AsyncSdkTransport(*targets)),
    }


def sdk_http_client(binding):
    """The synchronous HTTP client for a plain OpenAI SDK client."""
    from openai import DefaultHttpxClient

    return DefaultHttpxClient(transport=SdkTransport(*_targets(binding)))


# ─── Shared state in Redis ─────────────────────────────────────────────────

_redis_client = None
_redis_pid = None


def _redis():
    """One Redis connection per process, a forked worker opens its own."""
    global _redis_client, _redis_pid
    if _redis_client is None or _redis_pid != os.getpid():
        _redis_client = provider_slots._redis()
        _redis_pid = os.getpid()
    return _redis_client


def _is_down(target: Target, bucket: str) -> bool:
    try:
        return bool(_redis().exists(_DOWN_KEY.format(target.provider_id, bucket)))
    except Exception:  # noqa: BLE001 - without Redis every provider counts as there
        return False


def _mark_down(target: Target, bucket: str, seconds: float, why: str) -> None:
    logger.warning("Anbieter {} ({}) antwortet nicht ({}), {:.0f} s lang zweite Wahl",
                   target.name, bucket, why, seconds)
    try:
        _redis().set(_DOWN_KEY.format(target.provider_id, bucket), why[:100], ex=max(1, int(seconds)))
    except Exception as e:  # noqa: BLE001 - then the next call just tries the first choice again
        logger.warning("Sperrvermerk nicht gespeichert: {}", e)


def _down_seconds(response) -> float:
    """How long the provider itself wants to be left alone, otherwise the default."""
    for name in ("retry-after", "ratelimit-reset", "x-ratelimit-reset"):
        value = response.headers.get(name)
        if not value:
            continue
        try:
            seconds = float(value)
        except ValueError:
            try:
                seconds = email.utils.parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError):
                continue
        return min(max(seconds, 5.0), 3600.0)
    return float(PROVIDER_DOWN_SECONDS)


# ─── The request itself ────────────────────────────────────────────────────


def _text_chars(body: bytes) -> int:
    """How much text a JSON call carries, pictures do not count."""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return 0
    if not isinstance(data, dict):
        return 0
    total = 0
    for message in data.get("messages") or []:
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            total += sum(len(p.get("text") or "") for p in content if isinstance(p, dict))
    for name in ("input", "prompt"):
        value = data.get(name)
        if isinstance(value, str):
            total += len(value)
        elif isinstance(value, list):
            total += sum(len(v) for v in value if isinstance(v, str))
    return total


def _with_model(body: bytes, content_type: str, model: str) -> bytes:
    """The same body with the fallback's model name, JSON or a multipart form."""
    if not model:
        return body
    if "application/json" in content_type:
        try:
            data = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return body
        if isinstance(data, dict) and "model" in data:
            data["model"] = model
            return json.dumps(data, ensure_ascii=False).encode("utf-8")
        return body
    if "multipart/form-data" in content_type:
        return _MULTIPART_MODEL.sub(lambda m: m.group(1) + model.encode() + m.group(3), body, count=1)
    return body


class _Door:
    """Everything both transports share: order, seats, rewriting and the memory of who failed."""

    def __init__(self, primary: Target, fallback: Optional[Target], bucket: str):
        self.primary = primary
        self.fallback = fallback
        self.bucket = bucket

    def serves(self, request) -> bool:
        return bool(self.primary.root) and str(request.url).startswith(self.primary.root)

    def order(self) -> list[Target]:
        """The first choice first, one that failed a moment ago behind the fallback."""
        if self.fallback is None:
            return [self.primary]
        both = [self.primary, self.fallback]
        there = [t for t in both if not _is_down(t, self.bucket)]
        # A provider with a note stays as the last try, a slow answer must not leave only a dead one.
        return there + [t for t in both if t not in there]

    def prepare(self, request, body: bytes, target: Target):
        """The request for this provider, with a short connect wait when a fallback stands by."""
        extensions = dict(request.extensions)
        if self.fallback is not None:
            timeout = dict(extensions.get("timeout") or {})
            timeout["connect"] = min(timeout.get("connect") or _CONNECT_TIMEOUT, _CONNECT_TIMEOUT)
            extensions["timeout"] = timeout
        if target is self.primary:
            request.extensions = extensions
            return request
        headers = [(k, v) for k, v in request.headers.multi_items()
                   if k.lower() not in ("host", "content-length", "authorization")]
        headers.append(("authorization", f"Bearer {target.api_key}"))
        url = target.root + str(request.url)[len(self.primary.root):]
        content = _with_model(body, request.headers.get("content-type", ""), target.model)
        return type(request)(request.method, url, headers=headers, content=content, extensions=extensions)

    def seats(self, target: Target, body: bytes) -> list[tuple[str, int]]:
        """Which seats this call needs, a call with a lot of material one of the few large ones too."""
        cap = target.caps.get(self.bucket)
        if not cap or _exempt.get():
            return []
        wanted = []
        if self.bucket == "llm" and _text_chars(body) >= LLM_LARGE_INPUT_CHARS:
            wanted.append((f"{target.provider_id}:llm:large", max(1, int(cap) // LLM_LARGE_INPUT_SHARE)))
        wanted.append((f"{target.provider_id}:{self.bucket}", int(cap)))
        return wanted

    def served(self, target: Target) -> None:
        """Names the provider that really answered, the SDK's own log line only knows the first choice."""
        if target is not self.primary:
            logger.info("{} hat für {} geantwortet ({})", target.name, self.primary.name, self.bucket)

    def switch(self, target: Target, seconds: float, why: str, last: bool) -> bool:
        """Notes the failure when a fallback stands by, and tells whether another provider is left to ask."""
        if self.fallback is not None:
            _mark_down(target, self.bucket, seconds, why)
        return not last


def _releaser(held: list[tuple[str, str]]):
    """Gives the seats back exactly once."""
    done = []

    def release() -> None:
        if done:
            return
        done.append(True)
        for key, ticket in held:
            provider_slots.release(key, ticket)
    return release


def _build(lib, full=provider_slots.ProviderFull):
    """Both transports for one HTTP library, so plain httpx clients and the SDK's httpx2 share one door."""

    class _Pieces(lib.SyncByteStream, lib.AsyncByteStream):
        """A body read into memory, sent again in small pieces."""

        def __init__(self, data: bytes):
            self._data = data

        def __iter__(self):
            for i in range(0, len(self._data), _PIECE):
                yield self._data[i:i + _PIECE]

        async def __aiter__(self):
            for i in range(0, len(self._data), _PIECE):
                yield self._data[i:i + _PIECE]

    class _ReleasingStream(lib.SyncByteStream):
        def __init__(self, stream, release):
            self._stream, self._release = stream, release

        def __iter__(self):
            yield from self._stream

        def close(self) -> None:
            try:
                self._stream.close()
            finally:
                self._release()

    class _AsyncReleasingStream(lib.AsyncByteStream):
        def __init__(self, stream, release):
            self._stream, self._release = stream, release

        async def __aiter__(self):
            async for chunk in self._stream:
                yield chunk

        async def aclose(self) -> None:
            try:
                await self._stream.aclose()
            finally:
                self._release()

    class ProviderTransport(lib.BaseTransport):
        """The synchronous door, installed in every client that talks to a provider."""

        def __init__(self, primary: Target, fallback: Optional[Target], bucket: str, inner=None):
            self._door = _Door(primary, fallback, bucket)
            self._inner = inner or lib.HTTPTransport()

        def _take(self, wanted: list[tuple[str, int]]) -> list[tuple[str, str]]:
            held: list[tuple[str, str]] = []
            try:
                for key, limit in wanted:
                    held.append((key, provider_slots.claim_ranked(
                        key, limit=limit, wait_seconds=PROVIDER_SEAT_WAIT_SECONDS, rank=_rank,
                        stale_seconds=_SEAT_STALE_SECONDS)))
            except provider_slots.ProviderFull as e:
                _releaser(held)()
                raise full(e.provider, e.waited) from None
            except BaseException:
                # A time limit struck while waiting, the seats already taken go back.
                _releaser(held)()
                raise
            return held

        def handle_request(self, request):
            door = self._door
            if not door.serves(request):
                return self._inner.handle_request(request)
            body = request.read()
            order = door.order()
            for i, target in enumerate(order):
                last = i == len(order) - 1
                outgoing = door.prepare(request, body, target)
                outgoing.stream = _Pieces(outgoing.content)
                release = _releaser(self._take(door.seats(target, body)))
                try:
                    response = self._inner.handle_request(outgoing)
                except lib.TransportError as e:
                    release()
                    if door.switch(target, PROVIDER_DOWN_SECONDS, type(e).__name__, last):
                        continue
                    raise
                if response.status_code in _RETRY_STATUS:
                    if door.switch(target, _down_seconds(response), str(response.status_code), last):
                        response.read()
                        response.close()
                        release()
                        continue
                if response.is_closed:
                    # A body that is already complete never calls close, so the seat goes back now.
                    release()
                else:
                    response.stream = _ReleasingStream(response.stream, release)
                door.served(target)
                return response
            raise RuntimeError("provider door without a target")  # pragma: no cover

        def close(self) -> None:
            self._inner.close()

    class AsyncProviderTransport(lib.AsyncBaseTransport):
        """The asynchronous door, for the streaming chat and the summary."""

        def __init__(self, primary: Target, fallback: Optional[Target], bucket: str, inner=None):
            self._door = _Door(primary, fallback, bucket)
            self._inner = inner or lib.AsyncHTTPTransport()

        async def _take(self, wanted: list[tuple[str, int]]) -> list[tuple[str, str]]:
            held: list[tuple[str, str]] = []
            try:
                for key, limit in wanted:
                    held.append((key, await provider_slots.claim_ranked_async(
                        key, limit=limit, wait_seconds=PROVIDER_SEAT_WAIT_SECONDS, rank=_rank,
                        stale_seconds=_SEAT_STALE_SECONDS)))
            except provider_slots.ProviderFull as e:
                _releaser(held)()
                raise full(e.provider, e.waited) from None
            except BaseException:
                # A time limit struck while waiting, the seats already taken go back.
                _releaser(held)()
                raise
            return held

        async def handle_async_request(self, request):
            door = self._door
            if not door.serves(request):
                return await self._inner.handle_async_request(request)
            body = await request.aread()
            order = door.order()
            for i, target in enumerate(order):
                last = i == len(order) - 1
                outgoing = door.prepare(request, body, target)
                outgoing.stream = _Pieces(outgoing.content)
                release = _releaser(await self._take(door.seats(target, body)))
                try:
                    response = await self._inner.handle_async_request(outgoing)
                except lib.TransportError as e:
                    release()
                    if door.switch(target, PROVIDER_DOWN_SECONDS, type(e).__name__, last):
                        continue
                    raise
                if response.status_code in _RETRY_STATUS:
                    if door.switch(target, _down_seconds(response), str(response.status_code), last):
                        await response.aread()
                        await response.aclose()
                        release()
                        continue
                if response.is_closed:
                    # A body that is already complete never calls close, so the seat goes back now.
                    release()
                else:
                    response.stream = _AsyncReleasingStream(response.stream, release)
                door.served(target)
                return response
            raise RuntimeError("provider door without a target")  # pragma: no cover

        async def aclose(self) -> None:
            await self._inner.aclose()

    return ProviderTransport, AsyncProviderTransport


# Plain httpx clients, for pictures and speech output.
ProviderTransport, AsyncProviderTransport = _build(httpx)
# The OpenAI SDK's clients, for the LLM, speech recognition, embeddings and text recognition.
SdkTransport, AsyncSdkTransport = _build(_sdk_http, SeatsFull)
