"""Writing phase: plan the outline over the fact pool, write section by section, assemble."""

import asyncio
import json
import re

from loguru import logger

from src.services.facts.pool import Fact, facts_block, facts_for
from src.features.summary.models import GROUND_RULES, Caller, Outline, Section
from src.limits import (
    SUMMARY_ASSIGN_BATCH_FACTS,
    SUMMARY_ASSIGN_CONCURRENCY,
    SUMMARY_CHARS_PER_SECTION,
    SUMMARY_COMPOSE_MAX_ATTEMPTS,
    SUMMARY_MAX_SECTIONS,
    SUMMARY_MIN_SECTIONS,
    SUMMARY_OUTLINE_MAX_ATTEMPTS,
    SUMMARY_PROMPT_RESERVE_CHARS,
    SUMMARY_RETRY_DELAY_SECONDS,
    SUMMARY_SECTION_BASE_CHARS,
    SUMMARY_SECTION_FACT_CHARS,
    SUMMARY_SECTION_GROUP_CHARS,
    SUMMARY_SECTIONS_PER_SOURCE,
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
                "title": {
                    "type": "string",
                    "description": (
                        "The title of the finished document, in the output language: a short "
                        "noun phrase naming what the material is about. No file name, no "
                        "word for the format such as summary or briefing."
                    ),
                },
                "intro": {
                    "type": "string",
                    "description": (
                        "The opening summary in the output language. The first sentence says "
                        "what the material covers, the rest gives its most important "
                        "statements with their figures. Never a restatement of these "
                        "instructions."
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
                        },
                        "required": ["section_index", "title", "description"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["title", "intro", "sections"],
            "additionalProperties": False,
        },
    },
}


ASSIGNMENT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "assignments",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "assignments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "fact_id": {"type": "integer"},
                            "section_index": {
                                "type": "integer",
                                "description": "0 for the first section listed, 1 for the second, and so on.",
                            },
                        },
                        "required": ["fact_id", "section_index"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["assignments"],
            "additionalProperties": False,
        },
    },
}


def target_sections(facts_chars: int, sources: int = 1) -> int:
    """How many sections the material carries, a target the planner may deviate from.

    Never fewer than every source needs: with unrelated files a count drawn from the
    size alone leaves the last of them without a heading to stand under.
    """
    aus_umfang = facts_chars // SUMMARY_CHARS_PER_SECTION
    aus_quellen = SUMMARY_SECTIONS_PER_SOURCE * max(1, sources)
    return max(SUMMARY_MIN_SECTIONS, min(SUMMARY_MAX_SECTIONS, max(aus_umfang, aus_quellen)))


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


def parse_outline(raw: str | None) -> Outline:
    """Reads the planning answer, a broken one yields no sections rather than an error.

    Only headings are read here. Which fact goes where is settled afterwards, in batches,
    because one answer carrying every number of a large pool loses its tail.
    """
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
        umfang = (eintrag.get("scope") or eintrag.get("description")
                  if isinstance(eintrag, dict) else "") or ""
        titel = " ".join(str(titel).split()).lstrip("#").strip()
        if not titel or len(titel) > 120:
            continue
        if any(a.title.casefold() == titel.casefold() for a in abschnitte):
            continue
        abschnitte.append(Section(title=titel, scope=" ".join(str(umfang).split())))
    if len(abschnitte) < SUMMARY_MIN_SECTIONS:
        return Outline()
    titel = " ".join(str(roh.get("title") or "").split()).lstrip("#").strip()
    return Outline(title=titel[:120], intro=str(roh.get("intro") or "").strip(),
                   sections=abschnitte[:SUMMARY_MAX_SECTIONS])


def coverage(outline: Outline, pool: list[Fact]) -> float:
    """The share of the pool the outline actually put somewhere."""
    if not pool:
        return 1.0
    vergeben = {n for a in outline.sections for n in a.fact_ids}
    return len(vergeben) / len(pool)


