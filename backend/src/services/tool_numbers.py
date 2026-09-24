"""The numbers of the tools that the management may turn, all of them in one table.

A tool enters a number here once. That single entry carries everything the number needs:
what it is called in the database, what it may be, whose right it hangs off and which
tool's tab it belongs on. The admin route builds its field, its range check and its
permission check out of it, and the tool reads its value through ``value_of``.

Read on every use, so a change reaches a running worker without a restart. Nothing stored
can stop a run: a missing or unreadable entry falls back to the value from limits.py, and
a value outside its range is pulled back to the nearest end.
"""

from dataclasses import dataclass

from loguru import logger

from src.limits import (
    AIA_SOURCE_MAX_CHARS,
    SUMMARY_CALL_TIMEOUT_SECONDS,
    SUMMARY_MAX_OUTPUT_TOKENS,
    SUMMARY_READ_MAX_FACTS,
)
from src.permissions_registry import PERM_SET_AIA_SOURCES, PERM_SET_TOOLS_LIMITS


@dataclass(frozen=True)
class Number:
    """One number of one tool, everything about it in one place."""

    key: str
    # The tool it belongs to, the admin area groups its tab by this.
    tool: str
    # What holds without an entry, always a value from limits.py.
    default: int
    smallest: int
    largest: int
    permission: str


# One block per tool. A new tool adds its block here and nowhere else in the backend.
NUMBERS: tuple[Number, ...] = (
    # --- Francis ------------------------------------------------------------
    # Checked when a workspace document is read, a larger one fails instead of being cut.
    Number("aia_source_max_chars", "aia",
           AIA_SOURCE_MAX_CHARS, 30_000, 500_000, PERM_SET_AIA_SOURCES),
    # --- Zusammenfassung ----------------------------------------------------
    Number("summary_read_max_facts", "summary",
           SUMMARY_READ_MAX_FACTS, 10, 80, PERM_SET_TOOLS_LIMITS),
    # The provider drops a call at about 300 s, ours has to fire first.
    Number("summary_call_timeout_seconds", "summary",
           SUMMARY_CALL_TIMEOUT_SECONDS, 60, 300, PERM_SET_TOOLS_LIMITS),
    Number("summary_max_output_tokens", "summary",
           SUMMARY_MAX_OUTPUT_TOKENS, 2_048, 12_000, PERM_SET_TOOLS_LIMITS),
)

BY_KEY: dict[str, Number] = {n.key: n for n in NUMBERS}


def of_tool(tool: str) -> tuple[Number, ...]:
    """The numbers of one tool, in the order of the table."""
    return tuple(n for n in NUMBERS if n.tool == tool)


def permission_for(key: str) -> str | None:
    """The right this number hangs off, None when no tool entered it."""
    eintrag = BY_KEY.get(key)
    return eintrag.permission if eintrag else None


def value_of(key: str) -> int:
    """The stored number, pulled into its range, the default when nothing usable is there."""
    eintrag = BY_KEY[key]
    from src import database as db
    try:
        wert = int(db.get_setting(key, str(eintrag.default)))
    except Exception as e:  # noqa: BLE001 - a broken setting must never sink a run
        logger.warning("Einstellung '{}' unbrauchbar ({}), es gilt {}",
                       key, e, eintrag.default)
        return eintrag.default
    return max(eintrag.smallest, min(eintrag.largest, wert))
