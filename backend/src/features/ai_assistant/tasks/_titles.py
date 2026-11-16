"""The display name of a generated result, kept apart from the names already taken."""

# The length the title columns and the interface work with.
MAX_TITLE_LEN = 120

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
