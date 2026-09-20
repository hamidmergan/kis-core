"""The facts of a run: what one reads out of a file, and the numbered pool they form."""

import json
import re
from dataclasses import dataclass

from loguru import logger

_MAX_FIELD_CHARS = 2_000


_MAX_REFERENCE_CHARS = 80


@dataclass(frozen=True)
class Fact:
    """One statement with its proof, its file and its number in the pool."""

    fact_id: int
    category: str
    fact: str
    citation: str
    source_id: str
    source_name: str
    # The part of the source the statement sits in, such as "§ 27 Abs. 3". Often empty.
    reference: str = ""


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
        # A cut off answer is no reason to lose the whole file, its finished facts count.
        eintraege = salvage_facts(text)
    else:
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
            "reference": _clean(eintrag.get("reference"), _MAX_REFERENCE_CHARS),
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


def salvage_facts(text: str) -> list[dict]:
    """The finished objects of an array the token cap cut off, a half written one drops out."""
    anfang = text.find("[")
    if anfang == -1:
        return []
    rumpf = text[anfang + 1:]
    objekte: list[dict] = []
    tiefe = 0
    start = None
    im_text = False
    schutz = False
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
    if objekte:
        logger.warning("Zusammenfassung: abgeschnittene Antwort, {} Fakten gerettet",
                       len(objekte))
    return objekte


def _key(text: str) -> str:
    """The comparison form of a statement: letters and digits only, lower case."""
    return re.sub(r"[\W_]+", "", text.casefold(), flags=re.UNICODE)


# Below this a statement is too short for containment to mean it is the same statement.
_MIN_CONTAINED_CHARS = 40


def unique_statements(texts: list[str]) -> list[int]:
    """The positions worth keeping: a repeat and a statement another carries in full drop out.

    The read call returns the same sentence more than once, once per category it fits,
    and the writer would then render each copy as its own bullet point.
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


def build_pool(sources: list[dict], saved: dict[str, list[dict]]) -> list[Fact]:
    """The facts of all files as one numbered list, in the order of the files.

    Numbered here and not on saving: the files are read at the same time and their
    answers arrive in any order, only the pool gives the same number twice.
    """
    rohe: list[tuple[dict, str, str]] = []
    for quelle in sources:
        sid = quelle["source_id"]
        for eintrag in saved.get(sid) or []:
            aussage = _clean(eintrag.get("fact"))
            if aussage:
                rohe.append((eintrag, sid, quelle["filename"]))
    behalten = unique_statements([_clean(e.get("fact")) for e, _, _ in rohe])
    if len(behalten) < len(rohe):
        logger.info("Zusammenfassung: {} von {} Fakten sind Wiederholungen und fallen weg",
                    len(rohe) - len(behalten), len(rohe))
    vorrat: list[Fact] = []
    for nummer, stelle in enumerate(behalten, start=1):
        eintrag, sid, name = rohe[stelle]
        vorrat.append(Fact(
            fact_id=nummer,
            category=_clean(eintrag.get("category"), 80),
            fact=_clean(eintrag.get("fact")),
            citation=_clean(eintrag.get("citation")),
            source_id=sid,
            source_name=name,
            reference=_clean(eintrag.get("reference"), _MAX_REFERENCE_CHARS),
        ))
    return vorrat


def fact_line(fact: Fact, with_citation: bool = True, with_source: bool = True) -> str:
    """One fact as the model sees it, its number first so the outline can point at it."""
    quelle = f" [{fact.source_name}]" if with_source else ""
    kopf = f"#{fact.fact_id} ({fact.category}){quelle} {fact.fact}"
    if not with_citation:
        return kopf
    if fact.reference:
        kopf = f"{kopf} Stelle: {fact.reference}"
    if fact.citation:
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
    """The facts of one section, with their proofs, that is what the writer works from.

    Without the file name: it is working material, the reader's document never shows it.
    """
    text = "\n".join(fact_line(f, with_source=False) for f in facts)
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
