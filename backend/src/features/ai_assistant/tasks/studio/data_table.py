"""KI-Assistent Celery tasks - data_table generation."""

import concurrent.futures
import os
import re

from langfuse.decorators import langfuse_context, observe
from loguru import logger

from src.celery_app import celery_app
from src import database as db
from src.storage import open_input_file
from src.limits import (
    AIA_SUMMARY_MAX_RETRIES,
    AIA_SUMMARY_TIMEOUT_SMALL,
    AIA_SUMMARY_TIMEOUT_LARGE,
    AIA_SUMMARY_MAX_TOKENS_SMALL,
    AIA_SUMMARY_MAX_TOKENS_LARGE,
    AIA_SUMMARY_MAX_TOKENS_BATCH,
    AIA_SUMMARY_CONTENT_MAX_CHARS,
    AIA_SUMMARY_PARALLEL_WORKERS_SMALL,
    AIA_SUMMARY_PARALLEL_WORKERS_LARGE,
    AIA_SUMMARY_BATCH_SIZE,
)
from src.tool_prompts import (
    AIA_SUMMARY_PAGE_SYSTEM as _SUMMARY_SYSTEM,
    AIA_SUMMARY_PAGE_USER_SMALL as _SUMMARY_USER_SMALL,
    AIA_SUMMARY_PAGE_USER_LARGE as _SUMMARY_USER_LARGE,
    AIA_SUMMARY_PAGE_BATCH_USER as _SUMMARY_BATCH_USER,
    AIA_MINDMAP_PROMPT,
)

from src.features.ai_assistant.tasks._helpers import (
    _format_ts,
    _save_aia_output,
    _detect_language,
    _parse_numbered_summaries,
    _clean_summary,
    _call_llm_with_retry,
    _summarize_page,
    _summarize_batch,
    _get_llm_client,
    _clean_llm_json,
)

@celery_app.task(bind=True, name="aia.generate_data_table", queue="aia",
                 soft_time_limit=120, time_limit=180)
@observe(name="aia-data_table")
def run_generate_data_table(self, data_table_id: int, source_ids: list[int],
                              source_uuids: list[str], source_map: dict):
    """Generate a data table from source chunks as a background job."""
    import json as _json
    from src.tool_prompts import AIA_DATENTABELLE_PROMPT

    try:
        db.update_aia_data_table(data_table_id, "running")
        logger.info("KI Tutor: generating data_table {}", data_table_id)

        # Build context with source filenames for citations
        _MEDIA_EXTS = {".mp3", ".mp4", ".m4a", ".wav", ".ogg", ".webm", ".flac", ".aac"}
        context_parts: list[str] = []
        context_len = 0
        for sid, suuid in zip(source_ids, source_uuids):
            chunks = db.get_chunks_by_source(sid)
            src_info = source_map.get(str(sid), {})
            filename = src_info.get("filename", f"Source {src_info.get('number', '?')}")
            is_media = any(filename.lower().endswith(ext) for ext in _MEDIA_EXTS)
            for chunk in chunks:
                if is_media and chunk.get("start_time") is not None:
                    st = chunk["start_time"]
                    h, m, s = int(st // 3600), int((st % 3600) // 60), int(st % 60)
                    ts = f"{h}:{m:02}:{s:02}" if h > 0 else f"{m}:{s:02}"
                    part = f"[{filename}, {ts}]\n{chunk['content']}"
                else:
                    part = f"[{filename}, S. {chunk['page_number']}]\n{chunk['content']}"
                if context_len + len(part) > 200000:
                    break
                context_parts.append(part)
                context_len += len(part)

        if not context_parts:
            db.update_aia_data_table(data_table_id, "failed", error="Keine Chunks vorhanden")
            return

        context = "\n\n---\n\n".join(context_parts)

        client, model, _ = _get_llm_client()
        messages = [
            {"role": "system", "content": AIA_DATENTABELLE_PROMPT},
            {"role": "user", "content": (
                f"Create a structured data table from the following text (respond in the source-text language):\n\n{context}"
            )},
        ]

        response = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
        raw = response.choices[0].message.content
        if not raw:
            db.update_aia_data_table(data_table_id, "failed", error="LLM returned empty content")
            return

        table_data = _json.loads(_clean_llm_json(raw))
        if not isinstance(table_data, dict) or "columns" not in table_data or "rows" not in table_data:
            db.update_aia_data_table(data_table_id, "failed", error="Invalid table format")
            return

        sources_list = [
            {"number": info["number"], "filename": info["filename"]}
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        ]
        title = table_data.get("title", "DataTable")

        db.update_aia_data_table(data_table_id, "success",
                                        title=title, table_data=table_data, sources=sources_list)
        logger.info("KI Tutor: data_table {} generated successfully", data_table_id)

    except Exception as e:
        logger.error("KI Tutor: data_table {} generation failed: {}", data_table_id, e)
        db.update_aia_data_table(data_table_id, "failed", error=str(e))

