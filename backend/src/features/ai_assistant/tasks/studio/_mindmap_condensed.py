"""The mind map when the material does not fit: structure from the summaries, depth from search."""

from loguru import logger

# Enough topics for a four level map, more only costs searches.
_MAX_TOPICS = 60
# How much of one source's summary travels, a summary is short anyway.
_MAX_SUMMARY_CHARS = 4000


def usable(sources: list[dict]) -> bool:
    """True when every source carries a summary, otherwise the raw way stays."""
    return bool(sources) and all((s.get("summary") or "").strip() for s in sources)


def should_condense(total_chars: int, budget: int, sources: list[dict]) -> bool:
    """Only when the material does not fit, and only when every source can be condensed."""
    return total_chars > budget and usable(sources)


def summary_context(sources: list[dict]) -> str:
    """One labelled block per source: what that source is about."""
    teile = []
    for s in sources:
        summary = (s.get("summary") or "").strip()
        if summary:
            teile.append(f"--- {s['label']} ---\n{summary[:_MAX_SUMMARY_CHARS]}")
    return "\n\n".join(teile)


def node_topics(skeleton: dict, max_topics: int = _MAX_TOPICS) -> list[str]:
    """The node labels to search evidence for, the root names no single spot."""
    out: list[str] = []

    def sammeln(node: dict) -> None:
        for child in node.get("children") or []:
            topic = (child.get("topic") or "").strip()
            if topic and topic not in out:
                out.append(topic)
            sammeln(child)

    sammeln(skeleton or {})
    return out[:max_topics]


def _spot_key(chunk: dict) -> str:
    """The spot as the model writes it: a page number, or a timestamp for a recording."""
    start = chunk.get("start_time")
    if start is None:
        return str(chunk.get("page_number"))
    s = int(start)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _stelle(chunk: dict) -> str:
    """Where the passage stands: page for a document, timestamp for a recording."""
    if chunk.get("start_time") is None:
        return f"S. {chunk.get('page_number')}"
    return _spot_key(chunk)



def evidence_context(hits_by_topic: dict[str, list[dict]]) -> str:
    """The found passages as text, each with its file and its spot, every passage once."""
    teile: list[str] = []
    gesehen: set[tuple] = set()
    for treffer in hits_by_topic.values():
        for chunk in treffer:
            schluessel = (chunk.get("source_label"), chunk.get("page_number"),
                          chunk.get("start_time"))
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            teile.append(f"[{chunk.get('source_label')}, {_stelle(chunk)}]\n{chunk.get('content')}")
    return "\n\n".join(teile)


# Passages per node, enough for a page number without flooding the second call.
_PER_TOPIC = 3


def search_evidence(topics: list[str], *, embed, search, per_topic: int = _PER_TOPIC
                    ) -> dict[str, list[dict]]:
    """Per node label the passages that match it, a failed search costs only that node."""
    out: dict[str, list[dict]] = {}
    for topic in topics:
        try:
            treffer = search(topic, embed(topic), per_topic) or []
        except Exception as e:  # noqa: BLE001 - one node without evidence is no reason to stop
            logger.warning("Mindmap: keine Belegsuche fuer {}: {}", topic, e)
            continue
        if treffer:
            out[topic] = treffer
    return out


def skeleton_sources(skeleton: dict, known: set[str]) -> dict[str, str]:
    """Per node label the file its summary came from, invented names are dropped."""
    out: dict[str, str] = {}

    def sammeln(node: dict) -> None:
        for child in node.get("children") or []:
            topic = (child.get("topic") or "").strip()
            label = child.get("source_label")
            if topic and label in known:
                out.setdefault(topic, label)
            sammeln(child)

    sammeln(skeleton or {})
    return out


def fill_sources(node: dict, by_topic: dict[str, str], geerbt: str = "",
                 tiefe: int = 0) -> int:
    """Root and main branches name no file, they span several, everything below does."""
    ergaenzt = 0
    for child in node.get("children") or []:
        if tiefe == 0:
            # A main branch spans several sources, one chip on it would be arbitrary.
            for feld in ("source_label", "page_number", "keyword"):
                child.pop(feld, None)
            ergaenzt += fill_sources(child, by_topic, "", tiefe + 1)
            continue
        eigen = child.get("source_label")
        if not eigen:
            eigen = by_topic.get((child.get("topic") or "").strip()) or geerbt
            if eigen:
                child["source_label"] = eigen
                ergaenzt += 1
        ergaenzt += fill_sources(child, by_topic, eigen or "", tiefe + 1)
    return ergaenzt


def strip_unbacked(node: dict, text_at) -> int:
    """Drops a spot the keyword does not stand on word for word, the node itself stays.

    A spot that only came back from our own search is NOT enough: measured on 30 statutes
    the model then pins a leaf on any retrieved page of the right file, 6 of 10 landed wrong.
    """
    entfernt = 0
    label, stelle = node.get("source_label"), node.get("page_number")
    if label and stelle is not None:
        keyword = (node.get("keyword") or "").strip()
        if not keyword or keyword.lower() not in (text_at(label, stelle) or "").lower():
            for feld in ("source_label", "page_number", "keyword"):
                node.pop(feld, None)
            entfernt = 1
    for child in node.get("children") or []:
        entfernt += strip_unbacked(child, text_at)
    return entfernt


# Passages offered per leaf, few enough that the model can read them all.
_PER_LEAF = 4


