"""KI-Assistent Celery tasks - data_table generation."""

from langfuse.decorators import observe
from loguru import logger

from src.celery_app import celery_app
from src.limits import AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT
from src import database as db

from src.features.ai_assistant.tasks._helpers import (
    _get_llm_client,
    _clean_llm_json,
)

@celery_app.task(bind=True, name="aia.generate_data_table", queue="aia",
                 soft_time_limit=AIA_TOOL_SOFT_TIME_LIMIT, time_limit=AIA_TOOL_TIME_LIMIT)
@observe(name="aia-data_table")
def run_generate_data_table(self, data_table_id: int, source_ids: list[int],
                              source_uuids: list[str], source_map: dict,
                              locale: str = "de", user_id: int | None = None):
    """Generate a data table from source chunks as a background job.

    `locale` controls the output language (title/headers/values); 'highlight'
    stays verbatim in the source language. Defaults to 'de' for older queued tasks.
    `user_id` drives the adaptive language level (cell wording pitched at the
    learner's CEFR level); None for older queued tasks keeps the shipped register.
    """
    import json as _json
    from src.tool_prompts import AIA_DATENTABELLE_PROMPT
    from src.services.aia_adaptive_tools import build_adaptive_tool_suffix

    from src.features.ai_assistant.tasks._helpers import tool_output_language
    # Wie bei den Uebungs-Werkzeugen: der erzeugte Inhalt folgt der
    # Unterrichtssprache des Kursraums, nicht der Sprachwahl der Person.
    _erste = db.get_aia_source(source_uuids[0]) if source_uuids else None
    _, language = tool_output_language((_erste or {}).get("workspace_id"))

    try:
        db.update_aia_data_table(data_table_id, "running")
        logger.info("KI Tutor: generating data_table {}", data_table_id)

        # Build context with source filenames for citations. Per-source budget from the admin
        # aia_tool_context_max_chars setting (shared by all generation tools, separate from the
        # chat budget); each source goes in whole when it fits, otherwise it is read as a sweep
        # that resumes where the last run for this source stopped, so a re-run covers other
        # rows instead of the same window again.
        from src.features.ai_assistant.tasks._context_budget import (
            tool_context_budget,
            select_chunks_for_budget,
            read_cursors,
            write_cursors,
        )
        _MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".aac"}
        budget_per_source = max(1000, tool_context_budget() // max(1, len(source_ids)))
        sweep_workspace_id = (db.get_aia_source(source_uuids[0]) or {}).get("workspace_id") \
            if source_uuids else None
        context_parts: list[str] = []
        # For post-hoc pgvector attribution (same gate as chat): which source/pages the model
        # actually saw, and the id->label map. Chips are clamped to these seen pages.
        source_id_to_label: dict[int, str] = {}
        seen_pages_by_source: dict[int, set] = {}
        for sid, suuid in zip(source_ids, source_uuids):
            chunks = db.get_chunks_by_source(sid)
            src_info = source_map.get(str(sid), {})
            filename = src_info.get("filename", f"Source {src_info.get('number', '?')}")
            source_id_to_label[sid] = filename
            is_media = any(filename.lower().endswith(ext) for ext in _MEDIA_EXTS)
            picked, resume = select_chunks_for_budget(
                chunks, budget_per_source,
                cursors=read_cursors(sweep_workspace_id, sid, "datatable"))
            write_cursors(sweep_workspace_id, sid, "datatable", resume)
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
        # Workspace comes from the sources: the adaptive suffix is gated on the
        # Fachsprachentrainer being on there, exactly like the chat.
        _first_source = db.get_aia_source(source_uuids[0]) if source_uuids else None
        adaptive_suffix = build_adaptive_tool_suffix(
            user_id, (_first_source or {}).get("workspace_id"),
        )
        messages = [
            {"role": "system", "content": AIA_DATENTABELLE_PROMPT.replace("{language}", language) + adaptive_suffix},
            {"role": "user", "content": (
                f"Create a structured data table from the following text (write it in {language}):\n\n{context}"
            )},
        ]

        # The LLM occasionally emits malformed JSON (e.g. a missing delimiter).
        # Retry once with a fresh sample before giving up - a re-roll almost
        # always parses, so a single flaky generation no longer fails the table.
        table_data = None
        for attempt in range(2):
            response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
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

        # Post-hoc attribution (same pgvector gate as chat), nav-only: re-ground each row's
        # content and OVERWRITE the LLM's guessed page/highlight with the verified page (or a
        # media timestamp). A row that grounds nowhere gets no chip rather than a fabricated one.
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
        # Der Titel aus dem Erzeugungs-Aufruf beschreibt das Dokument, weil dieser Aufruf
        # das ganze Dokument sieht. Hier zaehlt, was in der Tabelle steht: die Spaltenkoepfe
        # und die erste Spalte. Der alte Titel bleibt der Rueckfall.
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

