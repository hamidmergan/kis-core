"""From a question to the context the model reads and the sources the answer shows."""
import re
from dataclasses import dataclass, field
from typing import Callable

from loguru import logger

from src.limits import CAMPUS_CONTEXT_MAX_CHARS, CAMPUS_SEARCH_CANDIDATES

_FRAGMENT_MAX = 80
_NEIGHBOR_SPAN = 1


@dataclass
class Context:
    text: str
    sources: list[dict] = field(default_factory=list)
    chunk_ids: list[int] = field(default_factory=list)


def fragment_for(content: str, heading: str | None) -> str | None:
    """A short verbatim start of the chunk body, the browser can jump to it with a text fragment."""
    body = content
    if heading and body.startswith(heading + "\n"):
        body = body[len(heading) + 1:]
    body = re.sub(r"^[#>\-\*\s]+", "", body.strip().split("\n", 1)[0]).strip()
    if len(body) < 12:
        return None
    if len(body) <= _FRAGMENT_MAX:
        return body
    cut = body[:_FRAGMENT_MAX]
    space = cut.rfind(" ")
    return cut[:space] if space > _FRAGMENT_MAX // 2 else cut


def _date_of(value) -> str | None:
    if value is None:
        return None
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10]


def _source_of(hit: dict, fragment: str | None) -> dict:
    return {
        "page_id": hit["page_id"],
        "kind": hit.get("kind") or "page",
        "url": hit.get("url") if (hit.get("kind") or "page") != "document" else None,
        "title": hit.get("title") or hit.get("filename") or hit.get("url") or "",
        "filename": hit.get("filename"),
        "fetched_at": _date_of(hit.get("fetched_at")),
        "fragment": fragment,
    }


def build_context(
    question: str,
    embed_one: Callable[[str], list[float]],
    search: Callable[[str, list[float] | None, int], list[dict]],
    neighbors: Callable[[int, int, int], list[dict]],
    budget: int = CAMPUS_CONTEXT_MAX_CHARS,
    candidates: int = CAMPUS_SEARCH_CANDIDATES,
) -> Context:
    """Hits in rank order with their page neighbours, packed per page until the budget is spent."""
    vector = None
    try:
        vector = embed_one(question)
    except Exception as e:  # noqa: BLE001
        logger.warning("Campus: Einbettung der Frage fehlgeschlagen, nur Stichwortsuche: {}", e)
    hits = search(question, vector, candidates)
    if not hits:
        return Context(text="", sources=[])
    pages: dict[int, dict] = {}
    order: list[int] = []
    used = 0
    seen_chunks: set[int] = set()
    for hit in hits:
        pid = hit["page_id"]
        group = pages.get(pid)
        if group is None:
            group = {"hit": hit, "chunks": {}}
        extra = [hit] + [n for n in neighbors(pid, hit["position"], _NEIGHBOR_SPAN)]
        fresh = [c for c in extra if c["id"] not in seen_chunks]
        cost = sum(len(c["content"]) for c in fresh)
        if used + cost > budget:
            if used == 0:
                fresh = [hit]
                cost = len(hit["content"])
            else:
                continue
        for c in fresh:
            seen_chunks.add(c["id"])
            group["chunks"][c["position"]] = c
        used += cost
        if pid not in pages:
            pages[pid] = group
            order.append(pid)
        if used >= budget:
            break
    docs = []
    sources = []
    chunk_ids: list[int] = []
    for index, pid in enumerate(order, start=1):
        group = pages[pid]
        hit = group["hit"]
        parts = [group["chunks"][pos]["content"] for pos in sorted(group["chunks"])]
        chunk_ids.extend(group["chunks"][pos]["id"] for pos in sorted(group["chunks"]))
        where = hit.get("url") if (hit.get("kind") or "page") != "document" else hit.get("filename")
        stand = _date_of(hit.get("fetched_at"))
        head = " | ".join(x for x in [hit.get("title") or "", where or "", f"Stand: {stand}" if stand else ""] if x)
        docs.append(f'<document index="{index}">\n<source>{head}</source>\n<content>\n' + "\n\n".join(parts) + "\n</content>\n</document>")
        sources.append(_source_of(hit, fragment_for(hit["content"], hit.get("heading"))))
    return Context(text="<documents>\n" + "\n".join(docs) + "\n</documents>", sources=sources, chunk_ids=chunk_ids)
