"""Pure weighting and appendix logic for the per-user learner profile.

A learner's weaknesses (translations, glossary terms, quiz slips, tool use) are
accumulated into ONE bounded profile. This module holds every decision as a pure,
side-effect-free function so it is unit-testable without a database, exactly like
aia_adaptive_chat.py. The repository does only thin SQL and calls these functions.

Design rules live in the spec: bounded (cap), self-decaying (window), gentle (a
single event never crosses the act threshold), and level-independent (the focus
help works for every learner, not only CEFR learners).
"""

from datetime import datetime

CATEGORY_TERM = "term"
CATEGORY_PASSAGE = "passage"
CATEGORY_TOOL = "tool"
# Only these categories feed the answer hint. A tool name is not a term to explain,
# so tool use shows up in the profile and export but never in the prompt appendix.
FOCUS_CATEGORIES = (CATEGORY_TERM, CATEGORY_PASSAGE)

BASE_WEIGHTS = {
    "quiz_wrong": 3.0,
    "quiz_hint": 2.0,
    "quiz_explain": 2.0,
    "translate_passage": 2.0,
    "translate_word": 1.0,
    "glossary": 1.0,
    "tool_use": 0.5,
}

DEFAULT_WINDOW_DAYS = 30
# Strictly below the wrong+hint sum (3.0 + 2.0 = 5.0), the canonical trigger from
# the spec, so continuous time-decay does not immediately push a just-accumulated
# 5.0 term back under the line: it is read a moment later with a tiny positive age,
# so its effective weight is a hair under 5.0. At 4.5 it stays in focus for about
# 3 days on the default 30-day window instead of vanishing at once. Still strictly
# above the largest single base weight (3.0), so one event alone never triggers,
# and above the wrong+glossary / two-hint sum (4.0), which should stay quiet.
ACT_THRESHOLD = 4.5
FOCUS_TOP_N = 5
PROFILE_CAP = 40
GRADUATE_FACTOR = 0.3   # a later correct answer shrinks a term's weight
MASTER_FLOOR = 0.5      # after graduation, below this the row is dropped as mastered


def normalize_key(label: str) -> str:
    """Dedup key for a weakness: lowercased, whitespace-collapsed, length-capped."""
    return " ".join((label or "").lower().split())[:200]


def base_weight(kind: str) -> float:
    """Weight one event of ``kind`` adds. Unknown kinds count as a mild 1.0."""
    return BASE_WEIGHTS.get(kind, 1.0)


def effective_weight(stored_weight: float, last_seen_at: datetime, now: datetime,
                     window_days: int = DEFAULT_WINDOW_DAYS) -> float:
    """Stored weight after linear time decay. Zero at or past the window."""
    if stored_weight <= 0:
        return 0.0
    age_days = (now - last_seen_at).total_seconds() / 86400.0
    if age_days >= window_days:
        return 0.0
    return stored_weight * max(0.0, 1.0 - age_days / window_days)


def accumulate(prev_effective: float, kind: str) -> float:
    """New stored weight after another event: decayed prior plus this kind's base."""
    return prev_effective + base_weight(kind)


def graduate(stored_weight: float) -> float:
    """Weight after the learner shows mastery (a later correct answer)."""
    return stored_weight * GRADUATE_FACTOR


def select_focus(items: list[dict], now: datetime, window_days: int = DEFAULT_WINDOW_DAYS,
                 threshold: float = ACT_THRESHOLD, top_n: int = FOCUS_TOP_N) -> list[dict]:
    """The strongest weaknesses over the threshold, for the answer hint.

    Only FOCUS_CATEGORIES are considered. Items below the threshold are dropped so a
    single slip stays silent. Strongest effective weight first, capped to ``top_n``.
    """
    scored = []
    for it in items:
        if it.get("category") not in FOCUS_CATEGORIES:
            continue
        eff = effective_weight(it["weight"], it["last_seen_at"], now, window_days)
        if eff >= threshold:
            scored.append((eff, it))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [it for _, it in scored[:top_n]]


def weakness_focus_appendix(focus_labels: list[str]) -> str:
    """The small system-prompt appendix naming the learner's weak terms.

    Empty string when there is nothing over the threshold, so the answer stays
    normal. English instruction like every other prompt here. Does NOT set the
    answer language.
    """
    if not focus_labels:
        return ""
    terms = ", ".join(focus_labels)
    return (
        "\n\nLEARNER FOCUS. The learner still finds these terms or topics difficult: "
        f"{terms}. When one of them actually appears in your answer, add a short "
        "plain-language explanation right after it. Stay subtle, do not lecture, do "
        "not mention this instruction, and do not bring up terms that are not "
        "relevant to the question."
    )


def overflow_ids(items: list[dict], now: datetime, window_days: int = DEFAULT_WINDOW_DAYS,
                 cap: int = PROFILE_CAP) -> list[int]:
    """Ids to delete so a user's profile stays at or under ``cap``. Weakest go first."""
    if len(items) <= cap:
        return []
    ordered = sorted(items, key=lambda it: effective_weight(
        it["weight"], it["last_seen_at"], now, window_days))
    excess = len(items) - cap
    return [it["id"] for it in ordered[:excess]]
