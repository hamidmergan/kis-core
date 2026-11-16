"""KI-Assistent Celery tasks - data_table generation."""

import json

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.ai_assistant.prompts.language_training_prompts import COMPACT_JSON_RULE
from src.features.ai_assistant.prompts.studio_prompts import (
    AIA_DATENTABELLE_PROMPT,
    AIA_DATENTABELLE_WEITERE_PAKETE,
)
from src.features.ai_assistant.tasks._context_budget import (
    fill_sources_evenly,
    overview_context_budget,
)
from src.features.ai_assistant.tasks._helpers import (
    _clean_llm_json,
    _get_llm_client,
)
from src.features.ai_assistant.tasks._instruction import (
    NONE,
    Resolution,
    prompt_block,
    spots_by_source,
)
from src.features.ai_assistant.tasks._instruction import resolve as resolve_instruction
from src.features.ai_assistant.tasks._json_commas import loads_entries
from src.features.ai_assistant.tasks.studio import _table_packets
from src.features.ai_assistant.tasks.studio._attribution import (
    _fmt_ts,
    _is_media_source,
    nav_page_value,
)
from src.limits import (
    AIA_TABLE_SOFT_TIME_LIMIT,
    AIA_TABLE_TIME_LIMIT,
)
from src.services.llm_call import create_logged


def _collect_sources(source_ids: list[int],
                     source_map: dict) -> list[tuple[int, str, list[dict]]]:
    """Per source: id, label and all of its chunks, the packets do the cutting."""
    vorhanden: list[tuple[int, str, list[dict]]] = []
    for sid in source_ids:
        chunks = db.get_chunks_by_source(sid)
        if not chunks:
            continue
        src_info = source_map.get(str(sid), {})
        vorhanden.append(
            (sid, src_info.get("filename", f"Source {src_info.get('number', '?')}"), chunks))
    return vorhanden


def _table_context(vorhanden: list[tuple[int, str, list[dict]]]
                   ) -> tuple[list[str], dict[int, str], dict[int, set]]:
    """The labelled passages, the file name per source and the pages the model saw."""
    context_parts: list[str] = []
    source_id_to_label: dict[int, str] = {}
    seen_pages_by_source: dict[int, set] = {}
    for sid, filename, picked in vorhanden:
        source_id_to_label[sid] = filename
        is_media = _is_media_source(filename)
        for chunk in picked:
            if is_media and chunk.get("start_time") is not None:
                part = f"[{filename}, {_fmt_ts(chunk['start_time'])}]\n{chunk['content']}"
            else:
                part = f"[{filename}, S. {chunk['page_number']}]\n{chunk['content']}"
            context_parts.append(part)
            seen_pages_by_source.setdefault(sid, set()).add(chunk["page_number"])
    return context_parts, source_id_to_label, seen_pages_by_source


def _ask_packet(client, model, system: str, language: str, data_table_id: int,
                context: str, columns) -> dict | None:
    """One packet: the first names the columns, every further one joins them."""
    anweisung = system
    if columns:
        anweisung += AIA_DATENTABELLE_WEITERE_PAKETE.format(
            columns=", ".join(str(c) for c in columns), count=len(columns))
    messages = [
        {"role": "system", "content": anweisung},
        {"role": "user", "content": (
            f"Create a structured data table from the following text "
            f"(write it in {language}):\n\n{context}"
        )},
    ]
    # A second attempt on broken JSON, a re-roll almost always works.
    for attempt in range(2):
        response = create_logged(client, endpoint="datentabelle", model=model,
                                 messages=messages, temperature=0.2)
        if getattr(response.choices[0], "finish_reason", None) == "length":
            logger.warning("data_table {}: Antwort abgeschnitten, Paket zu gross",
                           data_table_id)
            continue
        raw = response.choices[0].message.content
        if not raw:
            continue
        try:
            return loads_entries(_clean_llm_json(raw), "rows")
        except json.JSONDecodeError as e:
            logger.warning("data_table {} JSON parse failed (attempt {}/2): {}",
                           data_table_id, attempt + 1, e)
    return None


def _attach_sources(rows: list[dict], workspace_id, source_ids: list[int],
                    source_id_to_label: dict[int, str], seen_pages_by_source: dict[int, set]) -> None:
    """Attribution afterwards overwrites the guessed page with the checked one."""
    from src.features.ai_assistant.tasks.studio._attribution import attribute_studio_claims
    claims = [" ".join(str(c) for c in (r.get("cells") or []) if c).strip() for r in rows]
    chip_lists = attribute_studio_claims(
        claims, workspace_id=workspace_id, source_ids=source_ids,
        source_id_to_label=source_id_to_label, seen_pages_by_source=seen_pages_by_source,
    )
    for r, chips in zip(rows, chip_lists):
        r["sources"] = [
            {"source_label": c["source_label"], "page": nav_page_value(c)} for c in chips
        ]


@celery_app.task(bind=True, name="aia.generate_data_table", queue="aia",
                 soft_time_limit=AIA_TABLE_SOFT_TIME_LIMIT, time_limit=AIA_TABLE_TIME_LIMIT)
