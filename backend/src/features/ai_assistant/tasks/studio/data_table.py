"""KI-Assistent Celery tasks - data_table generation."""

from pathlib import Path

from langfuse.decorators import observe
from loguru import logger

from src.celery_app import celery_app
from src.limits import (
    AIA_TABLE_MAX_PACKETS,
    AIA_TABLE_SOFT_TIME_LIMIT,
    AIA_TABLE_TIME_LIMIT,
)
from src import database as db

from src.features.ai_assistant.tasks._helpers import (
    _get_llm_client,
    _clean_llm_json,
)
from src.features.ai_assistant.tasks._context_budget import tool_context_budget
from src.features.ai_assistant.tasks._instruction import (
    NONE,
    Resolution,
    prompt_block,
    spots_by_source,
)
from src.features.ai_assistant.tasks._instruction import resolve as resolve_instruction
from src.features.ai_assistant.tasks.studio import _table_condensed as _condensed
from src.features.ai_assistant.tasks.studio import _table_packets
from src.services import aia_chunker
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


def _is_media_source(filename: str) -> bool:
    """True when the source's suffix carries a transcript with timestamps."""
    return aia_chunker.is_media_file(Path(filename).suffix)


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
    import json as _json
    from src.features.ai_assistant.prompts.studio_prompts import (
        AIA_DATENTABELLE_PROMPT,
        AIA_DATENTABELLE_WEITERE_PAKETE,
    )
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
                                    tool_context_budget())
                if gewuenscht.strip() else Resolution("", None, False, NONE))
        # Written anew on every run, so a retry that hits the material clears an old miss.
        if gewuenscht.strip():
            db.set_instruction_unmatched("aia_data_tables", data_table_id, wahl.unmatched)
        vorhanden = _collect_sources(source_ids, source_map)
        if wahl.chunks is not None:
            treffer = spots_by_source(wahl.chunks)
            vorhanden = [(sid, label, treffer[sid])
                         for sid, label, _chunks in vorhanden if sid in treffer]

        context_parts: list[str] = []
        # Which pages the model saw, the chips are limited to them.
        source_id_to_label: dict[int, str] = {}
        seen_pages_by_source: dict[int, set] = {}
        for sid, filename, picked in vorhanden:
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

        client, model, _ = _get_llm_client()
        def _ask_json(messages) -> dict | None:
            """One request that must answer JSON, with a second try on a broken answer."""
            for attempt in range(2):
                response = create_logged(client, endpoint="datentabelle", model=model,
                                         messages=messages, temperature=0.2)
                raw = response.choices[0].message.content
                if not raw:
                    continue
                try:
                    return _json.loads(_clean_llm_json(raw))
                except _json.JSONDecodeError as e:
                    logger.warning("data_table {} JSON parse failed (attempt {}/2): {}",
                                   data_table_id, attempt + 1, e)
            return None

        # The level block hangs on the person, not on the course room. The instruction
        # travels with it so every packet and both condensed calls carry it.
        adaptive_suffix = (build_adaptive_tool_suffix(user_id)
                           + prompt_block(wahl.text, narrowed=wahl.chunks is not None))
        system = AIA_DATENTABELLE_PROMPT.replace("{language}", language) + adaptive_suffix

        def _ask(context: str, columns) -> dict | None:
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
                    return _json.loads(_clean_llm_json(raw))
                except _json.JSONDecodeError as e:
                    logger.warning("data_table {} JSON parse failed (attempt {}/2): {}",
                                   data_table_id, attempt + 1, e)
            return None

        # Whoever fits is read in full, only the rest goes through the summaries.
        gesamt = sum(len(p) for p in context_parts)
        quellen = [{"id": sid, "label": source_id_to_label[sid],
                    "summary": (db.get_aia_source(u) or {}).get("summary")}
                   for sid, u in zip(source_ids, source_uuids)
                   if sid in source_id_to_label]
        # Found spots always fit, they take one packet.
        verdichtet = wahl.chunks is None and _condensed.should_condense(
            gesamt, tool_context_budget(), quellen)
        logger.info("data_table {}: {} Zeichen Material, Weg {}", data_table_id, gesamt,
                    "verdichtet" if verdichtet else "Pakete")

        if verdichtet:
            from src.services.aia_embeddings import get_embedding_provider_with_fallback
            _emb = get_embedding_provider_with_fallback()
            _ws = (db.get_aia_source(source_uuids[0]) or {}).get("workspace_id")

            def _suche(frage: str, vektor, limit: int) -> list[dict]:
                """The passages for one row, each tagged with the file it stands in."""
                treffer = db.hybrid_search_chunks(
                    _ws, frage, vektor, source_ids=source_ids, limit=limit) or []
                for c in treffer:
                    c["source_label"] = source_id_to_label.get(c.get("source_id"), "")
                return treffer

            table_data = _condensed.build(
                sources=quellen, language=language, adaptive_suffix=adaptive_suffix,
                ask=lambda n: _ask_json(n), embed=_emb.embed_one, search=_suche,
            )
        else:
            pakete = _table_packets.packets(context_parts, tool_context_budget(),
                                            AIA_TABLE_MAX_PACKETS)
            logger.info("data_table {}: {} Teile in {} Paketen", data_table_id,
                        len(context_parts), len(pakete))
            table_data = _table_packets.run_packets(pakete, _ask)

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

