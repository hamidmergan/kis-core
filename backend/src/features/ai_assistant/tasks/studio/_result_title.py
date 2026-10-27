"""Which rows a studio result shows the title call."""

from src.core.db.pool import get_connection

# Only tables with a display name, a name enters the query once it stands here.
_TITLE_TABLES = ("aia_mindmaps", "aia_data_tables")


def mindmap_entries(mindmap: dict) -> list[str]:
    """The first level nodes, without the root node."""
    kinder = (mindmap or {}).get("children") or []
    return [
        k["topic"].strip()
        for k in kinder
        if isinstance(k, dict) and str(k.get("topic") or "").strip()
    ]


def table_entries(table_data: dict) -> list[str]:
    """Column headers and the values of the first column."""
    daten = table_data or {}
    eintraege = [str(c).strip() for c in (daten.get("columns") or []) if str(c or "").strip()]
    for zeile in daten.get("rows") or []:
        zellen = (zeile or {}).get("cells") or []
        if zellen and str(zellen[0] or "").strip():
            eintraege.append(str(zellen[0]).strip())
    return eintraege


def recent_titles(table: str, workspace_id: int | None, limit: int = 100) -> list[str]:
    """The most recent titles of this tool in the course room, newest first."""
    if table not in _TITLE_TABLES or not workspace_id:
        return []
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""SELECT title FROM {table}
                        WHERE workspace_id = %s AND status = 'success'
                          AND title IS NOT NULL AND title <> ''
                        ORDER BY created_at DESC LIMIT %s""",
                    (workspace_id, limit),
                )
                return [r[0] for r in cur.fetchall() if r[0]]
    except Exception:  # noqa: BLE001
        return []


# The prompt block lists only the newest names, it sits in front of a large context.
_PROMPT_TITLES = 10


def title_rule(language: str, taken: list[str]) -> str:
    """Prompt block asking the answer itself for a title that is not taken yet."""
    from src.features.ai_assistant.prompts.studio_prompts import (
        AIA_STUDIO_TITLE_RULE, AIA_STUDIO_TITLES_TAKEN,
    )
    block = AIA_STUDIO_TITLE_RULE.replace("{language}", language)
    namen = [" ".join(t.split())[:90] for t in taken[:_PROMPT_TITLES] if (t or "").strip()]
    if namen:
        block += AIA_STUDIO_TITLES_TAKEN.format(titles="\n".join(f"  - {t}" for t in namen))
    return block


def free_title(title: str, fallback: str, taken: list[str]) -> str:
    """The answer's title, numbered when it repeats one in use, the fallback when empty."""
    from src.features.ai_assistant.tasks._titles import (
        MAX_TITLE_LEN, is_title_taken, next_free_counter,
    )
    title = " ".join(str(title or "").split())[:MAX_TITLE_LEN] or (fallback or "").strip()
    if not title or not is_title_taken(title, taken):
        return title
    return next_free_counter(title, taken)
