"""Orchestrates one run: language, reading, outline, sections, reporting in all the while."""

import asyncio
import contextlib
import re
from typing import Callable, Protocol

from loguru import logger

from src.features.summary import facts as fc
from src.features.summary import settings as cfg
from src.features.summary import reading, writing
from src.features.summary.models import Caller, Outline
from src.features.summary.templates import Template, template_body
from src.limits import (
    SUMMARY_FACTS_MAX_CHARS,
    SUMMARY_FACTS_MIN_CHARS,
    SUMMARY_HEARTBEAT_SECONDS,
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


_LANGUAGE_SAMPLE_CHARS = 1500
# Below this the guess is noise, a file name or a page number is not a language.
_LANGUAGE_MIN_CHARS = 80
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


def language_name(code: str) -> str | None:
    """The English name behind a language code, None when the code names nothing.

    Only the base tag is asked for, so 'zh-cn' answers Chinese and not a country.
    """
    from babel import Locale

    try:
        return clean_language_name(Locale.parse(code.split("-")[0]).get_display_name("en"))
    except Exception:  # noqa: BLE001 - an unknown code is simply no name
        return None


def detect_language(text: str) -> str:
    """The language of a sample, read locally. The fallback wording when unsure.

    Naming its own language is not worth a model call, and a local guess cannot run
    into a rate limit halfway through a run.
    """
    probe = language_sample(text)
    if len(probe) < _LANGUAGE_MIN_CHARS:
        return LANGUAGE_FALLBACK
    try:
        from langdetect import DetectorFactory, detect

        # Without a fixed seed the same text can answer differently on two runs.
        DetectorFactory.seed = 0
        return language_name(detect(probe)) or LANGUAGE_FALLBACK
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


def read_max_facts(sources: int) -> int:
    """Facts one read call may return.

    Measured 20.09.: the model saturates at about 33 facts and 4.300 answer tokens per
    call, whatever the cap says, so a bigger cap buys nothing and a call per file is the
    only way every file gets its own share.
    """
    aus_budget = facts_per_source(sources) // reading.CHARS_PER_FACT
    return max(5, min(cfg.facts_cap(), aus_budget))


async def _read_one(caller, quelle, language, plan_text, categories, anteil, deckel):
    """One file, retried with a growing wait for as long as the provider turns it away."""
    for versuch in range(SUMMARY_READ_MAX_ATTEMPTS):
        try:
            return await reading.read_source(
                caller, source=quelle, language=language, template_body=plan_text,
                categories=categories, max_chars=anteil, max_facts=deckel)
        except reading.RateLimited as e:
            if versuch + 1 >= SUMMARY_READ_MAX_ATTEMPTS:
                logger.warning("Zusammenfassung: Datei '{}' bleibt abgewiesen ({})",
                               quelle["filename"], e)
                return None
            warte = min(SUMMARY_RETRY_DELAY_SECONDS * 2 ** versuch,
                        SUMMARY_MAX_BACKOFF_SECONDS)
            await asyncio.sleep(warte)
    return None


async def _map_phase(caller, sources, language, plan_text, categories, facts, store,
                     should_stop):
    """One call per file, as many at a time as the admin area allows.

    Measured 20.09. on the real documents: at three the slowest read takes 161 s while
    the provider drops a call at about 300 s. At five it is 205 s for 27 percent more
    throughput, and a provider that turns half as fast then kills the run.
    """
    fehlend = [q for q in sources if q["source_id"] not in facts]
    if not fehlend:
        return facts
    # From all files, not the missing ones, so every stage caps alike.
    anteil = facts_per_source(len(sources))
    deckel = read_max_facts(len(sources))
    # Read once per stage, so a change in the admin area reaches the next stage.
    semaphore = asyncio.Semaphore(cfg.map_concurrency())
    abgebrochen = False

    async def _eine(quelle: dict) -> None:
        nonlocal abgebrochen
        async with semaphore:
            # Asked after the semaphore, a check before it would pass for every coroutine at once.
            if should_stop and should_stop():
                abgebrochen = True
                return
            gelesen = await _read_one(caller, quelle, language, plan_text, categories,
                                      anteil, deckel)
        # Written outside the semaphore, so the next file starts while this one saves.
        if gelesen:
            # A failure is never written down, the next round asks again.
            await asyncio.to_thread(store.save_extraction, quelle["source_id"], gelesen)
            facts[quelle["source_id"]] = gelesen

    await asyncio.gather(*(_eine(q) for q in fehlend))
    if abgebrochen:
        raise PipelineInterrupted
    return facts


async def _outline_phase(caller, language, plan_text, sources, pool, pool_text, store,
                         should_stop):
    gemerkt = await asyncio.to_thread(store.load_outline)
    if gemerkt is not None:
        return Outline.model_validate(gemerkt)
    if should_stop and should_stop():
        raise PipelineInterrupted
    await asyncio.to_thread(store.progress, "outline")
    plan = await writing.plan_outline(
        caller, language=language, template_body=plan_text, sources=sources, pool=pool,
        pool_text=pool_text,
        target=writing.target_sections(len(pool_text), len(sources)))
    if plan.sections:
        # An empty plan is never saved, or every later attempt would stay on the single call.
        await asyncio.to_thread(store.save_outline, plan.model_dump())
    return plan


async def _write_group(caller, language, plan_text, outline, pool, indices, geschrieben,
                       budget) -> list[str]:
    """The texts of these sections in one call, one call each when the cut is not safe."""
    abschnitte = [outline.sections[i] for i in indices]
    andere = [a for j, a in enumerate(outline.sections) if j > max(indices)]
    fakten = [writing.section_facts(a, pool) for a in abschnitte]
    texte = await writing.write_sections(
        caller, language=language, template_body=plan_text, group=abschnitte, others=andere,
        written=geschrieben, facts=fakten, budget=budget)
    if texte is not None:
        return texte
    logger.warning("Zusammenfassung: Gruppe von {} Abschnitten nicht trennbar, einzeln",
                   len(indices))
    einzeln: list[str] = []
    for abschnitt, eigene in zip(abschnitte, fakten):
        text = await writing.write_sections(
            caller, language=language, template_body=plan_text, group=[abschnitt],
            others=andere,
            written=geschrieben + list(zip([a.title for a in abschnitte], einzeln)),
            facts=[eigene], budget=budget)
        if not text:
            raise RuntimeError("Das Modell hat nichts geantwortet.")
        einzeln.append(text[0])
    return einzeln


async def _section_phase(caller, language, plan_text, outline, pool, headings,
                         store, should_stop):
    texte: dict[int, str] = dict(await asyncio.to_thread(store.load_sections))
    geschrieben: list[tuple[str, str]] = []
    gesamt = len(outline.sections)
    budget = facts_budget()
    for gruppe in writing.group_sections(outline.sections):
        offen = [i for i in gruppe if i not in texte]
        if offen:
            if should_stop and should_stop():
                raise PipelineInterrupted
            await asyncio.to_thread(store.progress, "section", gruppe[-1] + 1, gesamt)
            # What an earlier stage already wrote is context here, never work again.
            vorher = geschrieben + [(outline.sections[i].title, texte[i])
                                    for i in gruppe if i in texte]
            neu = await _write_group(caller, language, plan_text, outline, pool, offen,
                                     vorher, budget)
            for i, text in zip(offen, neu):
                await asyncio.to_thread(store.save_section, i, text)
                texte[i] = text
        geschrieben += [(outline.sections[i].title, texte[i]) for i in gruppe]
    return writing.assemble(outline.intro, [a.title for a in outline.sections],
                            [texte.get(i, "") for i in range(gesamt)], headings,
                            title=outline.title)


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
        sprache = detect_language(probe)
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
