"""Find appointments: patterns pick the blocks, one model call per packet, harmonise, merge."""

import contextvars
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date as _date_cls

from celery.exceptions import SoftTimeLimitExceeded
from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.limits import AIA_SCHEDULE_SOFT_TIME_LIMIT, AIA_SCHEDULE_TIME_LIMIT
from src.features.ai_assistant.tasks._helpers import _get_llm_client

from src.features.ai_assistant.tasks._context_budget import tool_context_budget
from src.features.ai_assistant.tasks.studio.schedule._candidates import (
    _fundstelle_zeit,
    _load_source_chunks,
    _transcript_index,
)
from src.features.ai_assistant.tasks.studio.schedule._extract import (
    extract_packet,
    hit_blocks,
    items_to_pairs,
    packets,
)
from src.features.ai_assistant.tasks.studio.schedule._harmonize import (
    _harmonize_same_date_titles,
)
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _parse_date,
    _parse_time,
    _range_end_date,
    _resolve_current_year,
)
from src.features.ai_assistant.tasks.studio.schedule._titles import _find_merge_target


def _split_rejected_ranges(candidates: list[dict],
                           classifications: list[dict]) -> tuple[list[dict], list[dict]]:
    """Whatever the model does not confirm as a span becomes two appointments again."""
    cands: list[dict] = []
    cls_out: list[dict] = []
    for cand, cls in zip(candidates, classifications):
        cands.append(cand)
        cls_out.append(cls)
        if cls.get("is_range") or not cand.get("date_end_raw") or not cls.get("keep"):
            continue
        zweiter = dict(cand)
        zweiter["date_raw"] = cand["date_end_raw"]
        zweiter["date_iso"] = cand.get("date_end_iso")
        zweiter["partial_date"] = cand.get("date_end_partial")
        zweiter["date_end_raw"] = zweiter["date_end_iso"] = zweiter["date_end_partial"] = None
        cands.append(zweiter)
        cls_out.append(dict(cls))
    return cands, cls_out


# Measured: the provider runs two big requests side by side, a third slows all of them.
_PARALLEL_PACKETS = 2


@celery_app.task(bind=True, name="aia.generate_schedule", queue="aia",
                 soft_time_limit=AIA_SCHEDULE_SOFT_TIME_LIMIT, time_limit=AIA_SCHEDULE_TIME_LIMIT)
