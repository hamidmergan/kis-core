"""The stored summary of a source, shaped so the chat can read it like a chunk."""

# How much of one source's summary travels, a summary is short anyway.
MAX_SUMMARY_CHARS = 4000


def gekuerzt(chunks: list[dict], budget: int) -> list[dict]:
    """The summaries share the budget evenly, each cut at its last full sentence.

    A summary opens with what the source is about, so its beginning is what an overview
    needs. Below the share nothing changes, a few sources keep their whole summaries.
    """
    if not chunks:
        return chunks
    anteil = max(1, budget // len(chunks))
    return [c if len(c["content"]) <= anteil else {**c, "content": _bis_zum_satzende(c["content"], anteil)}
            for c in chunks]


def _bis_zum_satzende(text: str, grenze: int) -> str:
    stueck = text[:grenze]
    ende = max(stueck.rfind(". "), stueck.rfind(".\n"), stueck.rfind("! "), stueck.rfind("? "))
    return stueck[:ende + 1] if ende > grenze // 3 else stueck.rstrip()


def summary_chunks(sources: list[dict]) -> list[dict]:
    """One page-less chunk per source that carries a summary, the others yield nothing."""
    out: list[dict] = []
    for s in sources:
        summary = (s.get("summary") or "").strip()
        if summary:
            out.append({"source_id": s["id"], "page_number": None, "start_time": None,
                        "content": summary[:MAX_SUMMARY_CHARS]})
    return out
