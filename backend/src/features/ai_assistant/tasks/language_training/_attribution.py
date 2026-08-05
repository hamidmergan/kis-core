"""Tool-side wiring for the shared post-hoc attribution.

Turns a generated item's claim text into nav-only source chips via the SAME pgvector
gate/selector the chat uses (:mod:`src.services.aia_attribution`). Replaces the per-tool
page-guessing heuristics (find_all_pages, word-overlap, whole-page highlight) with one path.

Two entry points:

* :func:`attach_chips` — pure post-hoc search. Right for tools whose items REPEAT source
  wording (flashcards, quiz, karteikarten): the claim is close to a chunk, so the search
  finds it and a miss genuinely means "not clearly in the sources".
* :func:`attach_chips_cited` — search plus what the model itself reported. Right for the
  grammar drill, whose sentences are INVENTED from the material and then grammatically
  transformed on top. Such a claim is far from every chunk by construction, so the search
  alone left roughly half a set chip-less while the other half was cited, which reads to a
  learner as "this sentence has no source" although it has one.
"""

from loguru import logger

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_attribution import attribute_claims


# Prompt-Zeile, die das ``page``-Feld anfordert, das :func:`attach_chips_cited` liest.
# Sie steht hier und nicht in den Generatoren, damit die Frage und ihr Leser zusammen
# liegen: ändert sich das Feld, ändert sich beides an einer Stelle.
PAGE_RULE = (
    "- 'page' is the page number printed in front of the passage you took the facts "
    "from, copied from its \"[file, S. <number>]\" label above. Every exercise carries "
    "one, and it is always a plain number.\n"
)


def attribution_inputs(ctx: QuelleContext) -> tuple[int | None, list[int], dict[int, str]]:
    """Build (workspace_id, source_ids, source_id->label) for the active sources."""
    items = list(ctx.source_by_name.items())
    workspace_id = items[0][1].get("workspace_id") if items else None
    source_ids = [src["id"] for _, src in items]
    id_to_label = {src["id"]: name for name, src in items}
    return workspace_id, source_ids, id_to_label


def attach_chips(
    items: list[dict],
    claims: list[str],
    ctx: QuelleContext,
    *,
    multi: bool = False,
    embed_fn=None,
    search_fn=None,
) -> list[dict]:
    """Attribute each item's ``claim`` and attach nav-only ``sources`` (+ primary
    source_label/page_number/start_time from the first chip). Items that ground nowhere
    get no chip (their source fields are cleared), never a guessed page."""
    workspace_id, source_ids, id_to_label = attribution_inputs(ctx)
    chip_lists = attribute_claims(
        claims, id_to_label, multi=multi,
        workspace_id=workspace_id, source_ids=source_ids,
        # Clamp chips to the pages the LLM was actually shown (chat-style seen-check):
        # a card can only cite material from its own generation context, never elsewhere.
        # `or None` is a safety net: an empty seen-set would otherwise strip EVERY chip.
        seen_pages_by_source=ctx.seen_pages_by_source or None,
        embed_fn=embed_fn, search_fn=search_fn,
    )
    for item, chips in zip(items, chip_lists):
        _write_chips(item, chips)
    return items


def _write_chips(item: dict, chips: list[dict]) -> None:
    """Put ``chips`` on an item, or clear its source fields when there are none.

    The primary fields mirror the first chip because the views read those directly
    (older sets predate the ``sources`` list)."""
    if not chips:
        item.pop("sources", None)
        item["source_label"] = None
        item["page_number"] = None
        item["start_time"] = None
        return
    item["sources"] = chips
    item["source_label"] = chips[0]["source_label"]
    item["page_number"] = chips[0]["page_number"]
    item["start_time"] = chips[0]["start_time"]


def attach_chips_cited(
    items: list[dict],
    claims: list[str],
    ctx: QuelleContext,
    *,
    embed_fn=None,
    search_fn=None,
) -> list[dict]:
    """Attach one nav-only chip per item, taking the most trustworthy origin available.

    Three steps, in this order:

    1. the page the model itself cited while writing the sentence (``item['_page']``),
       accepted only if the model was actually shown that page,
    2. otherwise the shared pgvector search — run ONLY for the items step 1 left open, so
       the common case costs neither an embedding call nor a vector search,
    3. otherwise the source the model named as its section, cited at its first shown page.

    Step 1 is the accurate one and it is free: the model knows where it took the material
    from, we only have to ask. Step 3 is navigation rather than pinpointing, which is the
    honest promise for an invented sentence anyway ("the material is here"), and it is what
    turns a set with scattered chips into one where every sentence carries its origin.

    One gap stays open on purpose: several sources, no cited page, no named section and no
    search hit. Guessing a source there would be worse than staying silent, so the item
    keeps no chip and the counts below make it visible.
    """
    workspace_id, source_ids, id_to_label = attribution_inputs(ctx)
    chips: list[dict | None] = [_cited_chip(item, ctx, id_to_label) for item in items]
    from_model = sum(chip is not None for chip in chips)

    open_idx = [i for i, chip in enumerate(chips) if chip is None]
    if open_idx:
        found = attribute_claims(
            [claims[i] if i < len(claims) else "" for i in open_idx],
            id_to_label, multi=False,
            workspace_id=workspace_id, source_ids=source_ids,
            seen_pages_by_source=ctx.seen_pages_by_source or None,
            embed_fn=embed_fn, search_fn=search_fn,
        )
        for i, hits in zip(open_idx, found):
            if hits:
                chips[i] = hits[0]
    from_search = sum(chip is not None for chip in chips) - from_model

    for i, chip in enumerate(chips):
        if chip is None:
            chips[i] = _section_chip(items[i], ctx, id_to_label)

    for item, chip in zip(items, chips):
        item.pop("_page", None)
        item.pop("_source_label", None)
        _write_chips(item, [chip] if chip else [])

    missing = sum(chip is None for chip in chips)
    logger.info(
        "KI Tutor: Quellenchips {} vom Modell, {} aus der Suche, {} über die Sektion, {} ohne",
        from_model, from_search, len(chips) - from_model - from_search - missing, missing,
    )
    return items


