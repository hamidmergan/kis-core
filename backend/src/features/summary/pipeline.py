"""Orchestrates one run: language, plan, sections, assembling, reporting throughout.

The plan is made over the numbered text of every source, each section is written from
the original passages it names. Every stage writes what it finished before the next one
starts, so a run that is handed back to the queue never pays twice for the same call.
"""

from __future__ import annotations

from typing import Callable, Protocol

from loguru import logger

from src.features.summary import concurrency, writing
from src.features.summary.models import LANGUAGE_FALLBACK, Caller, Outline, Section
from src.features.summary.templates import Template, template_body
from src.limits import (
    MAP_MATERIAL_MAX_CHARS,
    MAP_PASSAGE_NEIGHBOURS,
    SUMMARY_SECTION_BASE_CHARS,
    SUMMARY_SECTION_GROUP_CHARS,
    SUMMARY_SOURCE_OPENING_CHARS,
    SUMMARY_WRITE_CONCURRENCY,
)
from src.services import text_map as tm
from src.services.source_reading import Source
from src.services.text_language import language_name


class PipelineInterrupted(Exception):
    """The stage ran out of working time, what is done is saved, the rest follows."""


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


def detect_language(sources: list[Source]) -> str:
    """The language of the material, read locally. A text without one falls back."""
    return language_name("\n".join(q.text for q in sources[:1])) or LANGUAGE_FALLBACK


async def _themen(caller: Caller, nachrichten: list[dict], teil: int) -> str | None:
    """One part of the material boiled down to topics, None when the call failed."""
    try:
        antwort = await caller.create(messages=nachrichten, temperature=0.2, name=f"themen:{teil}",
                                      response_format={"type": "json_object"})
        return antwort.choices[0].message.content
    except Exception as e:  # noqa: BLE001 - a lost part costs its topics, not the run
        if concurrency.overloaded(e):
            raise
        logger.warning("Zusammenfassung: Themen von Teil {} nicht gelesen ({})", teil, e)
        return None


async def _grundlage(caller: Caller, karte: tm.Karte, language: str,
                     store: RunStore) -> tm.Grundlage:
    """What the planning call reads: the numbered text, or its topics when it is too long."""
    gemerkt = tm.grundlage_aus_dict(store.load_map(), karte)
    if gemerkt:
        return gemerkt
    if len(karte.teile(caller.window_tokens)) <= 1:
        g = tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[])
    else:
        stuecke = karte.abschnitte(caller.window_tokens)
        antworten = await concurrency.run_limited([
            lambda i=i, bereich=bereich, anzahl=anzahl: _themen(
                caller, tm.themen_nachrichten(karte, bereich, len(stuecke), i + 1, language,
                                              "a written summary", hoechstens=anzahl), i + 1)
            for i, (bereich, anzahl) in enumerate(stuecke)], SUMMARY_WRITE_CONCURRENCY)
        themen: list[tm.Thema] = []
        for antwort, (_, anzahl) in zip(antworten, stuecke):
            themen.extend(tm.parse_themen(antwort, karte, len(themen) + 1, hoechstens=anzahl))
        if not themen:
            raise RuntimeError("Aus keinem Teil des Materials liessen sich Themen gewinnen.")
        g = tm.Grundlage(material=tm.themen_block(themen), modus=tm.THEMEN, themen=themen)
    store.save_map(tm.grundlage_als_dict(g))
    logger.info("Zusammenfassung: {} Stellen, geplant ueber {}", len(karte),
                "den ganzen Text" if g.modus == tm.STELLEN else f"{len(g.themen)} Themen")
    return g


async def _outline(caller: Caller, *, language: str, vorlage: Template, sources: list[Source],
                   karte: tm.Karte, store: RunStore, instructions: str = "") -> Outline:
    """The plan, taken from the store when a stage already paid for it."""
    gemerkt = store.load_outline()
    if gemerkt:
        return Outline(**gemerkt)
    store.progress("outline")
    g = await _grundlage(caller, karte, language, store)

    async def planen(fehlt: list[str] | None) -> Outline:
        return await writing.plan_outline(
            caller, language=language, template_body=template_body(vorlage),
            sources=[q.dateiname for q in sources], material=g.material,
            target=writing.target_sections(sum(len(q.text) for q in sources) // 10,
                                           len(sources), vorlage.sections),
            modus=g.modus, stellen=lambda refs: g.stellen(refs, karte),
            span=vorlage.sections, fehlt=fehlt,
            anfaenge=[q.text[:SUMMARY_SOURCE_OPENING_CHARS] for q in sources],
            instructions=instructions)

    plan = await planen(None)
    # A plan that starves a file loses it for good, so it is asked for once more.
    luecken = tm.zu_kurz([a.stellen for a in plan.sections], karte) if len(sources) > 1 else []
    if plan.sections and luecken:
        hinweis = [f"{n} ({a} % of the material)" for n, a in luecken]
        logger.warning("Zusammenfassung: Plan gibt zu wenig Gewicht: {}", ", ".join(hinweis))
        zweiter = await planen(hinweis)
        if zweiter.sections and len(tm.zu_kurz([a.stellen for a in zweiter.sections],
                                                karte)) < len(luecken):
            plan = zweiter
    if plan.sections:
        vorher = tm.abdeckung([a.stellen for a in plan.sections], len(karte))
        eigene = tm.exklusiv([a.stellen for a in plan.sections])
        for abschnitt, genannt, stellen in zip(plan.sections, eigene,
                                               tm.abdecken(eigene, len(karte))):
            abschnitt.genannt, abschnitt.stellen = genannt, stellen
        logger.info("Zusammenfassung: Plan nennt {:.0%} der Stellen, der Rest geht an den "
                    "naechsten Abschnitt", vorher)
        store.save_outline(plan.model_dump())
    return plan


