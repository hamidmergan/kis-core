"""The four presentation formats of the grammar exercise and the choice beneath."""

# The four formats in distribution order, the reshaping first.
KINDS = ("transform", "cloze", "statement", "choice")


def clean_kinds(roh) -> list[str] | None:
    """The selection in catalogue order, None means mixed."""
    if not isinstance(roh, list):
        return None
    gewaehlt = {k for k in roh if isinstance(k, str) and k in KINDS}
    if not gewaehlt or len(gewaehlt) == len(KINDS):
        return None
    return [k for k in KINDS if k in gewaehlt]


__all__ = ["KINDS", "clean_kinds"]
