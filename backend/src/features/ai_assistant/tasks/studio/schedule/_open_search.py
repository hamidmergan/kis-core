"""Finds appointments whose date is still open, by meaning instead of by pattern."""

# One wording per language the application serves, the search runs once per entry.
QUERIES = (
    "Der Termin wird noch bekannt gegeben, das Datum steht noch nicht fest.",
    "The date will be announced later, the appointment is not fixed yet.",
)
# Room enough for a whole module, the model sorts the rest out.
_LIMIT_PER_QUERY = 25


def open_spots_for_workspace(workspace_id, source_ids, *, embed, search) -> set[int]:
    """The ids of the chunks that read like an appointment without a date."""
    spots: set[int] = set()
    for query in QUERIES:
        for chunk in search(workspace_id, query, embed(query), source_ids,
                            _LIMIT_PER_QUERY) or []:
            cid = chunk.get("id")
            if cid is not None and (chunk.get("content") or "").strip():
                spots.add(cid)
    return spots
