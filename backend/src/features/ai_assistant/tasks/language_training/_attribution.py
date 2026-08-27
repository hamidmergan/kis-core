"""Connects the generated exercises to the shared after-the-fact evidence search."""

from loguru import logger

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_attribution import attribute_claims


# The prompt line requesting the page field sits next to its reader.
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
    segments_fn=None,
) -> list[dict]:
    """Backs every exercise and attaches the chips, without a hit it stays chip free."""
    workspace_id, source_ids, id_to_label = attribution_inputs(ctx)
    chip_lists = attribute_claims(
        claims, id_to_label, multi=multi,
        workspace_id=workspace_id, source_ids=source_ids,
        # Chips only onto shown pages, 'or None' guards against an empty set.
        seen_pages_by_source=ctx.seen_pages_by_source or None,
        embed_fn=embed_fn, search_fn=search_fn, segments_fn=segments_fn,
    )
    for item, chips in zip(items, chip_lists):
        _write_chips(item, chips)
    return items


def _write_chips(item: dict, chips: list[dict]) -> None:
    """Puts the chips on an exercise or clears its source fields."""
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
    segments_fn=None,
) -> list[dict]:
    """Attaches one chip per exercise, in three stages from the most reliable origin."""
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
            embed_fn=embed_fn, search_fn=search_fn, segments_fn=segments_fn,
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
    """The page the model names, as a bare number."""
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
    """The source the model names for this exercise, or None."""
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
    """Whether this source went into the context as time segments."""
    return bool(ctx.media_start_by_page.get(source_id))


def _chip_for_page(source_id: int, page: int, label: str) -> dict:
    """Nav chip for a page of the generation context. Documents only."""
    return {"source_label": label, "page_number": page, "start_time": None}


def _source_only_chip(label: str) -> dict:
    """Chip that names only the source, without a jump target."""
    return {"source_label": label, "page_number": None, "start_time": None}


def _cited_chip(item: dict, ctx: QuelleContext, id_to_label: dict[int, str]) -> dict | None:
    """The page named by the model, checked against what was shown, documents only."""
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
    """Names the sentence's source at its first shown page."""
    source_id = _named_source_id(item, ctx)
    if source_id is None:
        shown = list(ctx.seen_pages_by_source)
        if len(shown) != 1:
            return None
        source_id = shown[0]
    label = id_to_label.get(source_id, "")
    # Media get the file without a timestamp, the first segment says nothing.
    if _is_media(ctx, source_id):
        return _source_only_chip(label)
    pages = ctx.seen_pages_by_source.get(source_id) or set()
    if not pages:
        return None
    return _chip_for_page(source_id, min(pages), label)