def _cited_page(value) -> int | None:
    """The page the model claims it used, as a plain page number.

    Models write JSON numbers as strings often enough that a digit string counts, but
    anything else ("Seite 4", a range, a bool) is not an answer to the question asked
    and must fall through to the search rather than become a chip.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value.isdigit():
            return None
        value = int(value)
    if not isinstance(value, int) or value < 1:
        return None
    return value


def _named_source_id(item: dict, ctx: QuelleContext) -> int | None:
    """Source id the model named for this item, or None if it named nothing known.

    Two ways to name one, because the tools ask differently: the listening tool asks for
    the filename outright (``_source_label``), the others only for the numbered section
    the coverage rule hands out (``_section``). A filename that is not in this context is
    invented and counts as nothing.
    """
    label = (item.get("_source_label") or "").strip()
    if label and label in ctx.source_by_name:
        return ctx.source_by_name[label].get("id")
    try:
        num = int(item.get("_section"))
    except (TypeError, ValueError):
        return None
    source = ctx.source_by_name.get(ctx.sections.get(num) or "") or {}
    return source.get("id")


def _is_media(ctx: QuelleContext, source_id: int) -> bool:
    """Whether this source went into the context as timed segments (audio/video).

    Read off the timestamp map rather than the filename, so no extension list has to be
    kept in sync.
    """
    return bool(ctx.media_start_by_page.get(source_id))


def _chip_for_page(source_id: int, page: int, label: str) -> dict:
    """Nav chip for a page of the generation context. Documents only."""
    return {"source_label": label, "page_number": page, "start_time": None}


def _source_only_chip(label: str) -> dict:
    """Chip that names the source and nothing else: "the material is in this file".

    What media falls back to. A wrong minute inside a 45-minute recording sends the
    learner somewhere unrelated, which is worse than not offering a jump at all.
    """
    return {"source_label": label, "page_number": None, "start_time": None}


def _cited_chip(item: dict, ctx: QuelleContext, id_to_label: dict[int, str]) -> dict | None:
    """Step 1: the page the model named, cross-checked against what it was shown.

    The page alone identifies the source whenever only one source showed it. When several
    did, the model's own section claim breaks the tie, and a claim that contradicts the
    page is not trusted at all.

    Documents only. Measured on real sets: for a slide deck the cited page is right, even
    exactly right where the sentence sits on it, but for a lecture recording the model
    writes down any number — three sentences in one set carried the same segment number
    and none of them was about what is said there. The difference is what the number MEANS
    to the model: a slide page is a visible unit, while a transcript is 105 interchangeable
    30-second blocks labelled "S. 1", "S. 2" … So for media this step abstains and the
    search decides, because it compares actual transcript text.
    """
    page = _cited_page(item.get("_page"))
    if page is None:
        return None
    owners = [sid for sid, pages in ctx.seen_pages_by_source.items() if page in pages]
    if not owners:
        return None
    named = _named_source_id(item, ctx)
    source_id = named if named is not None else (owners[0] if len(owners) == 1 else None)
    if source_id is None or source_id not in owners:
        return None
    if _is_media(ctx, source_id):
        return None
    return _chip_for_page(source_id, page, id_to_label.get(source_id, ""))


def _section_chip(item: dict, ctx: QuelleContext, id_to_label: dict[int, str]) -> dict | None:
    """Step 3: cite the source the sentence came from, at its first shown page.

    With a single source that source is known regardless of what the model wrote, which is
    what makes the common case chip-less-proof.
    """
    source_id = _named_source_id(item, ctx)
    if source_id is None:
        shown = list(ctx.seen_pages_by_source)
        if len(shown) != 1:
            return None
        source_id = shown[0]
    label = id_to_label.get(source_id, "")
    # Media gets the file and no timestamp: the first shown segment is not where the
    # sentence came from, it is merely the earliest one in this run.
    if _is_media(ctx, source_id):
        return _source_only_chip(label)
    pages = ctx.seen_pages_by_source.get(source_id) or set()
    if not pages:
        return None
    return _chip_for_page(source_id, min(pages), label)