def _outline_system(language: str, template_body: str, target: int, sources: int) -> str:
    return (
        "You plan the headings of a document. The facts you read are working material, "
        "the reader never sees them as a list. You decide the headings only, another step "
        "puts the facts under them.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Derive every section from what the material carries. Never fall back on a "
        "generic scaffold such as introduction, main part, conclusion.\n"
        f"Rule 9: Plan around {target} sections, between {SUMMARY_MIN_SECTIONS} and "
        f"{SUMMARY_MAX_SECTIONS}. Thin material gets fewer, rich material gets more.\n"
        "Rule 10: A heading names a theme that carries several facts, never a single fact. "
        "If a heading would rest on one statement alone, widen it or fold it into another.\n"
        f"Rule 11: The material comes from {sources} file(s), listed below, and EVERY one of "
        "them must be covered by at least one section. Work through the whole list of facts "
        "to its last line before you settle the headings. A subject only the later facts "
        "carry still needs its own heading.\n"
        "Rule 12: Sections must not overlap, and the headings follow the subject, never the "
        "file a fact came from. A heading never names a file.\n"
        "Rule 13: Plan the sections the BUILD PLAN below asks for. Where it names parts the "
        "result must have, such as a quiz, an answer key or a glossary, each is a section of "
        "its own, and a part that answers another one comes after it. Where it asks for an "
        "order, such as what the reader must act on first and background last, the sections "
        "are already in that order.\n"
        "Rule 14: The title names what the material is about, short, and never mentions a "
        "file or the format.\n"
        "Rule 15: The intro stands before the first heading. Its first sentence says what "
        "the material covers, then come the three to five most important things it states, "
        "concretely and with their figures. Never say what the reader will receive and never "
        "repeat these instructions.\n"
        "\nBUILD PLAN\n" + template_body
    )


def _outline_user(sources: list[str], pool_text: str) -> str:
    liste = "\n".join(f"- {s}" for s in sources)
    return f"/no_think\nSources:\n{liste}\n\nFacts, one per line, numbered:\n\n{pool_text}"


async def plan_outline(caller: Caller, *, language: str, template_body: str,
                       sources: list[str], pool: list[Fact], pool_text: str,
                       target: int) -> Outline:
    """Plans the headings, then places every fact under them. Empty when planning failed."""
    plan = Outline()
    for versuch in range(1, SUMMARY_OUTLINE_MAX_ATTEMPTS + 1):
        try:
            antwort = await caller.create(
                messages=[
                    {"role": "system",
                     "content": _outline_system(language, template_body, target, len(sources))},
                    {"role": "user", "content": _outline_user(sources, pool_text)},
                ],
                temperature=0.2, name=f"outline:{versuch}",
                response_format=OUTLINE_SCHEMA,
            )
            plan = parse_outline(antwort.choices[0].message.content)
            if plan.sections:
                break
            logger.warning("Zusammenfassung: Gliederung {} unlesbar", versuch)
        except Exception as e:  # noqa: BLE001 - the single call still saves the run
            logger.warning("Zusammenfassung: Planungsaufruf {} gescheitert ({})", versuch, e)
        if versuch < SUMMARY_OUTLINE_MAX_ATTEMPTS:
            await asyncio.sleep(SUMMARY_RETRY_DELAY_SECONDS)
    if plan.sections:
        await assign_pool(caller, language=language, outline=plan, pool=pool)
    return plan


def parse_assignments(raw: str | None, known_ids: set[int], section_count: int) -> dict[int, int]:
    """Reads the gap fill answer, an unknown fact or section index is dropped, not guessed."""
    text = _strip_thinking(raw)
    treffer = re.search(r"\{.*\}", text, re.S)
    if not treffer:
        return {}
    try:
        roh = json.loads(treffer.group(0))
    except ValueError:
        return {}
    eintraege = roh.get("assignments")
    if not isinstance(eintraege, list):
        return {}
    zuordnung: dict[int, int] = {}
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        try:
            fact_id, index = int(eintrag.get("fact_id")), int(eintrag.get("section_index"))
        except (TypeError, ValueError):
            continue
        if fact_id in known_ids and 0 <= index < section_count:
            zuordnung[fact_id] = index
    return zuordnung


