"""The read phase: a source cut into calls, the calls paced, what survives a refusal.

One call per slice, a few at a time. What one slice finished is written down before the
next one starts, so a stage that runs out of time never costs a read that succeeded.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

from loguru import logger

from src.limits import (
    FACTS_CONCURRENCY,
    FACTS_MAX_ATTEMPTS,
    FACTS_MAX_BACKOFF_SECONDS,
    FACTS_MIN_WINDOW_TOKENS,
    FACTS_OUTPUT_TOKENS,
    FACTS_PROMPT_TOKENS,
    FACTS_RETRY_DELAY_SECONDS,
    FACTS_SLICE_MAX_CHARS,
)
from src.services.model_limits import CHARS_PER_TOKEN
from src.services.source_reading import Source


class RunInterrupted(Exception):
    """The stage ran out of working time, what is done is saved, the rest follows."""


class RateLimited(Exception):
    """The provider turned the call away or let it run out, the run slows down."""


class WindowTooSmall(ValueError):
    """The chosen model cannot carry a useful slice, the run is refused up front."""


@dataclass(frozen=True)
class Slice:
    """One read call: which source, which of its pieces, and which part of how many."""

    source: int
    von: int
    bis: int
    teil: int
    teile: int

    @property
    def key(self) -> str:
        """What the store files this slice under."""
        return f"{self.source}:{self.teil}"

    @property
    def pieces(self) -> range:
        return range(self.von, self.bis)


class FactStore(Protocol):
    """Everything of one read phase that outlives a single attempt."""

    def load_slices(self) -> dict[str, list[dict]]: ...
    def save_slice(self, key: str, facts: list[dict], vollstaendig: bool) -> None: ...
    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None: ...
    def heartbeat(self) -> None: ...


def slice_chars(window_tokens: int) -> int:
    """How much text one call may carry on this model.

    The 250.000 stay the ceiling even where the window would allow more: a call only
    ever writes so much, and two calls read one file twice as deeply as one.
    """
    if window_tokens and window_tokens < FACTS_MIN_WINDOW_TOKENS:
        raise WindowTooSmall(window_tokens)
    if not window_tokens:
        # Unmeasured models are let through, the slice then simply stays at the ceiling.
        return FACTS_SLICE_MAX_CHARS
    passt = int((window_tokens - FACTS_OUTPUT_TOKENS - FACTS_PROMPT_TOKENS) * CHARS_PER_TOKEN)
    return max(1, min(FACTS_SLICE_MAX_CHARS, passt))


def _cut_points(source: Source, teile: int) -> list[int]:
    """Where to cut a source into ``teile`` parts, at a page break where there is one."""
    if teile <= 1:
        return [0, len(source.stuecke)]
    je_teil = len(source.stuecke) / teile
    punkte = [0]
    for n in range(1, teile):
        ziel = round(n * je_teil)
        # A piece whose page differs from its predecessor is a page break.
        seitenwechsel = [i for i in range(1, len(source.stuecke))
                         if source.stuecke[i].seite != source.stuecke[i - 1].seite]
        if seitenwechsel:
            ziel = min(seitenwechsel, key=lambda i: abs(i - ziel))
        ziel = max(punkte[-1] + 1, min(ziel, len(source.stuecke) - (teile - n)))
        punkte.append(ziel)
    punkte.append(len(source.stuecke))
    return punkte


def plan_slices(sources: list[Source], hoechstens: int) -> list[Slice]:
    """Every source cut into as few calls as its size allows."""
    aus: list[Slice] = []
    for nummer, source in enumerate(sources):
        if not source.stuecke:
            continue
        teile = max(1, -(-len(source.text) // max(1, hoechstens)))
        teile = min(teile, len(source.stuecke))
        punkte = _cut_points(source, teile)
        for i in range(teile):
            aus.append(Slice(source=nummer, von=punkte[i], bis=punkte[i + 1],
                             teil=i + 1, teile=teile))
    return aus


def overloaded(exc: Exception) -> bool:
    """Whether this failure means too much at once rather than a bad request."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (429, 503):
        return True
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return "timeout" in type(exc).__name__.casefold()


# One slice in, its entries and whether the answer was complete out. None once the
# reader has given up on it. A reader that wants to be paced raises RateLimited.
ReadSlice = Callable[[Slice], Awaitable[tuple[list[dict], bool] | None]]


async def _read_one(read: ReadSlice, teil: Slice) -> tuple[list[dict], bool] | None:
    """One slice, retried with a growing wait for as long as the provider turns it away."""
    for versuch in range(FACTS_MAX_ATTEMPTS):
        try:
            return await read(teil)
        except RateLimited as e:
            if versuch + 1 >= FACTS_MAX_ATTEMPTS:
                logger.warning("Fakten: Stueck {} bleibt abgewiesen ({})", teil.key, e)
                return None
            await asyncio.sleep(min(FACTS_RETRY_DELAY_SECONDS * 2 ** versuch,
                                    FACTS_MAX_BACKOFF_SECONDS))
    return None


