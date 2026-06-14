"""Tool-side wiring for the shared post-hoc attribution.

Turns a generated item's claim text into nav-only source chips via the SAME pgvector
gate/selector the chat uses (:mod:`src.services.aia_attribution`). Replaces the per-tool
page-guessing heuristics (find_all_pages, word-overlap, whole-page highlight) with one path.
"""

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_attribution import attribute_claims


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
        embed_fn=embed_fn, search_fn=search_fn,
    )
    for item, chips in zip(items, chip_lists):
        if chips:
            item["sources"] = chips
            item["source_label"] = chips[0]["source_label"]
            item["page_number"] = chips[0]["page_number"]
            item["start_time"] = chips[0]["start_time"]
        else:
            item.pop("sources", None)
            item["source_label"] = None
            item["page_number"] = None
            item["start_time"] = None
    return items