def _assign_system(language: str, sections: list[Section]) -> str:
    liste = "\n".join(f"{i}: {a.title}. {a.scope}" for i, a in enumerate(sections))
    return (
        "The headings of a document are already fixed. You sort facts under them, you never "
        "change them.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Assign EVERY fact below to exactly one of the sections listed. Never invent "
        "a section, never leave a fact out, choose the closest fit if none is exact.\n"
        "Rule 9: Go by what the fact is about, never by the order of the list.\n"
        "Rule 10: Answer only with the assignments, a fact never appears twice.\n"
        f"\nSECTIONS\n{liste}\n"
    )


def _assign_user(facts: list[Fact]) -> str:
    zeilen = "\n".join(f"#{f.fact_id} ({f.category}) {f.fact}" for f in facts)
    return f"/no_think\nFacts to sort:\n\n{zeilen}"


async def assign_batch(caller: Caller, *, language: str, sections: list[Section],
                       facts: list[Fact]) -> dict[int, int]:
    """Places one batch of facts under the fixed headings, {} when the call fails."""
    bekannt = {f.fact_id for f in facts}
    try:
        antwort = await caller.create(
            messages=[
                {"role": "system", "content": _assign_system(language, sections)},
                {"role": "user", "content": _assign_user(facts)},
            ],
            temperature=0.1, name=f"assign:{facts[0].fact_id}-{facts[-1].fact_id}",
            response_format=ASSIGNMENT_SCHEMA,
        )
        return parse_assignments(antwort.choices[0].message.content, bekannt, len(sections))
    except Exception as e:  # noqa: BLE001 - place_by_wording below still places every fact
        logger.warning("Zusammenfassung: Zuordnung eines Stapels gescheitert ({})", e)
        return {}


def _words(text: str) -> set[str]:
    """The carrying words of a text, short ones say nothing about the subject."""
    return set(re.findall(r"[^\W\d_]{4,}", text.casefold()))


def place_by_wording(sections: list[Section], remaining: list[Fact]) -> None:
    """What no call placed goes where the wording fits best, never into an unrelated section.

    Round robin would keep the count right and the content wrong: a statement on turnover
    tax landed under a heading about guard registries, and the writer then dropped it.
    """
    if not sections:
        return
    felder = [_words(f"{a.title} {a.scope}") for a in sections]
    for fakt in remaining:
        eigene = _words(fakt.fact)
        # Ties go to the section carrying the least, so nothing piles up in one place.
        beste = max(range(len(sections)),
                    key=lambda i: (len(eigene & felder[i]), -len(sections[i].fact_ids)))
        sections[beste].fact_ids.append(fakt.fact_id)


async def _one_pass(caller: Caller, *, language: str, outline: Outline,
                    offen: list[Fact]) -> list[Fact]:
    """Asks for the placement of these facts and applies it, returns what stayed unplaced."""
    stapel = [offen[i:i + SUMMARY_ASSIGN_BATCH_FACTS]
              for i in range(0, len(offen), SUMMARY_ASSIGN_BATCH_FACTS)]
    grenze = asyncio.Semaphore(SUMMARY_ASSIGN_CONCURRENCY)

    async def _einer(teil: list[Fact]) -> dict[int, int]:
        async with grenze:
            return await assign_batch(caller, language=language, sections=outline.sections,
                                      facts=teil)

    # Applied in the order of the batches, so the same answers always give the same plan.
    ergebnisse = await asyncio.gather(*(_einer(t) for t in stapel))
    nachtrag: list[Fact] = []
    for teil, zuordnung in zip(stapel, ergebnisse):
        for fakt in teil:
            index = zuordnung.get(fakt.fact_id)
            if index is None:
                nachtrag.append(fakt)
            else:
                outline.sections[index].fact_ids.append(fakt.fact_id)
    return nachtrag


