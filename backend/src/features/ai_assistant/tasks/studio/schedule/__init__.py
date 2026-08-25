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
from src.limits import AIA_SCHEDULE_SOFT_TIME_LIMIT, AIA_SCHEDULE_TIME_LIMIT
from src.features.ai_assistant.tasks._helpers import _get_llm_client

from src.features.ai_assistant.tasks.studio.schedule._candidates import (
    _build_candidates_for_source,
)
from src.features.ai_assistant.tasks.studio.schedule._classify import (
    _classify_candidates,
    _dated_month_days,
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
    """Was das Modell nicht als Spanne bestaetigt hat, wird wieder zu zwei Terminen.

    Der Kandidatenschritt schlaegt eine Paarung nur vor, er sieht ja nur den Abstand.
    Lehnt die Klassifikation sie ab ("Abgabe 01.09.2026 Klausur 27.09.2026"), darf das
    zweite Datum nicht verloren gehen, sonst waere die Spannen-Erkennung ein Rueckschritt
    gegenueber dem Stand ohne sie.
    """
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


@celery_app.task(bind=True, name="aia.generate_schedule", queue="aia",
                 soft_time_limit=AIA_SCHEDULE_SOFT_TIME_LIMIT, time_limit=AIA_SCHEDULE_TIME_LIMIT)
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

        # STAGE 1+2: For each pending source, reuse stored extraction or
        # run regex + LLM and persist. Result is two index-aligned lists
        # (all_candidates, classifications) covering all pending sources,
        # assembled in `pending` order.
        today_d = _date_cls.today()
        per_source: dict[int, tuple[list[dict], list[dict]]] = {}
        sources_needing_classify: list[tuple[dict, list[dict]]] = []

        # Der Client steht schon vor der Kandidatensuche bereit: sie fragt fuer Termine
        # ohne Datum ("nach Vereinbarung", in jeder Sprache) selbst beim Modell nach.
        # Faellt er aus, laeuft ein Auftrag aus dem Zwischenspeicher trotzdem durch,
        # nur die Klassifikation unten kommt ohne Modell nicht aus.
        try:
            client, model, _ = _get_llm_client()
        except Exception as e:  # noqa: BLE001 - der Zwischenspeicher-Weg braucht kein Modell
            logger.warning("Schedule job {}: kein LLM-Client ({})", job_id, e)
            client, model = None, None

        for src in pending:
            stored = db.get_source_extraction(src["id"])
            if stored is not None:
                per_source[src["id"]] = (stored["candidates"], stored["classifications"])
                logger.info(
                    "Schedule job {}: source '{}' -> cache hit ({} candidates)",
                    job_id, src.get("filename", src["id"]),
                    len(stored["candidates"]),
                )
            else:
                cands = _build_candidates_for_source(src, client=client, model=model)
                logger.info(
                    "Schedule job {}: source '{}' -> {} date candidates (will classify)",
                    job_id, src.get("filename", src["id"]), len(cands),
                )
                sources_needing_classify.append((src, cands))

        # Schon stehende Eintraege des Workspaces. Sie werden weiter unten fuer den
        # Abgleich und das Zusammenfuehren gebraucht und schon hier, damit die
        # Klassifikation weiss, welche Tage mit Jahreszahl belegt sind.
        existing_entries: list[dict] = list(db.get_schedule_entries(workspace_id, user_id))
        workspace_entries: list[dict] = list(db.get_schedule_entries_for_workspace(workspace_id))

        if sources_needing_classify:
            to_classify: list[dict] = []
            for _src, cands in sources_needing_classify:
                to_classify.extend(cands)

            # Ein Vortrag sagt "der 3. Juli", der Kursplan schreibt "03.07.2026". Ohne
            # diesen Hinweis verwirft die Klassifikation den gesprochenen Termin als
            # Erinnerung an frueher, sobald der Tag im laufenden Jahr vorbei ist, und
            # der Zeitplan traegt am Ende nur PDF-Quellen.
            dated_days = _dated_month_days(to_classify, workspace_entries)

            try:
                fresh = _classify_candidates(client, model, to_classify, today_d, dated_days)
            except Exception as e:
                logger.error("Schedule job {}: classify failed: {}", job_id, e)
                db.update_schedule_job(
                    job_id, "failed",
                    error=f"Klassifikation fehlgeschlagen: {e}",
                )
                return

            idx = 0
            for src, cands in sources_needing_classify:
                n = len(cands)
                slice_ = fresh[idx : idx + n]
                per_source[src["id"]] = (cands, slice_)
                db.upsert_source_extraction(src["id"], cands, slice_)
                idx += n

        # Assemble final flat lists in pending order.
        all_candidates: list[dict] = []
        classifications: list[dict] = []
        for src in pending:
            cands, cls = per_source[src["id"]]
            all_candidates.extend(cands)
            classifications.extend(cls)

        # Abgelehnte Paarungen zurueck in zwei Termine, bevor irgendetwas die beiden
        # Listen ueber ihre Position miteinander verbindet.
        all_candidates, classifications = _split_rejected_ranges(all_candidates, classifications)

        if not all_candidates:
            for src in pending:
                db.mark_source_processed(workspace_id, user_id, src["id"])
            db.update_schedule_job(job_id, "success", added_count=0)
            logger.info("Schedule job {}: no candidates found", job_id)
            return

        # Die Eintraege stehen schon oben bereit (die Klassifikation braucht sie auch).
        # `existing_entries` (own) drives the merge loop below.
        # `harmonize_anchors` adds entries from OTHER users in the same workspace
        # so user B's job inherits user A's canonical wording (otherwise
        # harmonize has no anchor when user B uploads both sources at once
        # and the LLM may keep semantically-equal titles like
        # "Abgabe Hausarbeit" vs "Abgabe schriftliche Ausarbeitung" apart).
        own_ids = {e["id"] for e in existing_entries}
        cross_user_anchors = [e for e in workspace_entries if e["id"] not in own_ids]
        harmonize_anchors = existing_entries + cross_user_anchors

        # STAGE 2c: Cross-candidate title harmonization for events on the same date.
        # Aligns new candidates with each other AND with existing DB entries so
        # fuzzy-merge downstream picks them up instead of creating duplicates.
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
            # "month" heisst: die Quelle nannte nur einen Monat. due_date traegt dann den
            # Monatsersten als Sortierpunkt, die Ansicht zeigt keine Tagesnummer.
            precision = "month" if cand.get("date_precision") == "month" else "day"
            end_date_obj = (
                _range_end_date(cand, due_date_obj, today_d) if cls.get("is_range") else None
            )
            # Ein Ende und "laeuft unbegrenzt weiter" schliessen sich aus.
            offenes_ende = bool(cls.get("is_open_ended")) and end_date_obj is None

            ref = {
                "source_uuid": cand["source_uuid"],
                "page_number": cand["page_number"],
                "start_time": cand["start_time"],
                # raw_quote is the short +/-80-char snippet used by the frontend
                # highlight search; context (+/-450) was only for the classifier.
                "raw_quote": cand.get("raw_quote") or cand.get("context"),
            }

            # Try to merge into existing entry (same date + fuzzy title; for TBD:
            # also no-date + fuzzy title or same source text).
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
        for src in pending:
            db.mark_source_processed(workspace_id, user_id, src["id"])

        db.update_schedule_job(job_id, "success", added_count=added)
        logger.info("Schedule job {}: added {} new entries", job_id, added)

    except Exception as e:
        logger.error("Schedule job {} failed: {}", job_id, e)
        db.update_schedule_job(job_id, "failed", error=str(e))


__all__ = ["run_generate_schedule"]
