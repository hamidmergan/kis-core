"""Prompts of the source summary during ingest (map-reduce)."""


def aia_summary_system() -> str:
    """System prompt for the per-source summary, deliberately not exhaustive."""
    return (
        "Write a CONCISE summary of the following content.\n"
        "The content is one part of a larger document (PDF text or a media transcript).\n"
        "Rules:\n"
        "1. Write in the DOMINANT language of the input (judge by the majority of words; ignore isolated technical terms, proper nouns, citations, loanwords).\n"
        "2. Base it ONLY on the provided content. Never add or invent information.\n"
        "3. Be CONCISE: capture the main topics. Keep key named terms, definitions, names and dates spelled exactly as written (do not invent sub-numbers). Brevity over detail — do NOT enumerate every single item.\n"
        "4. Output ONLY the summary (short bullet points or a short paragraph). No preamble, no closing remarks.\n"
    )


def aia_summary_user(content: str) -> str:
    """User message for a single summary (map) call."""
    return f"Content to summarize:\n\n{content}"


def aia_summary_combine_system() -> str:
    """System prompt for merging per-batch partial summaries into ONE doc summary."""
    return (
        "Write a CONCISE summary of the following, which are partial summaries of consecutive parts of the SAME document.\n"
        "Rules:\n"
        "1. Write in the DOMINANT language of the partials.\n"
        "2. Use ONLY what the partials contain. Never add or invent information.\n"
        "3. Be CONCISE: ONE coherent summary of the whole document, main topics in document order, overlaps stated once (no repetition). Brevity over detail.\n"
        "4. SECTION NUMBERS (e.g. '§ 211', 'Art. 5', 'Kapitel 3'): carry a number over ONLY if a partial explicitly attaches it to that exact term. NEVER assign, guess, or attach a number yourself, and never infer one from order or proximity. If a topic has no number in the partials, name it WITHOUT a number.\n"
        "5. Output ONLY the merged summary. No preamble, no mention of 'partials', 'parts', or that a merge happened.\n"
    )


def aia_summary_combine_user(partials: list[str]) -> str:
    """User message for the combine (reduce) call."""
    blocks = "\n\n".join(
        f"--- Part {i} ---\n{p}" for i, p in enumerate(partials, 1)
    )
    return (
        "Below are partial summaries of consecutive parts of the SAME document. "
        "Merge them into ONE coherent document summary following the rules.\n\n"
        f"{blocks}"
    )