@observe(name="aia-schedule")
def run_generate_schedule(self, job_id: int, workspace_id: int, user_id: int,
                          source_uuids: list[str]):
    """Patterns pick the blocks, the model returns the appointments, the rest is merging."""
    try:
        db.update_schedule_job(job_id, "running")
        logger.info("Schedule job {} started", job_id)

        sources: list[dict] = []
        for suuid in source_uuids:
            src = db.get_aia_source(suuid)
            if src and src["workspace_id"] == workspace_id:
                sources.append(src)

        already_processed = set(db.get_processed_source_ids(workspace_id, user_id))
        pending = [s for s in sources if s["id"] not in already_processed]

        if not pending:
            db.update_schedule_job(job_id, "success", added_count=0)
            logger.info("Schedule job {}: no pending sources", job_id)
            return

        # Per open source, use the stored analysis or analyse again.
        today_d = _date_cls.today()
        per_source: dict[int, tuple[list[dict], list[dict]]] = {}

        # Without a model only the stored analyses can be used.
        try:
            client, model, _ = _get_llm_client()
        except Exception as e:  # noqa: BLE001 - der Zwischenspeicher-Weg braucht kein Modell
            logger.warning("Schedule job {}: kein LLM-Client ({})", job_id, e)
            client, model = None, None

        # Open appointments have no pattern, one search covers the whole module.
        open_spots: dict = {}
        try:
            from src.features.ai_assistant.tasks.studio.schedule._open_search import (
                open_spots_for_workspace,
            )
            from src.services.aia_embeddings import get_embedding_provider_with_fallback
            provider = get_embedding_provider_with_fallback()
            open_spots = open_spots_for_workspace(
                workspace_id, [s["id"] for s in pending],
                embed=provider.embed_one,
                search=lambda wid, q, vec, sids, limit: db.hybrid_search_chunks(
                    wid, q, vec, source_ids=sids, limit=limit),
            )
            logger.info("Schedule job {}: Suche fand {} offene Stellen", job_id, len(open_spots))
        except Exception as e:  # noqa: BLE001 - der Zeitplan entsteht auch ohne diese Suche
            logger.warning("Schedule job {}: Suche nach offenen Terminen fehlgeschlagen: {}",
                           job_id, e)

        # Per source: the stored analysis, or its hit blocks for the model.
        blocks: list[dict] = []
        zeitachsen: dict[int, object] = {}
        last_block_of: dict[int, int] = {}
        for src in pending:
            stored = db.get_source_extraction(src["id"])
            if stored is not None:
                per_source[src["id"]] = (stored["candidates"], stored["classifications"])
                logger.info(
                    "Schedule job {}: source '{}' -> cache hit ({} candidates)",
                    job_id, src.get("filename", src["id"]),
                    len(stored["candidates"]),
                )
                continue
            chunks = _load_source_chunks(src["id"])
            eigene = hit_blocks(src, chunks, open_spots)
            zeitachsen[src["id"]] = _transcript_index(src, chunks)
            logger.info("Schedule job {}: source '{}' -> {} of {} blocks carry a date",
                        job_id, src.get("filename", src["id"]), len(eigene), len(chunks))
            if not eigene:
                per_source[src["id"]] = ([], [])
                db.upsert_source_extraction(src["id"], [], [])
                continue
            last_block_of[src["id"]] = len(blocks) + len(eigene) - 1
            blocks.extend(eigene)

        # The entries already there, also as anchors for consistent naming.
        existing_entries: list[dict] = list(db.get_schedule_entries(workspace_id, user_id))
        workspace_entries: list[dict] = list(db.get_schedule_entries_for_workspace(workspace_id))

        def zeit_bei(block: dict, offset: int):
            return _fundstelle_zeit(zeitachsen.get(block["source_id"]), block["chunk"], offset)

        # Two packets at a time, a source is saved as soon as all its packets are through.
        pakete = packets(blocks, tool_context_budget())
        quellen_je_paket = [{b["source_id"] for b in p} for p in pakete]
        pakete_je_quelle: dict[int, set[int]] = {}
        for pi, sids in enumerate(quellen_je_paket):
            for sid in sids:
                pakete_je_quelle.setdefault(sid, set()).add(pi)
        ergebnis: dict[int, dict[int, tuple[list[dict], list[dict]]]] = {}
        fehler: Exception | None = None
        pool = ThreadPoolExecutor(max_workers=_PARALLEL_PACKETS)
        try:
            # Each packet keeps the trace context of the task in its thread.
            futures = {
                pool.submit(contextvars.copy_context().run, extract_packet,
                            client, model, p, today_d): pi
                for pi, p in enumerate(pakete)
            }
            for fut in as_completed(futures):
                pi = futures[fut]
                try:
                    neu = fut.result()
                except SoftTimeLimitExceeded:
                    raise
                except Exception as e:  # noqa: BLE001 - the other packets go on
                    fehler = e
                    logger.error("Schedule job {}: Terminsuche fehlgeschlagen: {}", job_id, e)
                    continue
                logger.info("Schedule job {}: packet of {} blocks -> {} appointments",
                            job_id, len(pakete[pi]), len(neu))
                ergebnis[pi] = items_to_pairs(neu, pakete[pi], today_d, time_at=zeit_bei)
                for sid in quellen_je_paket[pi]:
                    if sid in per_source or not pakete_je_quelle[sid].issubset(ergebnis):
                        continue
                    cands: list[dict] = []
                    cls: list[dict] = []
                    for pj in sorted(pakete_je_quelle[sid]):
                        c, v = ergebnis[pj].get(sid, ([], []))
                        cands.extend(c)
                        cls.extend(v)
                    per_source[sid] = (cands, cls)
                    db.upsert_source_extraction(sid, cands, cls)
        except SoftTimeLimitExceeded:
            logger.warning("Schedule job {}: Zeit abgelaufen, {} Quellen sind gesichert",
                           job_id, len(per_source))
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        if fehler is not None and not per_source:
            db.update_schedule_job(job_id, "failed", error=f"Terminsuche fehlgeschlagen: {fehler}")
            return

        # Assemble final flat lists in pending order.
        fertig = [src for src in pending if src["id"] in per_source]
        all_candidates: list[dict] = []
        classifications: list[dict] = []
        for src in fertig:
            cands, cls = per_source[src["id"]]
            all_candidates.extend(cands)
            classifications.extend(cls)

        # Rejected pairings back into two appointments before the lists are joined.
        all_candidates, classifications = _split_rejected_ranges(all_candidates, classifications)

        if not all_candidates:
            for src in fertig:
                db.mark_source_processed(workspace_id, user_id, src["id"])
            db.update_schedule_job(job_id, "success", added_count=0)
            logger.info("Schedule job {}: no candidates found", job_id)
            return

        # Other people's entries serve as anchors for consistent naming.
        own_ids = {e["id"] for e in existing_entries}
        cross_user_anchors = [e for e in workspace_entries if e["id"] not in own_ids]
        harmonize_anchors = existing_entries + cross_user_anchors

        # Harmonise titles of the same day so no duplicates appear later.
        try:
            _harmonize_same_date_titles(
                client, model, all_candidates, classifications, today_d, harmonize_anchors,
            )
        except Exception as e:
            logger.warning("Schedule job {}: harmonize pass failed (non-fatal): {}", job_id, e)

        # STAGE 3: Merge into entries (dedup with existing via fuzzy-title + date)
        added = 0

        for cand, cls in zip(all_candidates, classifications):
            if not cls["keep"] or cls["is_footer"] or cls.get("is_header") or cls.get("is_historical"):
                logger.info(
                    "Schedule job {}: drop candidate date={} (footer={}, header={}, historical={}, keep={})",
                    job_id, cand.get("date_iso") or cand.get("partial_date"),
                    cls["is_footer"], cls.get("is_header"), cls.get("is_historical"), cls["keep"],
                )
                continue

            # Resolve the date: complete, month and day only, or none at all.
            if cand.get("is_tbd"):
                due_date_obj = None
            elif cand["date_iso"]:
                due_date_obj = _parse_date(cand["date_iso"])
            elif cand.get("partial_date"):
                mo, da = cand["partial_date"]
                due_date_obj = _resolve_current_year(today_d, mo, da)
            else:
                due_date_obj = None
            # Only non-TBD candidates require a resolved date
            if due_date_obj is None and not cand.get("is_tbd"):
                continue
            # 'month' means the source named only a month.
            precision = "month" if cand.get("date_precision") == "month" else "day"
            end_date_obj = (
                _range_end_date(cand, due_date_obj, today_d) if cls.get("is_range") else None
            )
            # An end and 'runs on indefinitely' are mutually exclusive.
            offenes_ende = bool(cls.get("is_open_ended")) and end_date_obj is None

            ref = {
                "source_uuid": cand["source_uuid"],
                "page_number": cand["page_number"],
                "start_time": cand["start_time"],
                # The short excerpt serves the browser search, the long one only the classification.
                "raw_quote": cand.get("raw_quote") or cand.get("context"),
            }

            # Try to merge into an existing entry.
            merge_target = _find_merge_target(
                existing_entries, due_date_obj, precision, cls["title"], ref,
                end_date=end_date_obj,
            )
            if merge_target:
                db.append_source_ref_to_entry(merge_target["id"], ref)
                # Update local view too, so subsequent candidates see the merge
                merge_target.setdefault("source_refs", []).append(ref)
                logger.info("Schedule job {}: merged '{}' into entry #{}",
                            job_id, cls["title"], merge_target["id"])
                continue

            type_ = cls["type"] if cls["type"] in ("deadline", "termin") else "termin"
            new_row = db.create_schedule_entry(
                workspace_id,
                user_id,
                type=type_,
                title=(cls["title"] or cand["date_iso"])[:200],
                description=cls["description"],
                due_date=due_date_obj,
                end_date=end_date_obj,
                due_time=_parse_time(cls["due_time"]),
                end_time=_parse_time(cls.get("end_time")),
                date_precision=precision,
                is_open_ended=offenes_ende,
                is_optional=cls["is_optional"],
                origin="llm",
                source_refs=[ref],
            )
            existing_entries.append(new_row)
            added += 1

        # STAGE 4: mark sources processed
        for src in fertig:
            db.mark_source_processed(workspace_id, user_id, src["id"])

        db.update_schedule_job(job_id, "success", added_count=added)
        logger.info("Schedule job {}: added {} new entries", job_id, added)

    except Exception as e:
        logger.error("Schedule job {} failed: {}", job_id, e)
        db.update_schedule_job(job_id, "failed", error=str(e))


__all__ = ["run_generate_schedule"]
