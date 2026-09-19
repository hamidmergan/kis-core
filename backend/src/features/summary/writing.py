"""Writing phase: plan the outline over the fact pool, write section by section, assemble."""

import asyncio
import json
import re

from loguru import logger

from src.features.summary.facts import Fact, facts_block, facts_for, source_names
from src.features.summary.models import GROUND_RULES, Caller, Outline, Section
from src.limits import (
    SUMMARY_CHARS_PER_SECTION,
    SUMMARY_MAX_SECTIONS,
    SUMMARY_MIN_FACT_COVERAGE,
    SUMMARY_MIN_SECTIONS,
    SUMMARY_OUTLINE_MAX_ATTEMPTS,
    SUMMARY_PROMPT_RESERVE_CHARS,
    SUMMARY_RETRY_DELAY_SECONDS,
    SUMMARY_WRITE_MAX_TOKENS,
)

OUTLINE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "outline",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "intro": {
                    "type": "string",
                    "description": (
                        "Two to four sentences naming the subject and its most important "
                        "takeaways, in the output language."
                    ),
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "section_index": {"type": "integer"},
                            "title": {"type": "string",
                                      "description": "A short noun phrase, no numbering."},
                            "description": {
                                "type": "string",
                                "description": "One sentence on what belongs in it and what does not.",
                            },
                            "fact_ids": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "The numbers of the facts this section is written from.",
                            },
                        },
                        "required": ["section_index", "title", "description", "fact_ids"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["intro", "sections"],
            "additionalProperties": False,
        },
    },
}


