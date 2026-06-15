"""Post-hoc attribution wiring for the studio tools (data table, mindmap).

Unlike the language-training tools these build their own context (no ``QuelleContext``),
so they call the service-level :func:`attribute_claims` directly and convert each nav chip
into the page field their frontend reads: a page NUMBER for a PDF, or a ``"h:mm:ss"`` timestamp
STRING for media. Same pgvector gate/selector as the chat, nav-only, seen-clamped — replaces
the old LLM-guessed page numbers + highlight/keyword strings."""

from src.services.aia_attribution import attribute_claims, _GENERIC_ATTRIB_MAX_DIST


def _fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def nav_page_value(chip: dict):
    """Studio page field from a service chip: ``"h:mm:ss"`` for media, page number for a PDF."""
    if chip.get("start_time") is not None:
        return _fmt_ts(chip["start_time"])
    return chip.get("page_number")


def attribute_studio_claims(
    claims: list[str],
    *,
    workspace_id: int | None,
    source_ids: list[int],
    source_id_to_label: dict[int, str],
    seen_pages_by_source: dict[int, set] | None,
    max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
) -> list[list[dict]]:
    """One batched attribution for a list of claim texts -> one chip-list per claim.

    Chips are clamped to the pages actually shown to the model (``seen_pages_by_source``), so a
    citation can never point at a page that was not in the generation context. ``max_distance``
    lets a thin-claim caller (mindmap) tighten the gate so weak matches abstain."""
    if not claims:
        return []
    return attribute_claims(
        claims, source_id_to_label, multi=False, max_distance=max_distance,
        workspace_id=workspace_id, source_ids=source_ids,
        seen_pages_by_source=seen_pages_by_source or None,
    )
