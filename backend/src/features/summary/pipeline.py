"""Orchestrates one run: language, reading, outline, sections, reporting in all the while."""

import asyncio
import contextlib
import re
from typing import Callable, Protocol

from loguru import logger

from src.features.summary import reading, splitting, writing
from src.features.summary.models import Caller, Outline
from src.features.summary.templates import Template, template_body
from src.limits import (
    SUMMARY_FACTS_MAX_CHARS,
    SUMMARY_FACTS_MIN_CHARS,
    SUMMARY_HEARTBEAT_SECONDS,
    SUMMARY_MAP_CONCURRENCY,
    SUMMARY_PROMPT_RESERVE_CHARS,
)


class PipelineInterrupted(Exception):
    """The stage ran out of working time, what is done is saved, the rest follows."""


class RunStore(Protocol):
    """Everything of one run that outlives a single attempt."""

    def load_language(self) -> str | None: ...
    def save_language(self, language: str) -> None: ...
    def load_extractions(self) -> dict[str, str | None]: ...
    def save_extraction(self, source_id: str, text: str | None) -> None: ...
    def load_outline(self) -> dict | None: ...
    def save_outline(self, outline: dict) -> None: ...
    def load_sections(self) -> dict[int, str]: ...
    def save_section(self, index: int, text: str) -> None: ...
    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None: ...
    def heartbeat(self) -> None: ...


# Tells a unit held back by the clock apart from a failed read.
_SKIPPED = object()

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


def facts_per_unit(units: int) -> int:
    """Each unit's share of the facts budget, so all of them together always fit."""
    anteil = facts_budget() // max(1, units)
    return max(SUMMARY_FACTS_MIN_CHARS, min(SUMMARY_FACTS_MAX_CHARS, anteil))


def _facts_block(used: list[tuple[str, str]], facts: dict[str, str | None]) -> str:
    """The facts as one context, each block still carrying its source id."""
    text = "\n\n".join(f"--- {sid} ({name}) ---\n{facts[sid]}" for sid, name in used)
    decke = facts_budget()
    if len(text) > decke:
        logger.warning("Zusammenfassung: Fakten {} Zeichen, gekuerzt auf {}", len(text), decke)
        text = text[:decke]
    return text


async def _map_phase(caller, units, language, plan_text, facts, store, should_stop):
    """One call per unit for everything not read yet."""
    semaphore = asyncio.Semaphore(SUMMARY_MAP_CONCURRENCY)
    fehlend = [u for u in units if u["source_id"] not in facts]
    if not fehlend:
        return facts
    # From all units, not the missing ones, so every stage caps alike.
    anteil = facts_per_unit(len(units))

    async def _one(einheit: dict):
        async with semaphore:
            # Asked after the semaphore, a check before it would pass for every coroutine at once.
            if should_stop and should_stop():
                return _SKIPPED
            text = await reading.read_unit(caller, unit=einheit, language=language,
                                           template_body=plan_text, max_chars=anteil)
        if text:
            # A failure is never written down, the next stage asks again.
            await asyncio.to_thread(store.save_extraction, einheit["source_id"], text)
        return text

    ergebnisse = await asyncio.gather(*(_one(u) for u in fehlend))
    unterbrochen = False
    for einheit, text in zip(fehlend, ergebnisse):
        if text is _SKIPPED:
            unterbrochen = True
            continue
        facts[einheit["source_id"]] = text
    if unterbrochen:
        raise PipelineInterrupted
    return facts


async def _outline_phase(caller, language, plan_text, sources, block, note, store, should_stop):
    gemerkt = await asyncio.to_thread(store.load_outline)
    if gemerkt is not None:
        return Outline.model_validate(gemerkt)
    if should_stop and should_stop():
        raise PipelineInterrupted
    await asyncio.to_thread(store.progress, "outline")
    plan = await writing.plan_outline(caller, language=language, template_body=plan_text,
                                      sources=sources, facts=block, part_note=note,
                                      target=writing.target_sections(len(block)))
    if plan.sections:
        # An empty plan is never saved, or every later attempt would stay on the single call.
        await asyncio.to_thread(store.save_outline, plan.model_dump())
    return plan


async def _section_phase(caller, language, plan_text, outline, block, note, headings,
                         store, should_stop):
    fertig = await asyncio.to_thread(store.load_sections)
    texte: list[str] = []
    geschrieben: list[tuple[str, str]] = []
    gesamt = len(outline.sections)
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
                                           written=geschrieben, facts=block, part_note=note)
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


async def run_pipeline(caller: Caller, *, units: list[dict], template: Template,
                       store: RunStore, should_stop: Callable[[], bool] | None = None) -> str:
    """The finished document as Markdown, reported in while the calls are out."""
    puls = asyncio.create_task(_keepalive(store, SUMMARY_HEARTBEAT_SECONDS))
    try:
        return await _build(caller, units, template, store, should_stop)
    finally:
        puls.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await puls


async def _build(caller, units, template, store, should_stop) -> str:
    plan_text = template_body(template)
    facts = await asyncio.to_thread(store.load_extractions)
    sprache = await asyncio.to_thread(store.load_language)
    if not sprache:
        probe = next((u["content"] for u in units if u["content"]), "")
        sprache = await detect_language(caller, probe)
        await asyncio.to_thread(store.save_language, sprache)

    await asyncio.to_thread(store.progress, "map")
    facts = await _map_phase(caller, units, sprache, plan_text, facts, store, should_stop)

    genutzt = [(u["source_id"], u.get("label") or u["filename"])
               for u in units if facts.get(u["source_id"])]
    if not genutzt:
        raise RuntimeError("Aus keiner Quelle liessen sich Fakten herausziehen.")
    block = _facts_block(genutzt, facts)
    quellen = [f"{sid} ({name})" for sid, name in genutzt]
    note = splitting.part_note(units, keep={sid for sid, _ in genutzt})

    outline = await _outline_phase(caller, sprache, plan_text, quellen, block, note,
                                   store, should_stop)
    if not outline.sections:
        if should_stop and should_stop():
            raise PipelineInterrupted
        await asyncio.to_thread(store.progress, "compose")
        return await writing.compose_single(caller, language=sprache, template_body=plan_text,
                                            sources=quellen, facts=block, part_note=note)
    return await _section_phase(caller, sprache, plan_text, outline, block, note,
                                template.headings, store, should_stop)


def run_pipeline_sync(caller: Caller, *, units: list[dict], template: Template,
                      store: RunStore, should_stop: Callable[[], bool] | None = None) -> str:
    """Synchronous door into run_pipeline, for the Celery task calling in."""
    return asyncio.run(run_pipeline(caller, units=units, template=template, store=store,
                                    should_stop=should_stop))
