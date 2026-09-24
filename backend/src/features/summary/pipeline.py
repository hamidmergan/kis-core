"""Orchestrates one run: language, plan, sections, assembling, reporting throughout.

The plan is made over the numbered text of every source, each section is written from
the original passages it names. Every stage writes what it finished before the next one
starts, so a run that is handed back to the queue never pays twice for the same call.
"""

from __future__ import annotations

import asyncio
import re
from typing import Callable, Protocol

from loguru import logger

from src.features.summary import writing
from src.features.summary.models import LANGUAGE_FALLBACK, Caller, Outline, Section
from src.features.summary.templates import Template, template_body
from src.limits import (
    MAP_MATERIAL_MAX_CHARS,
    MAP_PASSAGE_NEIGHBOURS,
    SUMMARY_SECTION_BASE_CHARS,
    SUMMARY_SECTION_GROUP_CHARS,
)
from src.services import text_map as tm
from src.services.source_reading import Source


class PipelineInterrupted(Exception):
    """The stage ran out of working time, what is done is saved, the rest follows."""


_LANGUAGE_SAMPLE_CHARS = 1500
# Below this the guess is noise, a file name or a page number is not a language.
_LANGUAGE_MIN_CHARS = 80
_LANGUAGE_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ -][^\W\d_]+)?$", re.UNICODE)


class RunStore(Protocol):
    """Everything of one run that outlives a single attempt."""

    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None: ...
    def load_map(self) -> dict | None: ...
    def save_map(self, daten: dict) -> None: ...

    def load_language(self) -> str | None: ...
    def save_language(self, language: str) -> None: ...
    def load_outline(self) -> dict | None: ...
    def save_outline(self, outline: dict) -> None: ...
    def load_sections(self) -> dict[int, str]: ...
    def save_section(self, index: int, text: str) -> None: ...


def language_sample(text: str, sample_chars: int = _LANGUAGE_SAMPLE_CHARS) -> str:
    """An excerpt from the middle as a language sample, the edges mislead."""
    if len(text) <= sample_chars:
        return " ".join(text.split())
    mitte = len(text) // 2
    koerper = " ".join(text[max(0, mitte - sample_chars): mitte + sample_chars].split())
    if len(koerper) <= sample_chars:
        return koerper
    # Aus der Mitte heraus gekuerzt, sonst faellt genau die Mitte wieder weg.
    start = (len(koerper) - sample_chars) // 2
    return koerper[start:start + sample_chars]


def clean_language_name(raw: str | None) -> str | None:
    """Reduces a probe answer to a bare language name, or None if it is not one."""
    name = " ".join((raw or "").split()).strip(" .\"'")
    if not name or len(name) > 30 or not _LANGUAGE_NAME_RE.match(name):
        return None
    return name


async def detect_language(caller: Caller, sources: list[Source]) -> str:
    """The language of the material, asked once. A useless answer falls back."""
    probe = language_sample("\n".join(q.text for q in sources[:1]))
    if len(probe) < _LANGUAGE_MIN_CHARS:
        return LANGUAGE_FALLBACK
    try:
        antwort = await caller.create(
            messages=[
                {"role": "system", "content": "Name the language of the text in one English "
                                              "word. Answer with that word only."},
                {"role": "user", "content": f"/no_think\n{probe}"},
            ],
            temperature=0.0, name="language", max_tokens=16,
        )
        return clean_language_name(antwort.choices[0].message.content) or LANGUAGE_FALLBACK
    except Exception as e:  # noqa: BLE001 - without a name the fallback still describes it
        logger.warning("Zusammenfassung: Sprache nicht erkennbar ({})", e)
        return LANGUAGE_FALLBACK


async def _themen(caller: Caller, nachrichten: list[dict], teil: int) -> str | None:
    """One part of the material boiled down to topics, None when the call failed."""
    try:
        antwort = await caller.create(messages=nachrichten, temperature=0.2, name=f"themen:{teil}",
                                      response_format={"type": "json_object"})
        return antwort.choices[0].message.content
    except Exception as e:  # noqa: BLE001 - a lost part costs its topics, not the run
        logger.warning("Zusammenfassung: Themen von Teil {} nicht gelesen ({})", teil, e)
        return None


async def _grundlage(caller: Caller, karte: tm.Karte, language: str,
                     store: RunStore) -> tm.Grundlage:
    """What the planning call reads: the numbered text, or its topics when it is too long."""
    gemerkt = tm.grundlage_aus_dict(store.load_map(), karte)
    if gemerkt:
        return gemerkt
    teile = karte.teile(caller.window_tokens)
    if len(teile) <= 1:
        g = tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[])
    else:
        antworten = await asyncio.gather(*(
            _themen(caller, tm.themen_nachrichten(karte, teil, len(teile), i + 1, language,
                                                  "a written summary"), i + 1)
            for i, teil in enumerate(teile)))
        themen: list[tm.Thema] = []
        for antwort in antworten:
            themen.extend(tm.parse_themen(antwort, karte, len(themen) + 1))
        if not themen:
            raise RuntimeError("Aus keinem Teil des Materials liessen sich Themen gewinnen.")
        g = tm.Grundlage(material=tm.themen_block(themen), modus=tm.THEMEN, themen=themen)
    store.save_map(tm.grundlage_als_dict(g))
    logger.info("Zusammenfassung: {} Stellen, geplant ueber {}", len(karte),
                "den ganzen Text" if g.modus == tm.STELLEN else f"{len(g.themen)} Themen")
    return g


