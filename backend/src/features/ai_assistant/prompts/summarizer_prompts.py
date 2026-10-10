"""Prompts of the source summary during ingest (map-reduce)."""


def _language_rule(language: str | None, of: str) -> str:
    """A language read from the text is fixed, without one the model judges the majority."""
    if language:
        return (f"1. Write in {language}. This is fixed. Technical terms, headings, names or citations "
                f"in other languages never change your output language.\n")
    return (f"1. Write in the DOMINANT language of the {of} (judge by the majority of words; ignore "
            "isolated technical terms, proper nouns, citations, loanwords).\n")


def aia_summary_system(language: str | None = None) -> str:
    """System prompt for the per-source summary, deliberately not exhaustive."""
    return (
        "Write a CONCISE summary of the following content.\n"
        "The content is one part of a larger document (PDF text or a media transcript).\n"
        "Rules:\n"
        + _language_rule(language, "input") +
        "2. Base it ONLY on the provided content. Never add or invent information.\n"
        "3. Be CONCISE: capture the main topics. Keep key named terms, definitions, names and dates spelled exactly as written (do not invent sub-numbers). Brevity over detail — do NOT enumerate every single item.\n"
        "4. Output ONLY the summary (short bullet points or a short paragraph). No preamble, no closing remarks.\n"
        "5. NEVER comment on your own writing and never correct yourself in the answer. No 'wait', no 'let me rephrase', no rows of dashes or slashes. Write the summary once, straight through.\n"
    )


def aia_summary_user(content: str) -> str:
    """User message for a single summary (map) call."""
    return f"/no_think\nContent to summarize:\n\n{content}"


def aia_summary_combine_system(language: str | None = None) -> str:
    """System prompt for merging per-batch partial summaries into ONE doc summary."""
    return (
        "Write a CONCISE summary of the following, which are partial summaries of consecutive parts of the SAME document.\n"
        "Rules:\n"
        + _language_rule(language, "partials") +
        "2. Use ONLY what the partials contain. Never add or invent information.\n"
        "3. Be CONCISE: ONE coherent summary of the whole document, main topics in document order, overlaps stated once (no repetition). Brevity over detail.\n"
        "4. SECTION NUMBERS (e.g. '§ 211', 'Art. 5', 'Kapitel 3'): carry a number over ONLY if a partial explicitly attaches it to that exact term. NEVER assign, guess, or attach a number yourself, and never infer one from order or proximity. If a topic has no number in the partials, name it WITHOUT a number.\n"
        "5. Output ONLY the merged summary. No preamble, no mention of 'partials', 'parts', or that a merge happened.\n"
        "6. NEVER comment on your own writing and never correct yourself in the answer. No 'wait', no 'let me rephrase', no rows of dashes or slashes. Write the summary once, straight through.\n"
    )


def aia_summary_combine_user(partials: list[str]) -> str:
    """User message for the combine (reduce) call."""
    blocks = "\n\n".join(
        f"--- Part {i} ---\n{p}" for i, p in enumerate(partials, 1)
    )
    return (
        "/no_think\n"
        "Below are partial summaries of consecutive parts of the SAME document. "
        "Merge them into ONE coherent document summary following the rules.\n\n"
        f"{blocks}"
    )
