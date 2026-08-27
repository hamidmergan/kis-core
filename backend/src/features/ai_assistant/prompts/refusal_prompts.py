"""Refusal sentences of the AI assistant and how they are detected in the answer."""

import re


# Refusal sentence compared verbatim, and at the same time the anchor for the distance.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Materialien enthalten.",
}

# Language of the one anchor that the distance is measured against.
_MESS_LOCALE = "de"

# Safety net for the old wording the model still writes out of habit.
_GAP_ANCHORS: tuple[str, ...] = (
    "steht nicht in den materialien",
    "stehen nicht in den materialien",
    "steht nicht in den quellen",
    "stehen nicht in den quellen",
)

# A sentence has an end mark, a bare term does not.
_SATZENDE = ".!?"

# Nobody writes more words than this as a mere naming.
_MAX_BEGRIFF_WOERTER = 4

# Edge characters that fall off before the comparison.
_SENTINEL_TRIM = " \t\r\n*_`\"'“”„«».!"

# Sentence end with a follower, deliberately rough.
_MORE_THAN_ONE_SENTENCE = re.compile(r"[.!?][\"'”’)\]]?\s+[^\Wa-z\d_]", re.UNICODE)


def _sentinel_key(text: str | None) -> str:
    """Comparison form of a sentence: whitespace normalised, edge characters off, lowercased."""
    return " ".join((text or "").split()).strip(_SENTINEL_TRIM).casefold()


def refusal_reference_texts() -> list[str]:
    """The sentence measured against by embedding, the German one has proven enough."""
    return [RAG_NO_INFO_SENTINEL[_MESS_LOCALE]]


def is_only_gap(answer: str | None, gap: str | None) -> bool:
    """True when the whole answer is only the refusal sentence from the ``gap`` field."""
    schluessel = _sentinel_key(gap)
    return bool(schluessel) and _sentinel_key(answer) == schluessel


def is_gap_line(text: str | None) -> bool:
    """True when this line is a refusal and therefore gets NO source chip."""
    key = _sentinel_key(text)
    return bool(key) and any(anchor in key for anchor in _GAP_ANCHORS)


def is_sentinel_refusal(text: str | None) -> bool:
    """True when the WHOLE answer is only the refusal and post-processing can be skipped."""
    key = _sentinel_key(text)
    if not key:
        return False
    if any(key == _sentinel_key(s) for s in RAG_NO_INFO_SENTINEL.values()):
        return True
    if _MORE_THAN_ONE_SENTENCE.search(" ".join((text or "").split())):
        return False
    return is_gap_line(text)


def is_bare_term(text: str | None) -> bool:
    """True when only the term stands here instead of a sentence, for reporting only."""
    kern = (text or "").strip()
    return bool(kern) and kern[-1] not in _SATZENDE and len(kern.split()) <= _MAX_BEGRIFF_WOERTER