async def _outline(caller: Caller, *, language: str, vorlage: Template, sources: list[Source],
                   karte: tm.Karte, store: RunStore) -> Outline:
    """The plan, taken from the store when a stage already paid for it."""
    gemerkt = store.load_outline()
    if gemerkt:
        return Outline(**gemerkt)
    store.progress("plan")
    g = await _grundlage(caller, karte, language, store)
    plan = await writing.plan_outline(
        caller, language=language, template_body=template_body(vorlage),
        sources=[q.dateiname for q in sources], material=g.material,
        target=writing.target_sections(sum(len(q.text) for q in sources) // 10, len(sources)),
        modus=g.modus, stellen=lambda refs: g.stellen(refs, karte))
    if plan.sections:
        vorher = tm.abdeckung([a.stellen for a in plan.sections], len(karte))
        voll = tm.abdecken([a.stellen for a in plan.sections], len(karte))
        for abschnitt, stellen in zip(plan.sections, voll):
            abschnitt.stellen = stellen
        logger.info("Zusammenfassung: Plan nennt {:.0%} der Stellen, der Rest geht an den "
                    "naechsten Abschnitt", vorher)
        store.save_outline(plan.model_dump())
    return plan


def _costs(sections: list[Section]) -> list[int]:
    """What each section's prose is expected to cost, by the passages it carries."""
    return [SUMMARY_SECTION_BASE_CHARS + min(len(a.stellen), 10) * 150 for a in sections]


async def _sections(caller: Caller, *, language: str, vorlage: Template, plan: Outline,
                    karte: tm.Karte, store: RunStore, should_stop) -> dict[int, str]:
    """Every section written from the original passages it names."""
    fertig = dict(store.load_sections())
    gruppen = writing.group_sections(plan.sections, _costs(plan.sections),
                                     SUMMARY_SECTION_GROUP_CHARS)
    for alle in gruppen:
        # Nur die offenen, ein bezahlter Abschnitt wird nie noch einmal geschrieben.
        gruppe = [i for i in alle if i not in fertig]
        if not gruppe:
            continue
        if should_stop and should_stop():
            raise PipelineInterrupted
        store.progress("schreiben", len(fertig), len(plan.sections))
        abschnitte = [plan.sections[i] for i in gruppe]
        je = MAP_MATERIAL_MAX_CHARS // max(1, len(abschnitte))
        stoff = [karte.passagen(a.stellen, nachbarn=MAP_PASSAGE_NEIGHBOURS, budget=je)
                 for a in abschnitte]
        geschrieben = [(plan.sections[i].title, fertig[i]) for i in sorted(fertig)]
        texte = await writing.write_sections(
            caller, language=language, template_body=template_body(vorlage),
            group=abschnitte, others=[a for j, a in enumerate(plan.sections) if j not in gruppe],
            written=geschrieben, material=stoff, budget=SUMMARY_SECTION_GROUP_CHARS)
        if texte is None:
            # One answer that cannot be cut apart costs calls, never a mixed up section.
            texte = []
            for i in gruppe:
                einzeln = await writing.write_sections(
                    caller, language=language, template_body=template_body(vorlage),
                    group=[plan.sections[i]], others=[], written=geschrieben,
                    material=[stoff[gruppe.index(i)]], budget=SUMMARY_SECTION_GROUP_CHARS)
                texte.append((einzeln or [""])[0])
        for i, text in zip(gruppe, texte):
            if text.strip():
                fertig[i] = text
                store.save_section(i, text)
    return fertig


async def run(caller: Caller, *, sources: list[Source], template: Template,
              store: RunStore, should_stop: Callable[[], bool] | None = None) -> str:
    """One whole run, from the read sources to the finished document."""
    language = store.load_language()
    if not language:
        language = await detect_language(caller, sources)
        store.save_language(language)

    karte = tm.Karte(sources)
    if not len(karte):
        raise RuntimeError("Keine Quelle traegt Text.")

    plan = await _outline(caller, language=language, vorlage=template, sources=sources,
                          karte=karte, store=store)
    if not plan.sections:
        # Without a plan the document comes out of one call, that is the fallback.
        return await writing.compose_single(
            caller, language=language, template_body=template_body(template),
            sources=[q.dateiname for q in sources],
            material=karte.block()[:MAP_MATERIAL_MAX_CHARS * 4])

    fertig = await _sections(caller, language=language, vorlage=template, plan=plan,
                             karte=karte, store=store, should_stop=should_stop)
    reihenfolge = sorted(fertig)
    return writing.assemble(plan.intro, [plan.sections[i].title for i in reihenfolge],
                            [fertig[i] for i in reihenfolge], template.headings, plan.title)
