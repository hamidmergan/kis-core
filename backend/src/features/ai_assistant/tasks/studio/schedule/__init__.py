"""AI assistant Celery tasks: schedule extraction (regex + batch-classify pipeline).

Pipeline:
  1) Regex finds 100% of date candidates per source (_candidates)
  2) A single batch LLM call classifies them all (keep/footer/historical/type/title) (_classify)
  3) Same-date harmonization aligns titles with existing entries (_harmonize)
  4) Merge by fuzzy-title + date (_titles) into existing entries or create new ones
"""

from datetime import date as _date_cls

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.ai_assistant.tasks._helpers import _get_llm_client

from src.features.ai_assistant.tasks.studio.schedule._candidates import (
    _build_candidates_for_source,
)
from src.features.ai_assistant.tasks.studio.schedule._classify import _classify_candidates
from src.features.ai_assistant.tasks.studio.schedule._harmonize import (
    _harmonize_same_date_titles,
)
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _parse_date,
    _parse_time,
    _resolve_current_year,
)
from src.features.ai_assistant.tasks.studio.schedule._titles import _fuzzy_same


@celery_app.task(bind=True, name="aia.generate_schedule", queue="aia",
                 soft_time_limit=600, time_limit=720)
@observe(name="aia-schedule")
def run_generate_schedule(self, job_id: int, workspace_id: int, user_id: int,
                          source_uuids: list[str]):
    """Regex-first pipeline:
      1) find all date candidates per source via regex (100% recall)
      2) classify all candidates in ONE LLM call (is_event? footer? type? title?)
      3) merge into existing entries (fuzzy-title + same date, append source_ref)
    """
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

        # STAGE 1: Regex-based candidate collection (across all pending sources)
        all_candidates: list[dict] = []
        for src in pending:
            cands = _build_candidates_for_source(src)
            logger.info("Schedule job {}: source '{}' -> {} date candidates",
                        job_id, src.get("filename", src["id"]), len(cands))
            all_candidates.extend(cands)

        if not all_candidates:
            for src in pending:
                db.mark_source_processed(workspace_id, user_id, src["id"])
            db.update_schedule_job(job_id, "success", added_count=0)
            logger.info("Schedule job {}: no candidates found", job_id)
            return

        # STAGE 2: ONE batch LLM call classifies everything
        today_d = _date_cls.today()
        client, model, _ = _get_llm_client()
        try:
            classifications = _classify_candidates(client, model, all_candidates, today_d)
        except Exception as e:
            logger.error("Schedule job {}: classify failed: {}", job_id, e)
            db.update_schedule_job(job_id, "failed", error=f"Klassifikation fehlgeschlagen: {e}")
            return

        # Load existing entries now so the harmonize pass can align new
        # candidate titles with DB entries already present on the same date.
        existing_entries: list[dict] = list(db.get_schedule_entries(workspace_id, user_id))

        # STAGE 2c: Cross-candidate title harmonization for events on the same date.
        # Aligns new candidates with each other AND with existing DB entries so
        # fuzzy-merge downstream picks them up instead of creating duplicates.
        try:
            _harmonize_same_date_titles(
                client, model, all_candidates, classifications, today_d, existing_entries,
            )
        except Exception as e:
            logger.warning("Schedule job {}: harmonize pass failed (non-fatal): {}", job_id, e)

        # STAGE 3: Merge into entries (dedup with existing via fuzzy-title + date)
        added = 0

        for cand, cls in zip(all_candidates, classifications):
            if not cls["keep"] or cls["is_footer"] or cls.get("is_historical"):
                logger.info(
                    "Schedule job {}: drop candidate date={} (footer={}, historical={}, keep={})",
                    job_id, cand.get("date_iso") or cand.get("partial_date"),
                    cls["is_footer"], cls.get("is_historical"), cls["keep"],
                )
                continue

            # Resolve the date: explicit ISO -> use it; partial (MM-DD) -> current
            # year; TBD ('nach Vereinbarung') -> no date at all.
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

            ref = {
                "source_uuid": cand["source_uuid"],
                "page_number": cand["page_number"],
                "start_time": cand["start_time"],
                # raw_quote is the short +/-80-char snippet used by the frontend
                # highlight search; context (+/-450) was only for the classifier.
                "raw_quote": cand.get("raw_quote") or cand.get("context"),
            }

            # Try to merge into existing entry (same date + fuzzy title; for TBD:
            # also no-date + fuzzy title).
            merge_target = next(
                (
                    e for e in existing_entries
                    if e.get("due_date") == due_date_obj
                    and _fuzzy_same(cls["title"], e.get("title") or "")
                ),
                None,
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
                due_time=_parse_time(cls["due_time"]),
                is_optional=cls["is_optional"],
                origin="llm",
                source_refs=[ref],
            )
            existing_entries.append(new_row)
            added += 1

        # STAGE 4: mark sources processed
        for src in pending:
            db.mark_source_processed(workspace_id, user_id, src["id"])

        db.update_schedule_job(job_id, "success", added_count=added)
        logger.info("Schedule job {}: added {} new entries", job_id, added)

    except Exception as e:
        logger.error("Schedule job {} failed: {}", job_id, e)
        db.update_schedule_job(job_id, "failed", error=str(e))


__all__ = ["run_generate_schedule"]
