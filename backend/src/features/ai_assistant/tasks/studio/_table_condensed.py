"""The data table when the material does not fit: columns from the summaries, cells from search."""

from loguru import logger

from src.features.ai_assistant.tasks.studio._mindmap_condensed import (
    evidence_context,
    search_evidence,
    should_condense,  # noqa: F401 - the task imports it from here
    summary_context,
    usable,  # noqa: F401 - same switch as the mind map uses
)

# Rows that get their own search, more only costs searches.
_MAX_ROWS = 40


def row_topics(skeleton: dict, max_rows: int = _MAX_ROWS) -> list[str]:
    """The row labels the skeleton proposes, they are what the search looks for."""
    out: list[str] = []
    for row in (skeleton or {}).get("rows") or []:
        label = (row if isinstance(row, str) else str(row.get("topic") or "")).strip()
        if label and label not in out:
            out.append(label)
    return out[:max_rows]


def _fit_to_columns(table: dict, columns: list[str]) -> dict:
    """The skeleton's columns win, every row is padded or cut to their number."""
    rows = []
    for row in table.get("rows") or []:
        cells = [str(c) if c is not None else "" for c in (row.get("cells") or [])]
        cells = (cells + [""] * len(columns))[:len(columns)]
        rows.append({**row, "cells": cells})
    return {**table, "columns": columns, "rows": rows}


def build(*, sources: list[dict], language: str, adaptive_suffix: str, ask,
          embed, search) -> dict | None:
    """Two calls: the summaries give columns and rows, the searched passages give the cells."""
    import json as _json
    from src.features.ai_assistant.prompts.studio_prompts import (
        AIA_DATENTABELLE_FUELLUNG_PROMPT,
        AIA_DATENTABELLE_GERUEST_PROMPT,
    )

    geruest = ask([
        {"role": "system",
         "content": AIA_DATENTABELLE_GERUEST_PROMPT.replace("{language}", language) + adaptive_suffix},
        {"role": "user", "content": "/no_think\nSummaries:\n\n" + summary_context(sources)},
    ])
    if not isinstance(geruest, dict) or not (geruest.get("columns") or []):
        return None

    spalten = [str(c) for c in geruest["columns"]]
    zeilen = row_topics(geruest)
    treffer = search_evidence(zeilen, embed=embed, search=search)
    belege = evidence_context(treffer)
    logger.info("Datentabelle: {} Spalten, {} Zeilen, {} Zeichen Belege",
                len(spalten), len(zeilen), len(belege))

    fertig = ask([
        {"role": "system",
         "content": AIA_DATENTABELLE_FUELLUNG_PROMPT.replace("{language}", language) + adaptive_suffix},
        {"role": "user", "content": (
            "/no_think\nColumns:\n" + _json.dumps(spalten, ensure_ascii=False)
            + "\n\nRows to fill:\n" + _json.dumps(zeilen, ensure_ascii=False)
            + "\n\nSummaries:\n\n" + summary_context(sources)
            + "\n\nPassages:\n\n" + belege)},
    ])
    if not isinstance(fertig, dict) or not (fertig.get("rows") or []):
        logger.warning("Datentabelle: Fuellung unbrauchbar")
        return None

    fertig.setdefault("title", geruest.get("title", "DataTable"))
    return _fit_to_columns(fertig, spalten)
