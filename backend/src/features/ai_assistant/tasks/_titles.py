"""The display name of a generated result, built from the result itself."""

from loguru import logger

# The length the title columns and the interface work with.
MAX_TITLE_LEN = 120

# The title call sees this many entries, more only makes it costlier.
_MAX_ENTRIES = 10
_MAX_ENTRY_LEN = 160


def title_from_entries(client, model, entries: list[str], fallback: str,
                       avoid: list[str] | None = None) -> str:
    """Generates a short title from the entries, avoid names the ones already taken."""
    sauber = [str(e).strip() for e in entries if str(e or "").strip()]
    if not sauber:
        return fallback
    preview = "\n".join(f"- {e[:_MAX_ENTRY_LEN]}" for e in sauber[:_MAX_ENTRIES])
    avoid_rule = ""
    if avoid:
        avoid_rule = (
            " These titles are already taken and MUST NOT be used, not even with a single "
            "word changed, added or removed: " + "; ".join(t for t in avoid[:10] if t) + "."
        )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Provide a short, concise title (max 6 words) for this material "
                    "that reflects the concrete topic of the entries below. "
                    # Without this the model reaches past the material for the document name.
                    "Name the specific thing the entries have in common, for example the "
                    "step, the activity or the material they are about. Do NOT name the "
                    "document, the lecture, the course or the field as a whole. "
                    "Respond in the same language as the entries. "
                    "Respond ONLY with the title, no quotation marks."
                    + avoid_rule
                )},
                {"role": "user", "content": f"Entries:\n{preview}"},
            ],
            temperature=0.7,
            # Generous budget, a thinking model needs room before the first character.
            max_tokens=400,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # Only the first non-empty line, the title column is single-line.
        t = next((ln.strip().strip('"\'') for ln in raw.splitlines() if ln.strip()), "")[:MAX_TITLE_LEN]
        if not t:
            logger.warning("Title: empty LLM response, falling back to {!r}", fallback)
        return t or fallback
    except Exception as e:
        logger.warning("Title generation failed ({}), falling back to {!r}", e, fallback)
        return fallback


# From this similarity on two titles read as the same.
_SAME_TITLE_RATIO = 0.90


def is_title_taken(title: str, existing: list[str]) -> bool:
    """Whether a title sounds to a human like one of the existing ones."""
    from difflib import SequenceMatcher
    from src.services.aia_grammar_check import normalize

    want = normalize(title)
    if not want:
        return False
    for other in existing:
        have = normalize(other)
        if have and (want == have or SequenceMatcher(None, want, have).ratio() >= _SAME_TITLE_RATIO):
            return True
    return False


def next_free_counter(title: str, taken: list[str]) -> str:
    """Appends the smallest free number, counted across the whole title family."""
    used: set[int] = set()
    for other in taken:
        if not is_title_taken(title, [other]):
            continue
        tail = (other or "").rstrip().rsplit("(", 1)
        if len(tail) == 2 and tail[1].rstrip().endswith(")"):
            digits = tail[1].rstrip()[:-1].strip()
            if digits.isdigit():
                used.add(int(digits))
    n = 2
    while n in used:
        n += 1
    return f"{title} ({n})"


def resolve_title(client, model, taken: list[str], fallback: str, entries: list[str]) -> str:
    """The name a finished result gets."""
    fallback = (fallback or "").strip()
    if not entries:
        return fallback

    title = (title_from_entries(client, model, entries, fallback, avoid=taken) or "").strip()
    if not title:
        title = fallback
    if not title or not is_title_taken(title, taken):
        return title

    # Second attempt, this time naming the title it collided with.
    clashing = [t for t in taken if is_title_taken(title, [t])]
    retitled = (title_from_entries(client, model, entries, "", avoid=clashing + taken) or "").strip()
    if retitled and not is_title_taken(retitled, taken):
        return retitled

    return next_free_counter(title, taken)