def target_sections(facts_chars: int) -> int:
    """How many sections the material carries, a target the planner may deviate from."""
    return max(SUMMARY_MIN_SECTIONS, min(SUMMARY_MAX_SECTIONS,
                                         facts_chars // SUMMARY_CHARS_PER_SECTION))


def cut_to_last_line(text: str) -> str:
    """Drops a line the cap cut in half, unless that would drop most of the text."""
    schnitt = text.rfind("\n")
    return text[:schnitt].rstrip() if schnitt > len(text) // 2 else text


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


def parse_outline(raw: str | None, known_ids: set[int] | None = None) -> Outline:
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
    # A fact belongs to exactly one section, so a second mention of it is dropped.
    vergeben: set[int] = set()
    for eintrag in rohe or []:
        titel = (eintrag.get("title") if isinstance(eintrag, dict) else eintrag) or ""
        umfang = (eintrag.get("scope") or eintrag.get("description")
                  if isinstance(eintrag, dict) else "") or ""
        titel = " ".join(str(titel).split()).lstrip("#").strip()
        if not titel or len(titel) > 120:
            continue
        if any(a.title.casefold() == titel.casefold() for a in abschnitte):
            continue
        nummern = _fact_ids(eintrag, known_ids, vergeben)
        vergeben.update(nummern)
        abschnitte.append(Section(title=titel, scope=" ".join(str(umfang).split()),
                                  fact_ids=nummern))
    if len(abschnitte) < SUMMARY_MIN_SECTIONS:
        return Outline()
    return Outline(intro=str(roh.get("intro") or "").strip(),
                   sections=abschnitte[:SUMMARY_MAX_SECTIONS])


def _fact_ids(eintrag, known_ids: set[int] | None, taken: set[int]) -> list[int]:
    """The numbers of one section, without unknown ones and without repeats."""
    if not isinstance(eintrag, dict):
        return []
    nummern: list[int] = []
    for roh in eintrag.get("fact_ids") or []:
        try:
            nummer = int(roh)
        except (TypeError, ValueError):
            continue
        if nummer in taken or nummer in nummern:
            continue
        if known_ids is not None and nummer not in known_ids:
            continue
        nummern.append(nummer)
    return nummern


def coverage(outline: Outline, pool: list[Fact]) -> float:
    """The share of the pool the outline actually put somewhere."""
    if not pool:
        return 1.0
    vergeben = {n for a in outline.sections for n in a.fact_ids}
    return len(vergeben) / len(pool)


def _outline_system(language: str, template_body: str, target: int) -> str:
    return (
        "You plan the structure of a document. The facts you read are working material, "
        "the reader never sees them as a list.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Derive every section from what the material carries. Never fall back on a "
        "generic scaffold such as introduction, main part, conclusion.\n"
        f"Rule 9: Plan around {target} sections, between {SUMMARY_MIN_SECTIONS} and "
        f"{SUMMARY_MAX_SECTIONS}. Thin material gets fewer, rich material gets more.\n"
        "Rule 10: Sections must not overlap, every fact belongs under exactly one heading.\n"
        "Rule 11: Assign EVERY fact number to exactly one section. A number you leave out is "
        "content the reader never gets. Never invent a number that is not in the list.\n"
        "Rule 12: The facts come from several files and the sections follow the subject, "
        "never the file a fact came from.\n"
        "Rule 13: Plan the sections the BUILD PLAN below asks for. Where it names parts the "
        "result must have, such as a quiz, an answer key or a glossary, each is a section of "
        "its own, and a part that answers another one comes after it.\n"
        "\nBUILD PLAN\n" + template_body
    )


def _outline_user(sources: list[str], pool_text: str) -> str:
    liste = "\n".join(f"- {s}" for s in sources)
    return f"/no_think\nSources:\n{liste}\n\nFacts, one per line, numbered:\n\n{pool_text}"


async def plan_outline(caller: Caller, *, language: str, template_body: str,
                       sources: list[str], pool: list[Fact], pool_text: str,
                       target: int) -> Outline:
    """Plans the sections, an unusable answer yields an empty outline."""
    bekannt = {f.fact_id for f in pool}
    beste = Outline()
    for versuch in range(1, SUMMARY_OUTLINE_MAX_ATTEMPTS + 1):
        try:
            antwort = await caller.create(
                messages=[
                    {"role": "system", "content": _outline_system(language, template_body, target)},
                    {"role": "user", "content": _outline_user(sources, pool_text)},
                ],
                temperature=0.2, name=f"outline:{versuch}",
                response_format=OUTLINE_SCHEMA,
            )
            plan = parse_outline(antwort.choices[0].message.content, bekannt)
            if plan.sections:
                if coverage(plan, pool) > coverage(beste, pool) or not beste.sections:
                    beste = plan
                anteil = coverage(beste, pool)
                if anteil >= SUMMARY_MIN_FACT_COVERAGE:
                    return beste
                logger.warning("Zusammenfassung: Gliederung deckt nur {:.0%} der Fakten ab",
                               anteil)
            else:
                logger.warning("Zusammenfassung: Gliederung {} unlesbar", versuch)
        except Exception as e:  # noqa: BLE001 - the single call still saves the run
            logger.warning("Zusammenfassung: Planungsaufruf {} gescheitert ({})", versuch, e)
        if versuch < SUMMARY_OUTLINE_MAX_ATTEMPTS:
            await asyncio.sleep(SUMMARY_RETRY_DELAY_SECONDS)
    if beste.sections:
        offen = len(pool) - len({n for a in beste.sections for n in a.fact_ids})
        if offen:
            logger.warning("Zusammenfassung: {} von {} Fakten bleiben unbenutzt",
                           offen, len(pool))
    return beste


def _finished(antwort) -> str:
    """The written text, a half line the cap cut off is dropped."""
    wahl = antwort.choices[0]
    text = _strip_thinking(wahl.message.content)
    if getattr(wahl, "finish_reason", None) == "length":
        text = cut_to_last_line(text)
    if not text:
        raise RuntimeError("Das Modell hat nichts geantwortet.")
    return text


def _drop_leading_heading(text: str) -> str:
    """Cuts one leading Markdown heading, the rule against it is a request, not a guarantee."""
    zeilen = text.split("\n")
    if not zeilen or not re.match(r"^#{1,6}\s+\S", zeilen[0]):
        return text
    zeilen = zeilen[1:]
    while zeilen and not zeilen[0].strip():
        zeilen.pop(0)
    return "\n".join(zeilen)


def _marker_rule(names: list[str]) -> str:
    """The rule that puts the file a statement came from next to the statement."""
    if not names:
        return ""
    liste = ", ".join(f"[{n}]" for n in names)
    return (
        "Rule 15: Every fact below carries its file in square brackets. Put that marker "
        "behind the statement it belongs to, before the closing punctuation, exactly as it "
        f"is written. The markers of your facts are: {liste}. Never invent another one and "
        "never collect them at the end.\n"
    )


def _section_system(language: str, template_body: str, names: list[str]) -> str:
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
        "Rule 13: Do not repeat your own heading. Begin with the content, write no closing "
        "remark and no greeting.\n"
        "Rule 14: Never cite a page, a slide or a position the facts do not state. The "
        "citations in the facts are your proof, never quote them as a block.\n"
        + _marker_rule(names)
        + "\nThe document as a whole follows the build plan below. Match its register, but "
        "produce ONLY your own section.\n\nBUILD PLAN\n" + template_body
    )


def _document_so_far(written: list[tuple[str, str]]) -> str:
    """The sections already written, the newest in full, the oldest dropped when it is tight."""
    bisher = "\n\n".join(f"## {titel}\n{text}" for titel, text in written) \
        or "(nothing yet, yours is the first section)"
    if len(bisher) <= SUMMARY_PROMPT_RESERVE_CHARS:
        return bisher
    # The headings stay in full, the oldest prose goes, the newest is what matters.
    koepfe = "\n".join(f"## {titel}" for titel, _ in written)
    uebrig = max(0, SUMMARY_PROMPT_RESERVE_CHARS - len(koepfe))
    rest = bisher[-uebrig:] if uebrig else ""
    return f"{koepfe}\n\n[...]\n{rest}"


def _section_user(section: Section, others: list[Section],
                  written: list[tuple[str, str]], facts: str) -> str:
    fremd = "\n".join(f"- {a.title}: {a.scope}" for a in others) or "- none"
    return (
        "/no_think\n"
        f"YOUR HEADING: {section.title}\nYOUR SCOPE: {section.scope}\n\n"
        f"Still to be written by others, stay off these:\n{fremd}\n\n"
        f"THE DOCUMENT SO FAR:\n{_document_so_far(written)}\n\n"
        f"YOUR FACTS:\n\n{facts}"
    )


async def write_section(caller: Caller, *, language: str, template_body: str,
                        section: Section, others: list[Section],
                        written: list[tuple[str, str]], facts: list[Fact],
                        budget: int) -> str:
    """Writes one section from its own facts, seeing everything written before it."""
    antwort = await caller.create(
        messages=[
            {"role": "system",
             "content": _section_system(language, template_body, source_names(facts))},
            {"role": "user",
             "content": _section_user(section, others, written, facts_block(facts, budget))},
        ],
        temperature=0.3, name=f"section:{section.title}",
        max_tokens=SUMMARY_WRITE_MAX_TOKENS,
    )
    # Cut here, not in assemble: a stored or re-shown heading would keep teaching the pattern back.
    text = _drop_leading_heading(_finished(antwort))
    if not text:
        raise RuntimeError("Das Modell hat nichts geantwortet.")
    return text


def _compose_system(language: str, template_body: str, names: list[str]) -> str:
    return (
        "You write the finished document from facts drawn out of several sources.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Begin immediately with the content, no framing sentence, no closing remark.\n"
        "Rule 9: Follow the build plan below exactly, it decides the shape. About "
        "faithfulness, the rules above win.\n"
        "Rule 10: A figure, a date or a quantity never stands without what it refers to.\n"
        "Rule 11: What the material marks as open or disputed stays in, marked.\n"
        "Rule 12: Never cite a page, a slide or a position the facts do not state.\n"
        "Rule 13: Write ONE document covering all sources together, never one section per "
        "file unless the build plan asks for it.\n"
        + _marker_rule(names)
        + "\nBUILD PLAN\n" + template_body
    )


async def compose_single(caller: Caller, *, language: str, template_body: str,
                         sources: list[str], pool: list[Fact], pool_text: str) -> str:
    """The whole document in one call, the fallback for a failed outline."""
    antwort = await caller.create(
        messages=[
            {"role": "system",
             "content": _compose_system(language, template_body, source_names(pool))},
            {"role": "user", "content": _outline_user(sources, pool_text)},
        ],
        temperature=0.3, name="compose",
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


def section_facts(section: Section, pool: list[Fact]) -> list[Fact]:
    """The facts of one section, the whole pool when the planner assigned it none.

    A section without facts is not always a planning mistake: a build plan may ask for a
    part that draws on everything, such as a glossary or a set of self check questions.
    """
    return facts_for(section.fact_ids, pool) or pool
