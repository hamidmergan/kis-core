"""The facts of a run: what one reads out of a file, and the numbered pool they form."""

import json
import re
from dataclasses import dataclass

from loguru import logger

_MAX_FIELD_CHARS = 2_000


@dataclass(frozen=True)
class Fact:
    """One statement with its proof, its file and its number in the pool."""

    fact_id: int
    category: str
    fact: str
    citation: str
    source_id: str
    source_name: str


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


def _clean(value, limit: int = _MAX_FIELD_CHARS) -> str:
    """One field as a single line, cut where a model runs away with it."""
    text = " ".join(str(value or "").split())
    return text[:limit]


def parse_facts(raw: str | None) -> list[dict]:
    """The facts of one answer, an unusable answer yields an empty list rather than an error."""
    text = _strip_wrapper(raw)
    if not text:
        return []
    roh = _loads(text)
    if roh is None:
        return []
    eintraege = roh.get("facts") if isinstance(roh, dict) else roh
    if not isinstance(eintraege, list):
        return []
    fakten: list[dict] = []
    for eintrag in eintraege:
        if not isinstance(eintrag, dict):
            continue
        aussage = _clean(eintrag.get("fact"))
        if not aussage:
            continue
        fakten.append({
            "category": _clean(eintrag.get("category"), 80),
            "fact": aussage,
            "citation": _clean(eintrag.get("citation")),
        })
    return fakten


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


def build_pool(sources: list[dict], saved: dict[str, list[dict]]) -> list[Fact]:
    """The facts of all files as one numbered list, in the order of the files.

    Numbered here and not on saving: the files are read at the same time and their
    answers arrive in any order, only the pool gives the same number twice.
    """
    vorrat: list[Fact] = []
    nummer = 0
    for quelle in sources:
        sid = quelle["source_id"]
        for eintrag in saved.get(sid) or []:
            aussage = _clean(eintrag.get("fact"))
            if not aussage:
                continue
            nummer += 1
            vorrat.append(Fact(
                fact_id=nummer,
                category=_clean(eintrag.get("category"), 80),
                fact=aussage,
                citation=_clean(eintrag.get("citation")),
                source_id=sid,
                source_name=quelle["filename"],
            ))
    return vorrat


def fact_line(fact: Fact, with_citation: bool = True) -> str:
    """One fact as the model sees it, its number first so the outline can point at it."""
    kopf = f"#{fact.fact_id} ({fact.category}) [{fact.source_name}] {fact.fact}"
    if with_citation and fact.citation:
        return f'{kopf} Beleg: "{fact.citation}"'
    return kopf


def pool_block(facts: list[Fact], budget: int) -> str:
    """The whole pool for the outline call, without proofs, they only cost room there."""
    text = "\n".join(fact_line(f, with_citation=False) for f in facts)
    if len(text) > budget:
        logger.warning("Zusammenfassung: Vorrat {} Zeichen, gekuerzt auf {}", len(text), budget)
        text = text[:budget]
    return text


def facts_block(facts: list[Fact], budget: int) -> str:
    """The facts of one section, with their proofs, that is what the writer works from."""
    text = "\n".join(fact_line(f) for f in facts)
    if len(text) > budget:
        logger.warning("Zusammenfassung: Fakten eines Abschnitts {} Zeichen, gekuerzt auf {}",
                       len(text), budget)
        text = text[:budget]
    return text


def facts_for(ids: list[int], pool: list[Fact]) -> list[Fact]:
    """The facts behind these numbers, in the order of the pool, unknown numbers drop out."""
    gesucht = set(ids or [])
    return [f for f in pool if f.fact_id in gesucht]


def source_names(facts: list[Fact]) -> list[str]:
    """Every file these facts come from, each once, in the order of the pool."""
    namen: list[str] = []
    for fakt in facts:
        if fakt.source_name not in namen:
            namen.append(fakt.source_name)
    return namen