async def map_slices(slices: list[Slice], *, read: ReadSlice, store: FactStore,
                     should_stop: Callable[[], bool] | None = None) -> dict[str, list[dict]]:
    """Every slice read once, a few at a time. A slice already read is not read again."""
    fertig = dict(await asyncio.to_thread(store.load_slices))
    await asyncio.to_thread(store.progress, "lesen", len(fertig), len(slices))
    offen = [t for t in slices if t.key not in fertig]
    if not offen:
        return fertig
    semaphore = asyncio.Semaphore(max(1, FACTS_CONCURRENCY))
    abgebrochen = False

    async def _eines(teil: Slice) -> None:
        nonlocal abgebrochen
        async with semaphore:
            # Asked after the semaphore, a check before it would pass for all at once.
            if should_stop and should_stop():
                abgebrochen = True
                return
            gelesen = await _read_one(read, teil)
        # Written outside the semaphore, so the next slice starts while this one saves.
        if gelesen is not None:
            eintraege, vollstaendig = gelesen
            await asyncio.to_thread(store.save_slice, teil.key, eintraege, vollstaendig)
            fertig[teil.key] = eintraege
        # One finished slice is proof of life, per unit as the docstring in heartbeat.py
        # asks for. Without this the watchdog only sees the touch before the first call
        # and kills a run whose slices together outlast its 10-minute stale window, even
        # though every single one of them came back fine.
        await asyncio.to_thread(store.heartbeat)

    await asyncio.gather(*(_eines(t) for t in offen))
    if abgebrochen:
        raise RunInterrupted
    return fertig


def by_source(gelesen: dict[str, list[dict]], slices: list[Slice],
              anzahl: int) -> list[list[dict]]:
    """The entries per source, the parts of one source back in their order."""
    aus: list[list[dict]] = [[] for _ in range(anzahl)]
    for teil in sorted(slices, key=lambda t: (t.source, t.teil)):
        aus[teil.source].extend(gelesen.get(teil.key) or [])
    return aus


def _rejects_schema(exc: Exception) -> bool:
    """True when the provider explicitly rejected the strict answer format."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if status != 400:
        return False
    text = str(exc).casefold()
    return "response_format" in text or "json" in text or "schema" in text


# Probed once per process, a provider without the schema mode must not cost every slice.
_schema_mode_supported = True


async def read_slice(client, model: str, *, teil: Slice, sources: list[Source],
                     language: str, book=None) -> tuple[list[dict], bool] | None:
    """One read call. Returns the entries and whether the answer came through whole.

    ``None`` once every attempt failed for a reason that is not overload. ``book``
    records the consumption of one answer, these calls go around the logged door.
    """
    global _schema_mode_supported
    from src.limits import FACTS_CALL_TIMEOUT_SECONDS, FACTS_OUTPUT_TOKENS
    from src.services import facts as fk

    quelle = sources[teil.source]
    nachrichten = [
        {"role": "system",
         "content": fk.system_prompt(language, fk.categories(language), teil.teil, teil.teile)},
        {"role": "user",
         "content": f"/no_think\nDocument '{quelle.dateiname}':\n\n"
                    f"{fk.numbered_pieces(quelle, teil.von, teil.bis)}"},
    ]
    for versuch in range(1, FACTS_MAX_ATTEMPTS + 1):
        try:
            # The SDK retries timeouts on its own, one attempt is the only way the limit holds.
            antwort = await client.with_options(max_retries=0).chat.completions.create(
                model=model, messages=nachrichten, temperature=0.1,
                timeout=FACTS_CALL_TIMEOUT_SECONDS,
                max_tokens=FACTS_OUTPUT_TOKENS,
                **({"response_format": fk.SCHEMA} if _schema_mode_supported else {}),
            )
            if book is not None:
                book(antwort)
            wahl = antwort.choices[0]
            angeschnitten = getattr(wahl, "finish_reason", None) == "length"
            if angeschnitten:
                logger.warning("Fakten: Stueck {} aus '{}' lief in den Deckel, es bleibt "
                               "unvollstaendig", teil.key, quelle.dateiname)
            eintraege = fk.parse_answer(wahl.message.content, gueltige_stuecke=teil.pieces)
            if eintraege:
                return eintraege, not angeschnitten
            raise RuntimeError("Das Modell hat keine Aussagen geliefert.")
        except Exception as e:  # noqa: BLE001 - one bad slice must not sink the run
            if overloaded(e):
                # The pacing belongs to map_slices, it decides what to do with this.
                raise RateLimited(str(e)) from e
            if _schema_mode_supported and _rejects_schema(e):
                logger.warning("Fakten: Schema-Modus abgelehnt, dieser Prozess fragt ab "
                               "jetzt ohne ({})", e)
                _schema_mode_supported = False
                continue
            if versuch >= FACTS_MAX_ATTEMPTS:
                logger.warning("Fakten: Stueck {} nach {} Versuch(en) ausgelassen ({})",
                               teil.key, versuch, e)
                return None
            await asyncio.sleep(FACTS_RETRY_DELAY_SECONDS)
    return None