@observe(name="aia-data_table")
def run_generate_data_table(self, data_table_id: int, source_ids: list[int],
                              source_uuids: list[str], source_map: dict,
                              locale: str = "de", user_id: int | None = None,
                              _aia_job_uuid: str | None = None, anlauf: int = 0, seit: float | None = None):
    """Generates a data table from the sources as a background job."""
    # A requeued run takes the seat along and gives it back itself.
    platz_weiter = False
    from src.services.aia_adaptive_tools import build_adaptive_tool_suffix

    from src.features.ai_assistant.tasks._helpers import learning_tools_language
    # The generated content follows the management setting.
    _, language = learning_tools_language()

    try:
        db.update_aia_data_table(data_table_id, "running")
        logger.info("KI Tutor: generating data_table {}", data_table_id)

        # The instruction decides whether all the material or only the found spots go in.
        zeile = db.get_aia_data_table(data_table_id) or {}
        gewuenscht = zeile.get("user_instruction") or ""
        wahl = (resolve_instruction(zeile.get("workspace_id"), source_ids, gewuenscht,
                                    overview_context_budget())
                if gewuenscht.strip() else Resolution("", None, False, NONE))
        # Written anew on every run, so a retry that hits the material clears an old miss.
        if gewuenscht.strip():
            db.set_instruction_unmatched("aia_data_tables", data_table_id, wahl.unmatched)
        vorhanden = _collect_sources(source_ids, source_map)
        if wahl.chunks is not None:
            treffer = spots_by_source(wahl.chunks)
            vorhanden = [(sid, label, treffer[sid])
                         for sid, label, _chunks in vorhanden if sid in treffer]
        else:
            # Every source gets its share of one call, swept across the whole document.
            vorhanden = fill_sources_evenly(vorhanden, overview_context_budget())

        context_parts, source_id_to_label, seen_pages_by_source = _table_context(vorhanden)
        if not context_parts:
            db.update_aia_data_table(data_table_id, "failed", error="Keine Chunks vorhanden")
            return

        client, model, _ = _get_llm_client()
        # The level block hangs on the person, not on the course room. The instruction
        # travels with it into the one call.
        adaptive_suffix = (build_adaptive_tool_suffix(user_id)
                           + prompt_block(wahl.text, narrowed=wahl.chunks is not None))
        from src.features.ai_assistant.tasks.studio._result_title import (
            free_title, recent_titles, title_rule,
        )
        workspace_id = None
        if source_uuids:
            first = db.get_aia_source(source_uuids[0])
            workspace_id = first.get("workspace_id") if first else None
        vergeben = recent_titles("aia_data_tables", workspace_id)
        system = (AIA_DATENTABELLE_PROMPT.replace("{language}", language)
                  + title_rule(language, vergeben) + COMPACT_JSON_RULE + adaptive_suffix)

        def _ask(context: str, columns) -> dict | None:
            return _ask_packet(client, model, system, language, data_table_id, context, columns)

        # One packet, the material already fits the overview budget.
        pakete = _table_packets.packets(context_parts, overview_context_budget(), 1)
        logger.info("data_table {}: {} Zeichen in einem Aufruf", data_table_id,
                    sum(len(t) for p in pakete for t in p))
        table_data = _table_packets.run_packets(pakete, _ask)

        if table_data is None:
            db.update_aia_data_table(data_table_id, "failed", error="LLM returned unparseable JSON")
            return
        if not isinstance(table_data, dict) or "columns" not in table_data or "rows" not in table_data:
            db.update_aia_data_table(data_table_id, "failed", error="Invalid table format")
            return

        _attach_sources(table_data.get("rows") or [], workspace_id, source_ids,
                        source_id_to_label, seen_pages_by_source)

        sources_list = [
            {"number": info["number"], "filename": info["filename"]}
            for info in sorted(source_map.values(), key=lambda x: x["number"])
        ]
        # The name comes out of the same answer.
        title = free_title(table_data.get("title"), "DataTable", vergeben)

        db.update_aia_data_table(data_table_id, "success",
                                 title=title, table_data=table_data, sources=sources_list)
        logger.info("KI Tutor: data_table {} generated successfully", data_table_id)

    except Exception as e:
        from src.features.ai_assistant.tasks._warten import wieder_einreihen
        if wieder_einreihen(run_generate_data_table, e, anlauf=anlauf, seit=seit,
                            args=[data_table_id, source_ids, source_uuids, source_map],
                            kwargs={"locale": locale, "user_id": user_id, "_aia_job_uuid": _aia_job_uuid}):
            platz_weiter = True
            return
        logger.error("KI Tutor: data_table {} generation failed: {}", data_table_id, e)
        db.update_aia_data_table(data_table_id, "failed", error=str(e))
    finally:
        if _aia_job_uuid and not platz_weiter:
            try:
                from src.features.ai_assistant.scheduling.service import on_complete
                on_complete(_aia_job_uuid)
            except Exception as e:
                logger.error("KI Tutor: data_table dispatch on_complete failed: {}", e)