async def assign_pool(caller: Caller, *, language: str, outline: Outline,
                      pool: list[Fact]) -> None:
    """Places every fact of the pool under the planned headings.

    One call carries the whole pool, a second one only what it dropped, and the wording
    decides about the rest. The second call costs nothing on a model that drops nothing.
    """
    offen = [f for f in pool if f.fact_id not in {n for a in outline.sections for n in a.fact_ids}]
    if not offen:
        return
    nachtrag = await _one_pass(caller, language=language, outline=outline, offen=offen)
    if nachtrag:
        logger.warning("Zusammenfassung: {} von {} Fakten bleiben offen, zweiter Anlauf",
                       len(nachtrag), len(offen))
        nachtrag = await _one_pass(caller, language=language, outline=outline, offen=nachtrag)
    if nachtrag:
        logger.warning("Zusammenfassung: {} Fakten werden nach Wortlaut eingeordnet",
                       len(nachtrag))
        place_by_wording(outline.sections, nachtrag)


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


def expected_chars(facts: int) -> int:
    """How much prose a section of this many facts costs, measured on the accepted run."""
    return SUMMARY_SECTION_BASE_CHARS + facts * SUMMARY_SECTION_FACT_CHARS


def group_sections(sections: list[Section], budget: int | None = None) -> list[list[int]]:
    """Runs of neighbouring sections that fit one writing call, by their expected prose.

    Small sections cost a whole call each while using a fraction of the answer, so they
    travel together. A section too big on its own still gets its own call.
    """
    if budget is None:
        budget = SUMMARY_SECTION_GROUP_CHARS
    gruppen: list[list[int]] = []
    laufend: list[int] = []
    summe = 0
    for i, abschnitt in enumerate(sections):
        kosten = expected_chars(len(abschnitt.fact_ids))
        if laufend and summe + kosten > budget:
            gruppen.append(laufend)
            laufend, summe = [], 0
        laufend.append(i)
        summe += kosten
    if laufend:
        gruppen.append(laufend)
    return gruppen


def _heading_positions(text: str) -> list[tuple[int, int, str]]:
    """Every level two heading: where its line starts, where its body starts, its wording."""
    return [(m.start(), m.end(), m.group(1).strip())
            for m in re.finditer(r"^##+[ \t]+(.+)$", text, re.M)]


def split_group(text: str, titles: list[str]) -> list[str] | None:
    """The text of each section of a group, or None when the answer cannot be cut safely.

    Matched by wording first, by position only when the count is exactly right. A wrong cut
    would put one section's prose under another's heading, so None is the honest answer.
    """
    if len(titles) == 1:
        return [text.strip()]
    koepfe = _heading_positions(text)
    if not koepfe:
        return None
    gewaehlt: list[tuple[int, int, str]] = []
    suche = 0
    for titel in titles:
        treffer = next((k for k in koepfe[suche:]
                        if k[2].casefold() == titel.casefold()), None)
        if treffer is None:
            gewaehlt = []
            break
        gewaehlt.append(treffer)
        suche = koepfe.index(treffer) + 1
    if not gewaehlt:
        if len(koepfe) != len(titles):
            return None
        gewaehlt = koepfe
    teile: list[str] = []
    for nr, (_, koerper_ab, _) in enumerate(gewaehlt):
        ende = gewaehlt[nr + 1][0] if nr + 1 < len(gewaehlt) else len(text)
        teile.append(text[koerper_ab:ende].strip())
    return teile if all(teile) else None


