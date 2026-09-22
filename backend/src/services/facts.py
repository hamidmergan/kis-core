"""The facts of a run: what one read call pulls out of a source, and the numbered pool.

A fact never carries a guessed place. The source goes into the call cut into numbered
pieces, the model names the piece a statement came from, and the piece knows its page
and its character range. That is the way back into the document.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from loguru import logger

from src.services.source_reading import Source

# Hard caps per field, so the size of the pool is a number and not a hope.
MAX_FACT_CHARS = 400
MAX_CITATION_CHARS = 400
MAX_CATEGORY_CHARS = 30

# The search grid. A proof is no category, every fact carries its citation in a field.
CATEGORIES_DE: tuple[str, ...] = ("Kernaussage", "Zahl", "Begriff", "Beispiel", "Ablauf", "Streitpunkt")
CATEGORIES_EN: tuple[str, ...] = ("key point", "figure", "term", "example", "process", "dispute")


def categories(language: str) -> tuple[str, ...]:
    return CATEGORIES_DE if language == "de" else CATEGORIES_EN


@dataclass(frozen=True)
class Fact:
    """One statement with its proof and the piece of the document it sits in."""

    fact_id: int
    category: str
    fact: str
    citation: str
    # Which source of the run, counted from zero, and which of its pieces.
    source: int
    piece: int

    def as_dict(self) -> dict:
        return asdict(self)


def from_dict(daten: dict) -> Fact | None:
    """One fact back out of the job folder, None when it is not usable."""
    try:
        return Fact(fact_id=int(daten["fact_id"]), category=str(daten.get("category") or ""),
                    fact=str(daten["fact"]), citation=str(daten.get("citation") or ""),
                    source=int(daten["source"]), piece=int(daten["piece"]))
    except (KeyError, TypeError, ValueError):
        return None


def _clean(value, limit: int) -> str:
    """One field as a single line, cut where a model runs away with it."""
    return " ".join(str(value or "").split())[:limit]


def numbered_pieces(source: Source, von: int, bis: int) -> str:
    """The pieces of a source as the read call sees them, each behind its number.

    ``von`` and ``bis`` are piece indexes, so a large file can be read in two calls
    without the numbers shifting.
    """
    zeilen = []
    for i in range(von, min(bis, len(source.stuecke))):
        stueck = source.stuecke[i]
        zeilen.append(f"[{i}] {source.text[stueck.von:stueck.bis]}")
    return "\n\n".join(zeilen)


def system_prompt(language: str, grid: tuple[str, ...], teil: int, teile: int) -> str:
    """The reading order: pull out what a writer can build from, nothing of your own."""
    raster = "\n".join(f"- {k}" for k in grid)
    sprache = "German" if language == "de" else "English"
    von_teilen = (f"This is part {teil} of {teile} of one document. Never mention that, "
                  "never refer to the other parts, never describe the document as a whole.\n"
                  ) if teile > 1 else ""
    return (
        "You prepare ONE document for a team that writes from your statements. They never "
        "see the document itself.\n"
        "The document arrives cut into numbered pieces, each one starting with its number "
        "in square brackets.\n"
        f"Rule 1: Write every statement in {sprache}. The document may be in another "
        "language, that never changes your output language.\n"
        "Rule 2: Only what the document states in so many words becomes a statement. Never "
        "invent, never conclude, never interpret.\n"
        "Rule 3: Every statement carries a citation, copied word for word from the document, "
        "in the language of the document. A statement you cannot quote does not exist. One "
        "sentence of citation is enough, never a whole paragraph.\n"
        "Rule 4: Every statement carries the number of the piece it comes from, exactly as "
        "it stands in the square brackets. Never a number that is not there.\n"
        "Rule 5: A statement stands on its own later, next to statements from other "
        "documents. Keep a figure with what it counts, a definition with its term, a step "
        "with the procedure it belongs to.\n"
        "Rule 6: The categories below are your search grid. Write the category verbatim, "
        "never one of your own.\n"
        f"Rule 7: A statement is at most {MAX_FACT_CHARS} characters, one or two sentences. "
        "Drop filler and repetition before you drop substance, and never return the same "
        "statement twice.\n"
        f"{von_teilen}"
        "Rule 8: Do not use semicolons or any type of dash. Use only periods, commas, "
        "colons and question marks.\n"
        f"\nCATEGORIES\n{raster}\n"
    )


SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "facts",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "piece": {
                                "type": "integer",
                                "description": "The number in square brackets of the piece this comes from.",
                            },
                            "category": {
                                "type": "string",
                                "description": "One of the listed categories, verbatim.",
                            },
                            "fact": {
                                "type": "string",
                                "description": (
                                    "The statement in one or two sentences, in the output "
                                    "language, with every figure next to what it refers to."
                                ),
                            },
                            "citation": {
                                "type": "string",
                                "description": (
                                    "One sentence copied word for word from that piece, in "
                                    "the language of the document."
                                ),
                            },
                        },
                        "required": ["piece", "category", "fact", "citation"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["facts"],
            "additionalProperties": False,
        },
    },
}


def _strip_wrapper(raw: str | None) -> str:
    """Drops a thinking block and a fenced wrapper some models add around JSON."""
    text = (raw or "").strip()
    if text.startswith("<think>"):
        ende = text.find("</think>")
        if ende != -1:
            text = text[ende + len("</think>"):].strip()
    if text.startswith("```"):
        ohne_zaun = text.split("\n", 1)
        if len(ohne_zaun) == 2:
            text = ohne_zaun[1].rsplit("```", 1)[0].strip()
    return text


def _loads(text: str):
    """The JSON of an answer, also when the model wrote a sentence around it."""
    try:
        return json.loads(text)
    except ValueError:
        pass
    treffer = re.search(r"[\[{].*[\]}]", text, re.S)
    if not treffer:
        return None
    try:
        return json.loads(treffer.group(0))
    except ValueError:
        return None


def salvage(text: str) -> list[dict]:
    """The finished objects of an array the cap cut off, a half written one drops out."""
    anfang = text.find("[")
    if anfang == -1:
        return []
    rumpf = text[anfang + 1:]
    objekte: list[dict] = []
    tiefe, start, im_text, schutz = 0, None, False, False
    for i, zeichen in enumerate(rumpf):
        if im_text:
            if schutz:
                schutz = False
            elif zeichen == "\\":
                schutz = True
            elif zeichen == '"':
                im_text = False
            continue
        if zeichen == '"':
            im_text = True
        elif zeichen == "{":
            if tiefe == 0:
                start = i
            tiefe += 1
        elif zeichen == "}":
            tiefe -= 1
            if tiefe == 0 and start is not None:
                try:
                    eintrag = json.loads(rumpf[start:i + 1])
                except ValueError:
                    eintrag = None
                if isinstance(eintrag, dict):
                    objekte.append(eintrag)
                start = None
    return objekte


def parse_answer(raw: str | None, *, gueltige_stuecke: range) -> list[dict]:
    """The usable entries of one answer. A piece number outside the call drops out."""
    text = _strip_wrapper(raw)
    if not text:
        return []
    roh = _loads(text)
    eintraege = salvage(text) if roh is None else (
        roh.get("facts") if isinstance(roh, dict) else roh)
    if not isinstance(eintraege, list):
        return []
    aus: list[dict] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        aussage = _clean(eintrag.get("fact"), MAX_FACT_CHARS)
        if not aussage:
            continue
        try:
            stueck = int(eintrag["piece"])
        except (KeyError, TypeError, ValueError):
            continue
        if stueck not in gueltige_stuecke:
            # A made up number would point the way back at the wrong text.
            continue
        aus.append({
            "piece": stueck,
            "category": _clean(eintrag.get("category"), MAX_CATEGORY_CHARS),
            "fact": aussage,
            "citation": _clean(eintrag.get("citation"), MAX_CITATION_CHARS),
        })
    return aus


def _key(text: str) -> str:
    """The comparison form of a statement: letters and digits only, lower case."""
    return re.sub(r"[\W_]+", "", text.casefold(), flags=re.UNICODE)


# Below this a statement is too short for containment to mean it is the same statement.
_MIN_CONTAINED_CHARS = 40


def unique_within(texts: list[str]) -> list[int]:
    """The positions worth keeping among statements of ONE source.

    Never used across sources: two documents saying nearly the same thing is exactly
    the agreement or the contradiction a later step has to see.
    """
    schluessel = [_key(t) for t in texts]
    verworfen: set[int] = set()
    for i, eigener in enumerate(schluessel):
        if not eigener or i in verworfen:
            continue
        for j in range(i + 1, len(schluessel)):
            if j in verworfen:
                continue
            anderer = schluessel[j]
            if not anderer or eigener == anderer:
                verworfen.add(j)
            elif len(anderer) >= _MIN_CONTAINED_CHARS and anderer in eigener:
                verworfen.add(j)
            elif len(eigener) >= _MIN_CONTAINED_CHARS and eigener in anderer:
                # The later one says the same thing more fully, so this one steps aside.
                verworfen.add(i)
                break
    return [i for i, k in enumerate(schluessel) if k and i not in verworfen]


def build_pool(gelesen: list[list[dict]]) -> list[Fact]:
    """The facts of all sources as one numbered list, in the order of the sources.

    ``gelesen`` carries one list of entries per source. Repetitions fall away inside a
    source, never between two of them.
    """
    vorrat: list[Fact] = []
    nummer = 0
    for quelle, eintraege in enumerate(gelesen):
        behalten = unique_within([e["fact"] for e in eintraege])
        if len(behalten) < len(eintraege):
            logger.info("Fakten: Quelle {}, {} von {} Aussagen sind Wiederholungen",
                        quelle, len(eintraege) - len(behalten), len(eintraege))
        for stelle in behalten:
            eintrag = eintraege[stelle]
            nummer += 1
            vorrat.append(Fact(fact_id=nummer, category=eintrag["category"],
                               fact=eintrag["fact"], citation=eintrag["citation"],
                               source=quelle, piece=eintrag["piece"]))
    return vorrat


def pool_line(fact: Fact) -> str:
    """One fact as the planner sees it, its number first so the outline can point at it."""
    return f"#{fact.fact_id} ({fact.category}) {fact.fact}"


def pool_block(facts: list[Fact]) -> str:
    """The whole pool for the planning call, without proofs, they only cost room there."""
    return "\n".join(pool_line(f) for f in facts)


def facts_for(ids: list[int], pool: list[Fact]) -> list[Fact]:
    """The facts behind these numbers, in the order of the pool, unknown numbers drop out."""
    gesucht = set(ids or [])
    return [f for f in pool if f.fact_id in gesucht]


def context_for(facts: list[Fact], sources: list[Source], *, nachbarn: int = 1) -> str:
    """The pieces these facts come from, with their neighbours, each piece only once.

    This is the way back into the document. No search and no model call: the fact knows
    its piece, the piece knows its place.
    """
    gewollt: dict[int, set[int]] = {}
    for fakt in facts:
        gewollt.setdefault(fakt.source, set()).update(
            range(fakt.piece - nachbarn, fakt.piece + nachbarn + 1))
    teile: list[str] = []
    for quelle in sorted(gewollt):
        if quelle >= len(sources):
            continue
        source = sources[quelle]
        nummern = sorted(n for n in gewollt[quelle] if 0 <= n < len(source.stuecke))
        if not nummern:
            continue
        # Neighbouring pieces overlap, so they are joined into one passage.
        laeufe: list[list[int]] = []
        for n in nummern:
            if laeufe and n == laeufe[-1][-1] + 1:
                laeufe[-1].append(n)
            else:
                laeufe.append([n])
        for lauf in laeufe:
            von = source.stuecke[lauf[0]].von
            bis = source.stuecke[lauf[-1]].bis
            teile.append(source.text[von:bis])
    return "\n\n".join(teile)
