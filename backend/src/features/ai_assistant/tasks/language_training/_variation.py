"""Keeps generated sets from repeating themselves.

Second variation lever next to the page rotation in ``_context``. The rotation moves the
CONTEXT away from recently used pages; this module handles the one thing the rotation
cannot touch, the set TITLE. The model never learns that a set already exists, so it
names the document instead of the set and several sets end up sharing one title.

Only titles, deliberately. Listing the earlier ITEMS was tried and reverted: fed back into
the prompt they act as few-shot material and the model copies them verbatim (see the
comments in the generators). A title is a single short string with no such pull.

Language-agnostic by construction: nothing here inspects words, it only passes back text
the model itself produced earlier.
"""

# The block sits in front of an already large context, so it stays a footnote.
_MAX_TITLES = 10
_MAX_LEN = 90


def title_avoidance_block(titles: list[str]) -> str:
    """Prompt block naming the titles already in use. Empty when there are none.

    Carries a leading blank line, so a caller can append it to a system prompt without
    checking whether it is empty.
    """
    seen: set[str] = set()
    picked: list[str] = []
    for raw in titles:
        text = " ".join((raw or "").split())[:_MAX_LEN]
        key = text.casefold()
        if not text or key in seen:
            continue
        seen.add(key)
        picked.append(text)
        if len(picked) >= _MAX_TITLES:
            break
    if not picked:
        return ""
    return (
        "\n\nTITLES ALREADY IN USE in this workspace:\n"
        + "\n".join(f"  - {t}" for t in picked)
        + "\nThe new title MUST differ from every one of them. Name what THIS set is "
        "actually about, taken from the exercises you just wrote, not the document as a "
        "whole. Never reuse a title from the list above."
    )


def build_title_avoidance_block(workspace_id: int | None, tool: str) -> str:
    """The block for this workspace+tool, read from the finished sets.

    A missing workspace (older queued tasks) or a failing query yields an empty block
    rather than an error: a duplicate title is a blemish, never a reason to fail a set.
    """
    if not workspace_id:
        return ""
    from src import database as db
    try:
        return title_avoidance_block(db.get_recent_exercise_titles(workspace_id, tool))
    except Exception:  # noqa: BLE001
        return ""


# Above this similarity two titles read as the same one to a human. Measured against real
# titles from one document: a one-letter variant of the same title scores 0.99, while
# "… im Seminar: Passiv üben" against "… im Seminar" scores 0.85 and is clearly its own
# title. The threshold sits between the two. Substring containment is deliberately NOT a
# criterion: a longer, more specific title is exactly what we want to keep.
_SAME_TITLE_RATIO = 0.90


def is_title_taken(title: str, existing: list[str]) -> bool:
    """Whether ``title`` reads as one of ``existing`` to a human.

    Not an equality check. The model varies a title by a single letter and calls it new,
    which is how one workspace ended up with "Wissenschaftliche Arbeiten im Seminar" next
    to "Wissenschaftliches Arbeiten im Seminar".

    Language-agnostic: normalisation goes by Unicode category, similarity by character
    overlap. No word list anywhere.
    """
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


def _next_free_counter(title: str, taken: list[str]) -> str:
    """``title (n)`` with the lowest n not yet used by this title's own family.

    Counting only exact matches was the bug behind two sets both ending in "(2)": their
    bases differed by a letter, so neither saw the other. The family is therefore
    everything ``is_title_taken`` considers the same title, and ``normalize`` drops the
    bracketed counter, so a counted title lands in its own family.
    """
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


def resolve_set_title(client, model, workspace_id: int | None, tool: str,
                      fallback: str, items: list[dict]) -> str:
    """The name a finished set gets.

    Built from the set's OWN items rather than from the generation call. That call sees
    the whole document and therefore keeps naming the document, which is why every set
    from one script came out as a variant of its title. The items are what actually
    differs between two sets of the same document.

    ``fallback`` is the title the generation call proposed; it is used only when the
    title call gives nothing back.

    Costs one model call per set, and a second one only when the first result still
    reads like a title the workspace already has.
    """
    from src.features.ai_assistant.tasks.language_training._title import title_from_items

    fallback = (fallback or "").strip()
    if not workspace_id or not items:
        return fallback
    from src import database as db
    try:
        taken = db.get_recent_exercise_titles(workspace_id, tool, limit=100)
    except Exception:  # noqa: BLE001 - never fail a finished set over its name
        return fallback

    title = (title_from_items(client, model, items, fallback, avoid=taken) or "").strip()
    if not title:
        title = fallback
    if not title or not is_title_taken(title, taken):
        return title

    # Second attempt, this time naming the title it collided with.
    clashing = [t for t in taken if is_title_taken(title, [t])]
    retitled = (title_from_items(client, model, items, "", avoid=clashing + taken) or "").strip()
    if retitled and not is_title_taken(retitled, taken):
        return retitled

    return _next_free_counter(title, taken)


__all__ = [
    "title_avoidance_block",
    "build_title_avoidance_block",
    "resolve_set_title",
    "is_title_taken",
]