def _section_system(language: str, template_body: str, count: int = 1) -> str:
    mehrere = (
        f"You write {count} CONSECUTIVE sections of a larger document. Begin each one with "
        "its heading exactly as given, on its own line, written as '## Heading'. Write "
        "nothing before the first heading and nothing after the last section. Every heading "
        "you write is one of the given ones, never an extra one of your own.\n"
        if count > 1 else
        "You write ONE section of a larger document. Do not write the heading.\n"
    )
    return (
        mehrere
        + "The sections before yours are already written and given to you, the ones after "
        "yours come later.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Write only what belongs under the heading you are writing. The scopes of the "
        "sections still to come are listed so you stay off their ground. Never announce what "
        "comes later.\n"
        "Rule 9: Continue the document you are given, never repeat what it already says. Where "
        "your section answers or builds on an earlier one, make the two match item for item.\n"
        "Rule 10: Go as deep as the facts allow. A Markdown table where things are compared "
        "along the same attributes, bullet points where it is a list, numbered items where "
        "order or count matters, continuous text where it is an argument.\n"
        "Rule 11: A figure, a date or a quantity never stands without what it refers to, and "
        "you carry over every one the facts state for your heading.\n"
        "Rule 12: A fact carrying a 'Stelle:' names the part of the source it rests on. Put "
        "that exactly as it stands in square brackets at the end of the statement, for "
        "example [§ 27 Abs. 3]. A fact without one gets no brackets. Never invent a "
        "reference and never number a part yourself.\n"
        "Rule 13: Two facts saying the same thing become ONE statement, in the fuller wording. "
        "Never write the same figure or duty twice in different words.\n"
        "Rule 14: Every fact you are given appears in your section. A fact that does not sit "
        "well under your heading still gets its statement, in the closest place, rather than "
        "being left out.\n"
        "Rule 15: What the material marks as open or disputed stays in, marked as such.\n"
        + ("Rule 16: Under each heading begin straight with the content, no lead in, no "
           "closing remark and no greeting.\n" if count > 1 else
           "Rule 16: Do not repeat your own heading. Begin with the content, write no closing "
           "remark and no greeting.\n")
        + "Rule 17: Never cite a page, a slide or a position the facts do not state. The "
        "citations in the facts are your proof, never quote them as a block. Never name a "
        "file and never write a file name into your text.\n"
        "\nThe document as a whole follows the build plan below. Match its register, but "
        "produce ONLY the sections you are given.\n\nBUILD PLAN\n" + template_body
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


def _section_user(group: list[Section], others: list[Section],
                  written: list[tuple[str, str]], facts: list[str]) -> str:
    """The order matters: what is to be written comes last, that is what gets the attention."""
    fremd = "\n".join(f"- {a.title}: {a.scope}" for a in others) or "- none"
    if len(group) == 1:
        kopf = f"YOUR HEADING: {group[0].title}\nYOUR SCOPE: {group[0].scope}\n\n"
        auftrag = f"YOUR FACTS:\n\n{facts[0]}"
    else:
        kopf = f"YOU WRITE {len(group)} SECTIONS, in the order below.\n\n"
        teile = [f"=== SECTION {i + 1} OF {len(group)} ===\n"
                 f"HEADING: {a.title}\nSCOPE: {a.scope}\nFACTS:\n{f}"
                 for i, (a, f) in enumerate(zip(group, facts))]
        auftrag = "YOUR SECTIONS:\n\n" + "\n\n".join(teile)
    return (
        "/no_think\n"
        f"{kopf}"
        f"Still to be written by others, stay off these:\n{fremd}\n\n"
        f"THE DOCUMENT SO FAR:\n{_document_so_far(written)}\n\n"
        f"{auftrag}"
    )


async def write_sections(caller: Caller, *, language: str, template_body: str,
                         group: list[Section], others: list[Section],
                         written: list[tuple[str, str]], facts: list[list[Fact]],
                         budget: int) -> list[str] | None:
    """Writes a run of sections in one call, None when the answer cannot be cut apart.

    None is not a failure of the run: the caller then writes the sections one at a time,
    which costs calls but never mixes one section's prose into another's heading.
    """
    anteil = budget // len(group)
    antwort = await caller.create(
        messages=[
            {"role": "system", "content": _section_system(language, template_body, len(group))},
            {"role": "user",
             "content": _section_user(group, others, written,
                                      [facts_block(f, anteil) for f in facts])},
        ],
        temperature=0.3,
        name=f"section:{group[0].title}" if len(group) == 1
        else f"sections:{len(group)}:{group[0].title}",
        max_tokens=SUMMARY_WRITE_MAX_TOKENS,
    )
    fertig = _finished(antwort)
    if len(group) == 1:
        # Cut here, not in assemble: a stored heading would keep teaching the pattern back.
        text = _drop_leading_heading(fertig)
        return [text] if text else None
    return split_group(fertig, [a.title for a in group])


def _compose_system(language: str, template_body: str) -> str:
    return (
        "You write the finished document from facts drawn out of several sources.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Begin immediately with the content, no framing sentence, no closing remark.\n"
        "Rule 9: Follow the build plan below exactly, it decides the shape. About "
        "faithfulness, the rules above win.\n"
        "Rule 10: A figure, a date or a quantity never stands without what it refers to.\n"
        "Rule 11: A fact carrying a 'Stelle:' gets that reference in square brackets at the "
        "end of its statement. A fact without one gets no brackets.\n"
        "Rule 12: Two facts saying the same thing become ONE statement, in the fuller wording.\n"
        "Rule 13: What the material marks as open or disputed stays in, marked.\n"
        "Rule 14: Never cite a page, a slide or a position the facts do not state. Never name "
        "a file and never write a file name into your text.\n"
        "Rule 15: Write ONE document covering all sources together, never one section per "
        "file unless the build plan asks for it, and every source is represented.\n"
        "\nBUILD PLAN\n" + template_body
    )


async def compose_single(caller: Caller, *, language: str, template_body: str,
                         sources: list[str], pool: list[Fact], pool_text: str) -> str:
    """The whole document in one call, the fallback for a failed outline.

    Tried more than once on purpose: the facts of every file are already on disk at this
    point, and a single dropped call would throw the whole reading phase away. What still
    fails after the last attempt is raised, so the stage fails visibly and the resume
    picks the saved facts back up.
    """
    for versuch in range(1, SUMMARY_COMPOSE_MAX_ATTEMPTS + 1):
        try:
            antwort = await caller.create(
                messages=[
                    {"role": "system", "content": _compose_system(language, template_body)},
                    {"role": "user", "content": _outline_user(sources, pool_text)},
                ],
                temperature=0.3, name=f"compose:{versuch}",
                max_tokens=SUMMARY_WRITE_MAX_TOKENS,
            )
            return _finished(antwort)
        except Exception as e:  # noqa: BLE001 - the last attempt hands the failure on
            logger.warning("Zusammenfassung: Einzelaufruf {} gescheitert ({})", versuch, e)
            if versuch >= SUMMARY_COMPOSE_MAX_ATTEMPTS:
                raise
            await asyncio.sleep(SUMMARY_RETRY_DELAY_SECONDS)
    raise RuntimeError("Der Einzelaufruf hat nichts geliefert.")


def assemble(intro: str, titles: list[str], texts: list[str], headings: bool,
             title: str = "") -> str:
    """Joins the written sections, with or without their headings.

    The document title only goes in where the build plan allows headings at all: a plan
    asking for one continuous text gets no heading of any level.
    """
    teile = [f"# {title.strip()}"] if title.strip() and headings else []
    if intro.strip():
        teile.append(intro.strip())
    for titel, text in zip(titles, texts):
        koerper = (text or "").strip()
        if not koerper:
            continue
        teile.append(f"## {titel}\n\n{koerper}" if headings else koerper)
    return "\n\n".join(teile)


def split_title(text: str) -> tuple[str, str]:
    """The document's own title and the body without it, ("", text) when it carries none.

    The Word cover page shows the title, so leaving it in the body would print it twice.
    """
    zeilen = text.split("\n")
    if not zeilen or not re.match(r"^#\s+\S", zeilen[0]):
        return "", text
    titel = zeilen[0].lstrip("#").strip()
    rest = zeilen[1:]
    while rest and not rest[0].strip():
        rest.pop(0)
    return titel, "\n".join(rest)


def section_facts(section: Section, pool: list[Fact]) -> list[Fact]:
    """The facts of one section, the whole pool when the planner assigned it none.

    A section without facts is not always a planning mistake: a build plan may ask for a
    part that draws on everything, such as a glossary or a set of self check questions.
    """
    return facts_for(section.fact_ids, pool) or pool
