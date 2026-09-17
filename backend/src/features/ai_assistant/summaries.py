"""The stored summary of a source, shaped so the chat can read it like a chunk."""

# How much of one source's summary travels, a summary is short anyway.
MAX_SUMMARY_CHARS = 4000


def summary_chunks(sources: list[dict]) -> list[dict]:
    """One page-less chunk per source that carries a summary, the others yield nothing."""
    out: list[dict] = []
    for s in sources:
        summary = (s.get("summary") or "").strip()
        if summary:
            out.append({"source_id": s["id"], "page_number": None, "start_time": None,
                        "content": summary[:MAX_SUMMARY_CHARS]})
    return out