def pageless_leaves(node: dict) -> list[dict]:
    """The outermost nodes that name a file but no spot in it, nothing above them."""
    out: list[dict] = []

    def sammeln(n: dict) -> None:
        kinder = n.get("children") or []
        if not kinder and n.get("source_label") and n.get("page_number") is None:
            out.append(n)
        for child in kinder:
            sammeln(child)

    sammeln(node or {})
    return out


def locate_context(paare: list[tuple[dict, list[dict]]]) -> str:
    """Every leaf with its numbered candidates, the numbers are what comes back."""
    teile: list[str] = []
    nummer = 0
    for i, (blatt, kandidaten) in enumerate(paare, 1):
        zeilen = [f"N{i}: {blatt.get('topic')}"]
        for chunk in kandidaten:
            nummer += 1
            # Whole, never cut: the deciding sentence sat at char 470 and was lost.
            zeilen.append(f"  [{nummer}] {' '.join((chunk.get('content') or '').split())}")
        teile.append("\n".join(zeilen))
    return "\n\n".join(teile)


def apply_located(paare: list[tuple[dict, list[dict]]], antwort: dict) -> int:
    """Puts the chosen passage's spot on its leaf, the numbers never leave our own data."""
    nummern: dict[int, tuple[dict, dict]] = {}
    nummer = 0
    for blatt, kandidaten in paare:
        for chunk in kandidaten:
            nummer += 1
            nummern[nummer] = (blatt, chunk)

    gesetzt = 0
    for i, (blatt, _k) in enumerate(paare, 1):
        wahl = (antwort or {}).get(f"N{i}", (antwort or {}).get(str(i)))
        if not isinstance(wahl, int):
            continue
        ziel = nummern.get(wahl)
        if not ziel or ziel[0] is not blatt:
            continue
        chunk = ziel[1]
        blatt["source_label"] = chunk.get("source_label") or blatt.get("source_label")
        blatt["page_number"] = (int(chunk["page_number"]) if chunk.get("start_time") is None
                                else _spot_key(chunk))
        # The old keyword is from another passage, it would highlight the wrong spot.
        blatt.pop("keyword", None)
        gesetzt += 1
    return gesetzt


def build(*, sources: list[dict], language: str, adaptive_suffix: str, ask,
          embed, search, verify=None, locate=None) -> dict | None:
    """Two calls: the summaries give the structure, the searched passages give the depth."""
    import json as _json
    from src.features.ai_assistant.prompts.studio_prompts import (
        AIA_MINDMAP_DEEPEN_PROMPT,
        AIA_MINDMAP_LOCATE_PROMPT,
        AIA_MINDMAP_SKELETON_PROMPT,
    )

    skeleton = ask([
        {"role": "system",
         "content": AIA_MINDMAP_SKELETON_PROMPT.replace("{language}", language) + adaptive_suffix},
        {"role": "user", "content": "/no_think\nSummaries:\n\n" + summary_context(sources)},
    ])
    if not isinstance(skeleton, dict) or "topic" not in skeleton:
        return None

    # The skeleton knows which summary a node came from, that survives the second call.
    bekannt = {s["label"] for s in sources if s.get("label")}
    dateien = skeleton_sources(skeleton, bekannt)
    skeleton.pop("source_label", None)

    treffer = search_evidence(node_topics(skeleton), embed=embed, search=search)
    belege = evidence_context(treffer)
    if not belege:
        logger.info("Mindmap: keine Belegstellen gefunden, das Gerippe bleibt wie es ist")
        fill_sources(skeleton, dateien)
        return skeleton

    fertig = ask([
        {"role": "system",
         "content": AIA_MINDMAP_DEEPEN_PROMPT.replace("{language}", language) + adaptive_suffix},
        {"role": "user", "content": (
            "/no_think\nSkeleton:\n" + _json.dumps(skeleton, ensure_ascii=False)
            + "\n\nSummaries:\n\n" + summary_context(sources)
            + "\n\nPassages:\n\n" + belege)},
    ])
    if not isinstance(fertig, dict) or "topic" not in fertig:
        logger.warning("Mindmap: Vertiefung unbrauchbar, das Gerippe bleibt wie es ist")
        fill_sources(skeleton, dateien)
        return skeleton

    if verify is not None:
        ohne_deckung = strip_unbacked(fertig, verify)
        logger.info("Mindmap: {} Belege ohne Deckung entfernt", ohne_deckung)
    fertig.pop("source_label", None)
    fertig.pop("page_number", None)
    ergaenzt = fill_sources(fertig, dateien)
    logger.info("Mindmap: {} Knoten auf ihre Datei zurueckgefallen", ergaenzt)

    # Third call: the outermost nodes without a spot pick one from a numbered list.
    offen = pageless_leaves(fertig)
    if offen and locate is not None:
        paare = [(blatt, treffer) for blatt in offen
                 if (treffer := locate(blatt["topic"], blatt["source_label"], _PER_LEAF))]
        if paare:
            wahl = ask([
                {"role": "system", "content": AIA_MINDMAP_LOCATE_PROMPT},
                {"role": "user", "content": "/no_think\n" + locate_context(paare)},
            ])
            gesetzt = apply_located(paare, wahl if isinstance(wahl, dict) else {})
            logger.info("Mindmap: {} von {} offenen Blaettern haben ihre Seite bekommen",
                        gesetzt, len(paare))
    return fertig
