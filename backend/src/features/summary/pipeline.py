"""Orchestrates one run: language, reading, outline, sections, reporting in all the while."""

import asyncio
import contextlib
import re
from typing import Callable, Protocol

from loguru import logger

from src.features.summary import facts as fc
from src.features.summary import reading, writing
from src.features.summary.models import Caller, Outline
from src.features.summary.templates import Template, template_body
from src.limits import (
    SUMMARY_FACTS_MAX_CHARS,
    SUMMARY_FACTS_MIN_CHARS,
    SUMMARY_HEARTBEAT_SECONDS,
    SUMMARY_MAP_CONCURRENCY,
    SUMMARY_MAX_BACKOFF_SECONDS,
    SUMMARY_PROMPT_RESERVE_CHARS,
    SUMMARY_READ_MAX_ATTEMPTS,
    SUMMARY_RETRY_DELAY_SECONDS,
)


class PipelineInterrupted(Exception):
    """The stage ran out of working time, what is done is saved, the rest follows."""


class RunStore(Protocol):
    """Everything of one run that outlives a single attempt."""

    def load_language(self) -> str | None: ...
    def save_language(self, language: str) -> None: ...
    def load_extractions(self) -> dict[str, list[dict]]: ...
    def save_extraction(self, source_id: str, facts: list[dict]) -> None: ...
    def load_outline(self) -> dict | None: ...
    def save_outline(self, outline: dict) -> None: ...
    def load_sections(self) -> dict[int, str]: ...
    def save_section(self, index: int, text: str) -> None: ...
    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None: ...
    def heartbeat(self) -> None: ...


# Tells a file held back by the clock apart from one the provider turned away.
_SKIPPED = object()
_THROTTLED = object()

_LANGUAGE_SAMPLE_CHARS = 1500
_LANGUAGE_PROBE = (
    "Identify the language of the text the user sends. Answer with the English name of "
    "that language and nothing else, for example: English, German, Spanish."
)
LANGUAGE_FALLBACK = "the language of the main body text, ignoring cover pages, headers and footers"
_LANGUAGE_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ -][^\W\d_]+)?$", re.UNICODE)


def language_sample(text: str, sample_chars: int = _LANGUAGE_SAMPLE_CHARS) -> str:
    """An excerpt from the middle as a language sample, the edges mislead."""
    if len(text) <= sample_chars:
        return " ".join(text.split())
    mitte = len(text) // 2
    koerper = " ".join(text[max(0, mitte - sample_chars): mitte + sample_chars].split())
    if len(koerper) <= sample_chars:
        return koerper
    start = (len(koerper) - sample_chars) // 2
    return koerper[start:start + sample_chars]


def clean_language_name(raw: str | None) -> str | None:
    """Reduces a probe answer to a bare language name, or None if it is not one."""
    name = (raw or "").strip().strip(".!\"'").strip()
    if not name or len(name) > 30:
        return None
    return name if _LANGUAGE_NAME_RE.match(name) else None


async def detect_language(caller: Caller, text: str) -> str:
    """Asks the model for the language of a sample, a failure falls back."""
    try:
        antwort = await caller.create(
            messages=[{"role": "system", "content": _LANGUAGE_PROBE},
                      {"role": "user", "content": language_sample(text)}],
            temperature=0.0,
        )
        return clean_language_name(antwort.choices[0].message.content) or LANGUAGE_FALLBACK
    except Exception as e:  # noqa: BLE001 - the fallback wording still works
        logger.warning("Zusammenfassung: Sprache nicht erkannt ({})", e)
        return LANGUAGE_FALLBACK


def facts_budget() -> int:
    """Characters of facts one call may carry, from the admin's tool budget."""
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget

    return max(20_000, tool_context_budget() - SUMMARY_PROMPT_RESERVE_CHARS)


def facts_per_source(sources: int) -> int:
    """Each file's share of the facts budget, so all of them together always fit."""
    anteil = facts_budget() // max(1, sources)
    return max(SUMMARY_FACTS_MIN_CHARS, min(SUMMARY_FACTS_MAX_CHARS, anteil))


async def _map_phase(caller, sources, language, plan_text, categories, facts, store,
                     should_stop):
    """One call per file for everything not read yet, ten at once until one is refused."""
    fehlend = [q for q in sources if q["source_id"] not in facts]
    if not fehlend:
        return facts
    # From all files, not the missing ones, so every stage caps alike.
    anteil = facts_per_source(len(sources))
    semaphore = asyncio.Semaphore(SUMMARY_MAP_CONCURRENCY)
    gedrosselt = asyncio.Event()

    async def _one(quelle: dict):
        async with semaphore:
            # Asked after the semaphore, a check before it would pass for every coroutine at once.
            if should_stop and should_stop():
                return _SKIPPED
            if gedrosselt.is_set():
                return _THROTTLED
            try:
                gelesen = await reading.read_source(
                    caller, source=quelle, language=language, template_body=plan_text,
                    categories=categories, max_chars=anteil)
            except reading.RateLimited as e:
                # The whole run slows down, the rest is worked through one at a time.
                logger.warning("Zusammenfassung: Anbieter weist ab, ab jetzt einzeln ({})", e)
                gedrosselt.set()
                return _THROTTLED
        if gelesen:
            # A failure is never written down, the next round asks again.
            await asyncio.to_thread(store.save_extraction, quelle["source_id"], gelesen)
        return gelesen

    ergebnisse = await asyncio.gather(*(_one(q) for q in fehlend))
    for quelle, gelesen in zip(fehlend, ergebnisse):
        if gelesen is not _SKIPPED and gelesen is not _THROTTLED and gelesen:
            facts[quelle["source_id"]] = gelesen
    if any(g is _SKIPPED for g in ergebnisse):
        raise PipelineInterrupted
    abgewiesen = [q for q, g in zip(fehlend, ergebnisse) if g is _THROTTLED]
    if not abgewiesen:
        return facts
    return await _sequential_phase(caller, abgewiesen, language, plan_text, categories,
                                   anteil, facts, store, should_stop)