def _costs(sections: list[Section], je: int | None = None) -> list[int]:
    """What each section's prose is expected to cost, by the template or by its passages."""
    if je:
        return [je] * len(sections)
    return [SUMMARY_SECTION_BASE_CHARS + min(len(a.stellen), 10) * 150 for a in sections]


async def _sections(caller: Caller, *, language: str, vorlage: Template, plan: Outline,
                    karte: tm.Karte, store: RunStore, should_stop,
                    instructions: str = "") -> dict[int, str]:
    """Every section written from the original passages it names, several at once.

    A template whose closing answers the sections before it gets that closing written
    last, reading what the others wrote.
    """
    fertig = dict(store.load_sections())
    # A template with a length shares it out, about six characters make a word.
    je = vorlage.length_chars // len(plan.sections) if vorlage.length_chars else None
    worte = je // 6 if je else None
    gruppen = writing.group_sections(plan.sections, _costs(plan.sections, je),
                                     SUMMARY_SECTION_GROUP_CHARS)
    # Nur die offenen, ein bezahlter Abschnitt wird nie noch einmal geschrieben.
    offen = [[i for i in alle if i not in fertig] for alle in gruppen]
    schluss = offen.pop() if vorlage.closing_reads_document and offen else []
    offen = [gruppe for gruppe in offen if gruppe]

    async def schreibe(gruppe: list[int], geschrieben: list[tuple[str, str]] | None) -> None:
        abschnitte = [plan.sections[i] for i in gruppe]
        andere = [a for j, a in enumerate(plan.sections) if j not in gruppe]
        je = MAP_MATERIAL_MAX_CHARS // max(1, len(abschnitte))
        stoff = [karte.passagen(a.stellen, vorrang=a.genannt, nachbarn=MAP_PASSAGE_NEIGHBOURS,
                                budget=je)
                 for a in abschnitte]
        texte = await writing.write_sections(
            caller, language=language, template_body=template_body(vorlage),
            group=abschnitte, others=andere, written=geschrieben, material=stoff,
            budget=SUMMARY_SECTION_GROUP_CHARS, words=worte, names=plan.names,
            instructions=instructions)
        if texte is None:
            # One answer that cannot be cut apart costs calls, never a mixed up section.
            texte = []
            for i in gruppe:
                einzeln = await writing.write_sections(
                    caller, language=language, template_body=template_body(vorlage),
                    group=[plan.sections[i]], others=andere, written=geschrieben,
                    material=[stoff[gruppe.index(i)]], budget=SUMMARY_SECTION_GROUP_CHARS,
                    words=worte, names=plan.names, instructions=instructions)
                texte.append((einzeln or [""])[0])
        for i, text in zip(gruppe, texte):
            if text.strip():
                fertig[i] = text
                store.save_section(i, text)
        store.progress("section", len(fertig), len(plan.sections))

    darf = (lambda: not should_stop()) if should_stop else None
    store.progress("section", len(fertig), len(plan.sections))
    ergebnisse = await concurrency.run_limited(
        [lambda g=g: schreibe(g, None) for g in offen], SUMMARY_WRITE_CONCURRENCY, may_start=darf)
    if any(e is concurrency.SKIPPED for e in ergebnisse):
        raise PipelineInterrupted
    if schluss:
        geschrieben = [(plan.sections[i].title, fertig[i]) for i in sorted(fertig)]
        ergebnisse = await concurrency.run_limited(
            [lambda: schreibe(schluss, geschrieben)], 1, may_start=darf)
        if any(e is concurrency.SKIPPED for e in ergebnisse):
            raise PipelineInterrupted
    return fertig


async def run(caller: Caller, *, sources: list[Source], template: Template,
              store: RunStore, should_stop: Callable[[], bool] | None = None,
              instructions: str = "") -> str:
    """One whole run, from the read sources to the finished document."""
    language = store.load_language()
    if not language:
        language = detect_language(sources)
        store.save_language(language)

    karte = tm.Karte(sources)
    if not len(karte):
        raise RuntimeError("Keine Quelle traegt Text.")

    plan = await _outline(caller, language=language, vorlage=template, sources=sources,
                          karte=karte, store=store, instructions=instructions)
    if not plan.sections:
        # Without a plan the document comes out of one call, that is the fallback.
        return await writing.compose_single(
            caller, language=language, template_body=template_body(template),
            sources=[q.dateiname for q in sources],
            material=karte.block()[:MAP_MATERIAL_MAX_CHARS * 4], instructions=instructions)

    fertig = await _sections(caller, language=language, vorlage=template, plan=plan,
                             karte=karte, store=store, should_stop=should_stop,
                             instructions=instructions)
    reihenfolge = sorted(fertig)
    return writing.assemble(plan.intro, [plan.sections[i].title for i in reihenfolge],
                            [fertig[i] for i in reihenfolge], template.headings, plan.title)
