"""Orchestrates one run: language, facts, plan, sections, assembling, reporting throughout.

Every stage writes what it finished before the next one starts, so a run that is handed
back to the queue never pays twice for the same call.
"""

from __future__ import annotations

import re
from typing import Callable, Protocol

from loguru import logger

from src.features.summary import writing
from src.features.summary.models import LANGUAGE_FALLBACK, Caller, Outline, Section
from src.features.summary.templates import Template, template_body
from src.limits import SUMMARY_SECTION_BASE_CHARS, SUMMARY_SECTION_GROUP_CHARS
from src.services import facts as fk
from src.services import facts_reading as fr
from src.services.source_reading import Source

# The read phase hands a stage back the same way the summary always did.
PipelineInterrupted = fr.RunInterrupted

_LANGUAGE_SAMPLE_CHARS = 1500
# Below this the guess is noise, a file name or a page number is not a language.
_LANGUAGE_MIN_CHARS = 80
_LANGUAGE_NAME_RE = re.compile(r"^[^\W\d_]+(?:[ -][^\W\d_]+)?$", re.UNICODE)


class RunStore(fr.FactStore, Protocol):
    """Everything of one run that outlives a single attempt."""

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


async def _facts(caller: Caller, sources: list[Source], language: str, store: RunStore,
                 should_stop) -> list[fk.Fact]:
    """Every source read into facts, the numbered pool of what they gave up."""
    teile = fr.plan_slices(sources, fr.slice_chars(caller.window_tokens))
    logger.info("Zusammenfassung: {} Quelle(n) in {} Leseaufruf(en)", len(sources), len(teile))

    async def _lesen(teil: fr.Slice):
        return await fr.read_slice(caller.client, caller.model, teil=teil, sources=sources,
                                   language=language, book=caller.book)

    gelesen = await fr.map_slices(teile, read=_lesen, store=store, should_stop=should_stop)
    vorrat = fk.build_pool(fr.by_source(gelesen, teile, len(sources)))
    logger.info("Zusammenfassung: {} Aussagen im Vorrat", len(vorrat))
    return vorrat


async def _outline(caller: Caller, *, language: str, vorlage: Template, sources: list[Source],
                   vorrat: list[fk.Fact], store: RunStore) -> Outline:
    """The plan, taken from the store when a stage already paid for it."""
    gemerkt = store.load_outline()
    if gemerkt:
        return Outline(**gemerkt)
    store.progress("plan")
    plan = await writing.plan_outline(
        caller, language=language, template_body=template_body(vorlage),
        sources=[q.dateiname for q in sources], material=fk.pool_block(vorrat),
        target=writing.target_sections(sum(len(f.fact) for f in vorrat), len(sources)))
    if plan.sections:
        store.save_outline(plan.model_dump())
    return plan


def _costs(sections: list[Section]) -> list[int]:
    """What each section's prose is expected to cost, by the facts it carries."""
    return [SUMMARY_SECTION_BASE_CHARS + len(a.fact_ids) * 160 for a in sections]


async def _sections(caller: Caller, *, language: str, vorlage: Template, plan: Outline,
                    vorrat: list[fk.Fact], sources: list[Source], store: RunStore,
                    should_stop) -> dict[int, str]:
    """Every section written from its own facts and the passages they come from."""
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
        stoff = []
        for abschnitt in abschnitte:
            eigene = fk.facts_for(abschnitt.fact_ids, vorrat)
            belege = "\n".join(f"- {f.fact} Beleg: \"{f.citation}\"" for f in eigene)
            umgebung = fk.context_for(eigene, sources)
            stoff.append(f"{belege}\n\nPASSAGES\n{umgebung}" if umgebung else belege)
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

    vorrat = await _facts(caller, sources, language, store, should_stop)
    if not vorrat:
        raise RuntimeError("Aus keiner Quelle liessen sich Aussagen herausziehen.")

    plan = await _outline(caller, language=language, vorlage=template, sources=sources,
                          vorrat=vorrat, store=store)
    if not plan.sections:
        # Without a plan the whole document comes out of one call, that is the fallback.
        return await writing.compose_single(
            caller, language=language, template_body=template_body(template),
            sources=[q.dateiname for q in sources], material=fk.pool_block(vorrat))

    fertig = await _sections(caller, language=language, vorlage=template, plan=plan,
                             vorrat=vorrat, sources=sources, store=store,
                             should_stop=should_stop)
    reihenfolge = sorted(fertig)
    return writing.assemble(plan.intro, [plan.sections[i].title for i in reihenfolge],
                            [fertig[i] for i in reihenfolge], template.headings, plan.title)