async def _sequential_phase(caller, offen, language, plan_text, categories, anteil, facts,
                            store, should_stop):
    """What the provider turned away, one call at a time with a growing wait."""
    for quelle in offen:
        if should_stop and should_stop():
            raise PipelineInterrupted
        for versuch in range(SUMMARY_READ_MAX_ATTEMPTS):
            try:
                gelesen = await reading.read_source(
                    caller, source=quelle, language=language, template_body=plan_text,
                    categories=categories, max_chars=anteil)
            except reading.RateLimited as e:
                if versuch + 1 >= SUMMARY_READ_MAX_ATTEMPTS:
                    logger.warning("Zusammenfassung: Datei '{}' bleibt abgewiesen ({})",
                                   quelle["filename"], e)
                    break
                warte = min(SUMMARY_RETRY_DELAY_SECONDS * 2 ** versuch,
                            SUMMARY_MAX_BACKOFF_SECONDS)
                await asyncio.sleep(warte)
                continue
            if gelesen:
                await asyncio.to_thread(store.save_extraction, quelle["source_id"], gelesen)
                facts[quelle["source_id"]] = gelesen
            break
    return facts


async def _outline_phase(caller, language, plan_text, sources, pool, pool_text, store,
                         should_stop):
    gemerkt = await asyncio.to_thread(store.load_outline)
    if gemerkt is not None:
        return Outline.model_validate(gemerkt)
    if should_stop and should_stop():
        raise PipelineInterrupted
    await asyncio.to_thread(store.progress, "outline")
    plan = await writing.plan_outline(caller, language=language, template_body=plan_text,
                                      sources=sources, pool=pool, pool_text=pool_text,
                                      target=writing.target_sections(len(pool_text)))
    if plan.sections:
        # An empty plan is never saved, or every later attempt would stay on the single call.
        await asyncio.to_thread(store.save_outline, plan.model_dump())
    return plan


async def _section_phase(caller, language, plan_text, outline, pool, headings,
                         store, should_stop):
    fertig = await asyncio.to_thread(store.load_sections)
    texte: list[str] = []
    geschrieben: list[tuple[str, str]] = []
    gesamt = len(outline.sections)
    budget = facts_budget()
    for i, abschnitt in enumerate(outline.sections):
        if i in fertig:
            texte.append(fertig[i])
            geschrieben.append((abschnitt.title, fertig[i]))
            continue
        if should_stop and should_stop():
            raise PipelineInterrupted
        await asyncio.to_thread(store.progress, "section", i + 1, gesamt)
        andere = [a for j, a in enumerate(outline.sections) if j > i]
        text = await writing.write_section(caller, language=language, template_body=plan_text,
                                           section=abschnitt, others=andere,
                                           written=geschrieben,
                                           facts=writing.section_facts(abschnitt, pool),
                                           budget=budget)
        await asyncio.to_thread(store.save_section, i, text)
        texte.append(text)
        geschrieben.append((abschnitt.title, text))
    return writing.assemble(outline.intro, [a.title for a in outline.sections], texte, headings)


async def _keepalive(store: RunStore, interval: float) -> None:
    """Reports the job in while a call is out, a whole phase can pass in silence."""
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(store.heartbeat)
        except Exception:  # noqa: BLE001 - a missed beat must not sink the run
            return


async def run_pipeline(caller: Caller, *, sources: list[dict], template: Template,
                       store: RunStore, should_stop: Callable[[], bool] | None = None) -> str:
    """The finished document as Markdown, reported in while the calls are out."""
    puls = asyncio.create_task(_keepalive(store, SUMMARY_HEARTBEAT_SECONDS))
    try:
        return await _build(caller, sources, template, store, should_stop)
    finally:
        puls.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await puls


async def _build(caller, sources, template, store, should_stop) -> str:
    plan_text = template_body(template)
    gelesen = await asyncio.to_thread(store.load_extractions)
    sprache = await asyncio.to_thread(store.load_language)
    if not sprache:
        probe = next((q["content"] for q in sources if q["content"]), "")
        sprache = await detect_language(caller, probe)
        await asyncio.to_thread(store.save_language, sprache)

    await asyncio.to_thread(store.progress, "map")
    gelesen = await _map_phase(caller, sources, sprache, plan_text, template.categories,
                               gelesen, store, should_stop)

    vorrat = fc.build_pool(sources, gelesen)
    if not vorrat:
        raise RuntimeError("Aus keiner Quelle liessen sich Fakten herausziehen.")
    vorrat_text = fc.pool_block(vorrat, facts_budget())
    quellen = fc.source_names(vorrat)

    outline = await _outline_phase(caller, sprache, plan_text, quellen, vorrat, vorrat_text,
                                   store, should_stop)
    if not outline.sections:
        if should_stop and should_stop():
            raise PipelineInterrupted
        await asyncio.to_thread(store.progress, "compose")
        return await writing.compose_single(caller, language=sprache, template_body=plan_text,
                                            sources=quellen, pool=vorrat,
                                            pool_text=vorrat_text)
    return await _section_phase(caller, sprache, plan_text, outline, vorrat,
                                template.headings, store, should_stop)


def run_pipeline_sync(caller: Caller, *, sources: list[dict], template: Template,
                      store: RunStore, should_stop: Callable[[], bool] | None = None) -> str:
    """Synchronous door into run_pipeline, for the Celery task calling in."""
    return asyncio.run(run_pipeline(caller, sources=sources, template=template, store=store,
                                    should_stop=should_stop))
