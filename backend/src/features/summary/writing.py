"""Writing phase: plan the outline from the material, write section by section, assemble."""

import asyncio
import json
import re

from loguru import logger

from src.features.summary.models import GROUND_RULES, Caller, Outline, Section
from src.features.summary.reading import cut_to_last_line
from src.limits import (
    SUMMARY_CHARS_PER_SECTION,
    SUMMARY_MAX_SECTIONS,
    SUMMARY_MIN_SECTIONS,
    SUMMARY_OUTLINE_MAX_ATTEMPTS,
    SUMMARY_PROMPT_RESERVE_CHARS,
    SUMMARY_RETRY_DELAY_SECONDS,
    SUMMARY_WRITE_MAX_TOKENS,
)


def target_sections(facts_chars: int) -> int:
    """How many sections the material carries, a target the planner may deviate from."""
    return max(SUMMARY_MIN_SECTIONS, min(SUMMARY_MAX_SECTIONS,
                                         facts_chars // SUMMARY_CHARS_PER_SECTION))


def _strip_thinking(raw: str | None) -> str:
    """Drops a leading thinking block and a fenced wrapper some models add."""
    antwort = (raw or "").strip()
    if antwort.startswith("<think>"):
        ende = antwort.find("</think>")
        if ende != -1:
            antwort = antwort[ende + len("</think>"):].strip()
    if antwort.startswith("```"):
        ohne_zaun = antwort.split("\n", 1)
        if len(ohne_zaun) == 2:
            antwort = ohne_zaun[1].rsplit("```", 1)[0].strip()
    return antwort


def parse_outline(raw: str | None) -> Outline:
    """Reads the planning answer, a broken one yields no sections rather than an error."""
    text = _strip_thinking(raw)
    treffer = re.search(r"\{.*\}", text, re.S)
    if not treffer:
        return Outline()
    try:
        roh = json.loads(treffer.group(0))
    except ValueError:
        return Outline()
    rohe = roh.get("sections")
    if rohe is not None and not isinstance(rohe, list):
        return Outline()
    abschnitte: list[Section] = []
    for eintrag in rohe or []:
        titel = (eintrag.get("title") if isinstance(eintrag, dict) else eintrag) or ""
        umfang = (eintrag.get("scope") if isinstance(eintrag, dict) else "") or ""
        titel = " ".join(str(titel).split()).lstrip("#").strip()
        if not titel or len(titel) > 120:
            continue
        if any(a.title.casefold() == titel.casefold() for a in abschnitte):
            continue
        abschnitte.append(Section(title=titel, scope=" ".join(str(umfang).split())))
    if len(abschnitte) < SUMMARY_MIN_SECTIONS:
        return Outline()
    return Outline(intro=str(roh.get("intro") or "").strip(),
                   sections=abschnitte[:SUMMARY_MAX_SECTIONS])


def _parts_block(part_note: str) -> str:
    """Tells a call which sources are excerpts of one file, empty when none are."""
    if not part_note:
        return ""
    return (
        "\nPARTS OF ONE FILE\n"
        "Each line names one file that was read in excerpts. The excerpts of a line are ONE "
        "source. Never give an excerpt a section of its own, never name an excerpt or a part "
        "number anywhere, and where two excerpts say the same thing, say it once.\n"
        f"{part_note}\n"
    )


def _outline_system(language: str, template_body: str, part_note: str, target: int) -> str:
    return (
        "You plan the structure of a document. The facts you read are working material, "
        "the reader never sees them.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Derive every section from what the material carries. Never fall back on a "
        "generic scaffold such as introduction, main part, conclusion.\n"
        f"Rule 9: Plan around {target} sections, between {SUMMARY_MIN_SECTIONS} and "
        f"{SUMMARY_MAX_SECTIONS}. Thin material gets fewer, rich material gets more.\n"
        "Rule 10: Sections must not overlap, every fact belongs under exactly one heading.\n"
        "Rule 11: Plan the sections the BUILD PLAN below asks for. Where it names parts the "
        "result must have, such as a quiz, an answer key or a glossary, each is a section of "
        "its own, and a part that answers another one comes after it.\n"
        "Rule 12: Answer as a JSON object with two keys and nothing else, no code fence:\n"
        '  "intro": two to four sentences naming the subject and its most important takeaways\n'
        '  "sections": a list of objects, each with "title" (a short noun phrase) and "scope" '
        "(one sentence saying what belongs in it and what does not)\n"
        + _parts_block(part_note)
        + "\nBUILD PLAN\n" + template_body
    )


def _sources_and_facts(sources: list[str], facts: str, several_note: str = "") -> str:
    liste = "\n".join(f"- {s}" for s in sources)
    return f"/no_think\nSources:\n{liste}\n\n{several_note}Facts:\n\n{facts}"


async def plan_outline(caller: Caller, *, language: str, template_body: str,
                       sources: list[str], facts: str, part_note: str, target: int) -> Outline:
    """Plans the sections, an unusable answer yields an empty outline."""
    for versuch in range(1, SUMMARY_OUTLINE_MAX_ATTEMPTS + 1):
        try:
            antwort = await caller.create(
                messages=[
                    {"role": "system",
                     "content": _outline_system(language, template_body, part_note, target)},
                    {"role": "user", "content": _sources_and_facts(sources, facts)},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            plan = parse_outline(antwort.choices[0].message.content)
            if plan.sections:
                return plan
            logger.warning("Zusammenfassung: Gliederung {} unlesbar", versuch)
        except Exception as e:  # noqa: BLE001 - the single call still saves the run
            logger.warning("Zusammenfassung: Planungsaufruf {} gescheitert ({})", versuch, e)
        if versuch < SUMMARY_OUTLINE_MAX_ATTEMPTS:
            await asyncio.sleep(SUMMARY_RETRY_DELAY_SECONDS)
    return Outline()


def _finished(antwort) -> str:
    """The written text, a half line the cap cut off is dropped."""
    wahl = antwort.choices[0]
    text = _strip_thinking(wahl.message.content)
    if getattr(wahl, "finish_reason", None) == "length":
        text = cut_to_last_line(text)
    if not text:
        raise RuntimeError("Das Modell hat nichts geantwortet.")
    return text


def _section_system(language: str, template_body: str, part_note: str) -> str:
    return (
        "You write ONE section of a larger document. The sections before yours are already "
        "written and given to you, the ones after yours come later.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Write only what belongs under your own heading. The scopes of the sections "
        "still to come are listed so you stay off their ground. Never announce what comes later.\n"
        "Rule 9: Continue the document you are given, never repeat what it already says. Where "
        "your section answers or builds on an earlier one, make the two match item for item.\n"
        "Rule 10: Go as deep as the facts allow. A Markdown table where things are compared "
        "along the same attributes, bullet points where it is a list, numbered items where "
        "order or count matters, continuous text where it is an argument.\n"
        "Rule 11: A figure, a date or a quantity never stands without what it refers to, and "
        "you carry over every one the facts state for your heading.\n"
        "Rule 12: What the material marks as open or disputed stays in, marked as such.\n"
        "Rule 13: Do not repeat your own heading. Begin with the content, write no closing remark.\n"
        "Rule 14: Never cite a page, a slide or a position the facts do not state.\n"
        + _parts_block(part_note)
        + "\nThe document as a whole follows the build plan below. Match its register, but "
        "produce ONLY your own section.\n\nBUILD PLAN\n" + template_body
    )


def _section_user(section: Section, others: list[Section],
                  written: list[tuple[str, str]], facts: str) -> str:
    fremd = "\n".join(f"- {a.title}: {a.scope}" for a in others) or "- none"
    bisher = "\n\n".join(f"## {titel}\n{text}" for titel, text in written) \
        or "(nothing yet, yours is the first section)"
    if len(bisher) > SUMMARY_PROMPT_RESERVE_CHARS:
        # The headings stay in full, the oldest prose goes, the newest is what matters.
        koepfe = "\n".join(f"## {titel}" for titel, _ in written)
        # A negative budget must drop all prose, not wrap into a slice from the front.
        uebrig = max(0, SUMMARY_PROMPT_RESERVE_CHARS - len(koepfe))
        rest = bisher[-uebrig:] if uebrig else ""
        bisher = f"{koepfe}\n\n[...]\n{rest}"
    return (
        "/no_think\n"
        f"YOUR HEADING: {section.title}\nYOUR SCOPE: {section.scope}\n\n"
        f"Still to be written by others, stay off these:\n{fremd}\n\n"
        f"THE DOCUMENT SO FAR:\n{bisher}\n\nFacts:\n\n{facts}"
    )


async def write_section(caller: Caller, *, language: str, template_body: str,
                        section: Section, others: list[Section],
                        written: list[tuple[str, str]], facts: str, part_note: str) -> str:
    """Writes one section, seeing everything written before it."""
    antwort = await caller.create(
        messages=[
            {"role": "system", "content": _section_system(language, template_body, part_note)},
            {"role": "user", "content": _section_user(section, others, written, facts)},
        ],
        temperature=0.3,
        max_tokens=SUMMARY_WRITE_MAX_TOKENS,
    )
    return _finished(antwort)


def _compose_system(language: str, template_body: str, part_note: str) -> str:
    return (
        "You write the finished document from facts drawn out of several sources.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Begin immediately with the content, no framing sentence, no closing remark.\n"
        "Rule 9: Follow the build plan below exactly, it decides the shape. About "
        "faithfulness, the rules above win.\n"
        "Rule 10: A figure, a date or a quantity never stands without what it refers to.\n"
        "Rule 11: What the material marks as open or disputed stays in, marked.\n"
        "Rule 12: Never cite a page, a slide or a position the facts do not state.\n"
        + _parts_block(part_note)
        + "\nBUILD PLAN\n" + template_body
    )


async def compose_single(caller: Caller, *, language: str, template_body: str,
                         sources: list[str], facts: str, part_note: str) -> str:
    """The whole document in one call, the fallback for a failed outline."""
    mehrere = (
        "The facts come from several sources. Write ONE document covering all of them "
        "together. Never produce one section per source unless the build plan asks.\n"
        if len(sources) > 1 else ""
    )
    antwort = await caller.create(
        messages=[
            {"role": "system", "content": _compose_system(language, template_body, part_note)},
            {"role": "user", "content": _sources_and_facts(sources, facts, mehrere)},
        ],
        temperature=0.3,
        max_tokens=SUMMARY_WRITE_MAX_TOKENS,
    )
    return _finished(antwort)


def assemble(intro: str, titles: list[str], texts: list[str], headings: bool) -> str:
    """Joins the written sections, with or without their headings."""
    teile = [intro.strip()] if intro.strip() else []
    for titel, text in zip(titles, texts):
        koerper = (text or "").strip()
        if not koerper:
            continue
        teile.append(f"## {titel}\n\n{koerper}" if headings else koerper)
    return "\n\n".join(teile)
