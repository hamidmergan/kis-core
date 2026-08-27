"""After-the-fact evidence search for the data table, with its own context."""

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
    """One batched attribution for many statements, limited to seen pages."""
    if not claims:
        return []
    return attribute_claims(
        claims, source_id_to_label, multi=False, max_distance=max_distance,
        workspace_id=workspace_id, source_ids=source_ids,
        seen_pages_by_source=seen_pages_by_source or None,
    )
