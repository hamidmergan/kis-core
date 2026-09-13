"""KI-Assistent Celery tasks - data_table generation."""

from pathlib import Path

from langfuse.decorators import observe
from loguru import logger

from src.celery_app import celery_app
from src.limits import AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT
from src import database as db

from src.features.ai_assistant.tasks._helpers import (
    _get_llm_client,
    _clean_llm_json,
)
from src.services import aia_chunker
from src.services.llm_call import create_logged


def _collect_sources(source_ids: list[int], source_uuids: list[str],
                     source_map: dict) -> list[tuple[int, str, list[dict]]]:
    """Per source: id, label and the window that fits the budget."""
    from src.features.ai_assistant.tasks._context_budget import fill_sources_greedy

    vorhanden: list[tuple[int, str, list[dict]]] = []
    workspace_id = (db.get_aia_source(source_uuids[0]) or {}).get("workspace_id") \
        if source_uuids else None
    for sid in source_ids:
        chunks = db.get_chunks_by_source(sid)
        if not chunks:
            continue
        src_info = source_map.get(str(sid), {})
        vorhanden.append(
            (sid, src_info.get("filename", f"Source {src_info.get('number', '?')}"), chunks))
    return fill_sources_greedy(vorhanden, workspace_id, "datatable")


def _is_media_source(filename: str) -> bool:
    """True when the source's suffix carries a transcript with timestamps."""
    return aia_chunker.is_media_file(Path(filename).suffix)


@celery_app.task(bind=True, name="aia.generate_data_table", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-data_table")
def run_generate_data_table(self, data_table_id: int, source_ids: list[int],
                              source_uuids: list[str], source_map: dict,
                              locale: str = "de", user_id: int | None = None):
    """Generates a data table from the sources as a background job."""
    import json as _json
    from src.features.ai_assistant.prompts.studio_prompts import AIA_DATENTABELLE_PROMPT
    from src.services.aia_adaptive_tools import build_adaptive_tool_suffix

    from src.features.ai_assistant.tasks._helpers import learning_tools_language
    # The generated content follows the management setting.
    _, language = learning_tools_language()

    try:
        db.update_aia_data_table(data_table_id, "running")
        logger.info("KI Tutor: generating data_table {}", data_table_id)

        context_parts: list[str] = []
        # Which pages the model saw, the chips are limited to them.
        source_id_to_label: dict[int, str] = {}
        seen_pages_by_source: dict[int, set] = {}
        for sid, filename, picked in _collect_sources(source_ids, source_uuids, source_map):
            source_id_to_label[sid] = filename
            is_media = _is_media_source(filename)
            for chunk in picked:
                if is_media and chunk.get("start_time") is not None:
                    st = chunk["start_time"]
                    h, m, s = int(st // 3600), int((st % 3600) // 60), int(st % 60)
                    ts = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"
                    part = f"[{filename}, {ts}]\n{chunk['content']}"
                else:
                    part = f"[{filename}, S. {chunk['page_number']}]\n{chunk['content']}"
                context_parts.append(part)
                seen_pages_by_source.setdefault(sid, set()).add(chunk["page_number"])

        if not context_parts:
            db.update_aia_data_table(data_table_id, "failed", error="Keine Chunks vorhanden")
            return

        context = "\n\n---\n\n".join(context_parts)

        client, model, _ = _get_llm_client()
        # The level block hangs on the person, not on the course room.
        adaptive_suffix = build_adaptive_tool_suffix(user_id)
        messages = [
            {"role": "system", "content": AIA_DATENTABELLE_PROMPT.replace("{language}", language) + adaptive_suffix},
            {"role": "user", "content": (
                f"Create a structured data table from the following text (write it in {language}):\n\n{context}"
            )},
        ]

        # A second attempt on broken JSON, a re-roll almost always works.
        table_data = None
        for attempt in range(2):
            response = create_logged(client, endpoint="datentabelle", model=model, messages=messages, temperature=0.2)
            raw = response.choices[0].message.content
            if not raw:
                continue
            try:
                table_data = _json.loads(_clean_llm_json(raw))
                break
            except _json.JSONDecodeError as e:
                logger.warning("data_table {} JSON parse failed (attempt {}/2): {}", data_table_id, attempt + 1, e)

        if table_data is None:
            db.update_aia_data_table(data_table_id, "failed", error="LLM returned unparseable JSON")
            return
        if not isinstance(table_data, dict) or "columns" not in table_data or "rows" not in table_data:
            db.update_aia_data_table(data_table_id, "failed", error="Invalid table format")
            return

        # Attribution afterwards overwrites the guessed page with the checked one.
        from src.features.ai_assistant.tasks.studio._attribution import (
            attribute_studio_claims, nav_page_value,
        )
        rows = table_data.get("rows") or []
        workspace_id = None
        if source_uuids:
            first = db.get_aia_source(source_uuids[0])
            workspace_id = first.get("workspace_id") if first else None
        claims = [" ".join(str(c) for c in (r.get("cells") or []) if c).strip() for r in rows]
        chip_lists = attribute_studio_claims(
            claims, workspace_id=workspace_id, source_ids=source_ids,
            source_id_to_label=source_id_to_label, seen_pages_by_source=seen_pages_by_source,
        )
        for r, chips in zip(rows, chip_lists):
            r["sources"] = [
                {"source_label": c["source_label"], "page": nav_page_value(c)} for c in chips
            ]

        sources_list = [
            {"number": info["number"], "filename": info["filename"]}
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        ]
        # The title comes from the column headers and the first column.
        from src.features.ai_assistant.tasks._titles import resolve_title
        from src.features.ai_assistant.tasks.studio._result_title import (
            recent_titles, table_entries,
        )

        title = table_data.get("title", "DataTable")
        try:
            title = resolve_title(
                client, model,
                recent_titles("aia_data_tables", workspace_id),
                title,
                table_entries(table_data),
            ) or title
        except Exception as e:  # noqa: BLE001
            logger.warning("KI Tutor: data_table {} behaelt ihren vorlaeufigen Namen: {}", data_table_id, e)

        db.update_aia_data_table(data_table_id, "success",
                                        title=title, table_data=table_data, sources=sources_list)
        logger.info("KI Tutor: data_table {} generated successfully", data_table_id)

    except Exception as e:
        logger.error("KI Tutor: data_table {} generation failed: {}", data_table_id, e)
        db.update_aia_data_table(data_table_id, "failed", error=str(e))

