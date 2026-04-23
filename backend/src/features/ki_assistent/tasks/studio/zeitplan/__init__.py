"""KI-Assistent Celery tasks — zeitplan extraction (Regex + Batch-Classify pipeline).

Pipeline:
  1) Regex findet 100% der Datumskandidaten pro Source (_candidates)
  2) Ein Batch-LLM-Call klassifiziert alle (keep/footer/historical/type/title) (_classify)
  3) Same-date Harmonisierung richtet Titel an bestehende Entries aus (_harmonize)
  4) Merge per fuzzy-title + date (_titles) in bestehende Einträge bzw. neu anlegen
"""

from collections import defaultdict
from datetime import date as _date_cls

from langfuse.decorators import observe
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.ki_assistent.tasks._helpers import _get_llm_client

from src.features.ki_assistent.tasks.studio.zeitplan._candidates import (
    _build_candidates_for_source,
)
from src.features.ki_assistent.tasks.studio.zeitplan._classify import _classify_candidates
from src.features.ki_assistent.tasks.studio.zeitplan._harmonize import (
    _harmonize_same_date_titles,
)
from src.features.ki_assistent.tasks.studio.zeitplan._parse import (
    _parse_date,
    _parse_time,
    _resolve_current_year,
)
from src.features.ki_assistent.tasks.studio.zeitplan._titles import _fuzzy_same


@celery_app.task(bind=True, name="kia.generate_zeitplan", queue="kia",
                 soft_time_limit=600, time_limit=720)
@observe(name="kia-zeitplan")
def run_generate_zeitplan(self, job_id: int, module_id: int, user_id: int,
                          source_uuids: list[str]):
    """Regex-first pipeline:
      1) find all date candidates per source via regex (100% recall)
      2) classify all candidates in ONE LLM call (is_event? footer? type? title?)
      3) merge into existing entries (fuzzy-title + same date → append source_ref)
    """
    try:
        db.update_zeitplan_job(job_id, "running")
        logger.info("Zeitplan job {} started", job_id)

        sources: list[dict] = []
        for suuid in source_uuids:
            src = db.get_kia_source(suuid)
            if src and src["module_id"] == module_id:
                sources.append(src)

        already_processed = set(db.get_processed_source_ids(module_id, user_id))
        pending = [s for s in sources if s["id"] not in already_processed]

        if not pending:
            db.update_zeitplan_job(job_id, "success", added_count=0)
            logger.info("Zeitplan job {}: no pending sources", job_id)
            return

        # STAGE 1: Regex-based candidate collection (across all pending sources)
        all_candidates: list[dict] = []
        for src in pending:
            cands = _build_candidates_for_source(src)
            logger.info("Zeitplan job {}: source '{}' → {} date candidates",
                        job_id, src.get("filename", src["id"]), len(cands))
            all_candidates.extend(cands)

        if not all_candidates:
            for src in pending:
                db.mark_source_processed(module_id, user_id, src["id"])
            db.update_zeitplan_job(job_id, "success", added_count=0)
            logger.info("Zeitplan job {}: no candidates found", job_id)
            return

        # STAGE 2: ONE batch LLM call classifies everything
        today_d = _date_cls.today()
        client, model, _ = _get_llm_client()
        try:
            classifications = _classify_candidates(client, model, all_candidates, today_d)
        except Exception as e:
            logger.error("Zeitplan job {}: classify failed: {}", job_id, e)
            db.update_zeitplan_job(job_id, "failed", error=f"Klassifikation fehlgeschlagen: {e}")
            return

        # STAGE 2b: Deterministic slide-footer override.
        # A date that appears 4+ times in the same single source is almost certainly
        # a slide-deck footer (date printed on every slide), not a real event. Force
        # drop ALL candidates sharing (source_uuid, date). We trust this over the LLM
        # because the LLM only sees ±250 chars of context per candidate and can't see
        # how often the same date repeats across the whole document.
        _SLIDE_FOOTER_THRESHOLD = 4
        grp: dict[tuple[str, str], list[int]] = defaultdict(list)
        for idx, cand in enumerate(all_candidates):
            date_key = cand.get("date_iso") or (
                f"partial:{cand['partial_date']}" if cand.get("partial_date") else None
            )
            if date_key is None:
                continue
            grp[(cand["source_uuid"], date_key)].append(idx)
        for (suuid, date_key), indices in grp.items():
            if len(indices) >= _SLIDE_FOOTER_THRESHOLD:
                logger.info(
                    "Zeitplan job {}: slide-footer override — date {} repeats {}x in source {}, dropping all",
                    job_id, date_key, len(indices), suuid,
                )
                for idx in indices:
                    classifications[idx]["keep"] = False
                    classifications[idx]["is_footer"] = True

        # Load existing entries now so the harmonize pass can align new
        # candidate titles with DB entries already present on the same date.
        existing_entries: list[dict] = list(db.get_zeitplan_entries(module_id, user_id))

        # STAGE 2c: Cross-candidate title harmonization for events on the same date.
        # Aligns new candidates with each other AND with existing DB entries so
        # fuzzy-merge downstream picks them up instead of creating duplicates.
        try:
            _harmonize_same_date_titles(
                client, model, all_candidates, classifications, today_d, existing_entries,
            )
        except Exception as e:
            logger.warning("Zeitplan job {}: harmonize pass failed (non-fatal): {}", job_id, e)

        # STAGE 3: Merge into entries (dedup with existing via fuzzy-title + date)
        added = 0

        for cand, cls in zip(all_candidates, classifications):
            if not cls["keep"] or cls["is_footer"] or cls.get("is_historical"):
                logger.info(
                    "Zeitplan job {}: drop candidate date={} (footer={}, historical={}, keep={})",
                    job_id, cand.get("date_iso") or cand.get("partial_date"),
                    cls["is_footer"], cls.get("is_historical"), cls["keep"],
                )
                continue

            # Resolve the date: explicit ISO → use it; partial (MM-DD) → current
            # year; TBD ('nach Vereinbarung') → no date at all.
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
                # raw_quote is the short ±80-char snippet used by the frontend
                # highlight search; context (±450) was only for the classifier.
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
                logger.info("Zeitplan job {}: merged '{}' into entry #{}",
                            job_id, cls["title"], merge_target["id"])
                continue

            type_ = cls["type"] if cls["type"] in ("deadline", "termin") else "termin"
            new_row = db.create_zeitplan_entry(
                module_id,
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
            db.mark_source_processed(module_id, user_id, src["id"])

        db.update_zeitplan_job(job_id, "success", added_count=added)
        logger.info("Zeitplan job {}: added {} new entries", job_id, added)

    except Exception as e:
        logger.error("Zeitplan job {} failed: {}", job_id, e)
        db.update_zeitplan_job(job_id, "failed", error=str(e))


__all__ = ["run_generate_zeitplan"]
