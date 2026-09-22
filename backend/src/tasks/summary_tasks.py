"""Celery task of the summary tool: plan, write, assemble, in stages."""

import asyncio
import json
import re
from pathlib import Path

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.summary import pipeline as pl
from src.features.summary import writing
from src.features.summary.docx_export import markdown_to_docx
from src.features.summary.models import LANGUAGE_FALLBACK, Caller
from src.features.summary.templates import get_template
from src.i18n import t
from src.limits import (
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
    SUMMARY_MAX_SOURCES,
    SUMMARY_WRITE_MAX_TOKENS,
)
from src.security.usage_log import log_llm_response
from src.services import sources
from src.services.job_files import (
    JobState,
    parse_job_json,
    read_job_text,
    write_job_text,
)
from src.services.job_recovery import attempt_failed, still_mine
from src.storage import (
    job_file_exists,
    open_input_file,
    save_job_file,
    save_result_and_evict,
    save_result_file,
)
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage

_MIN_WORDS = 20
_OUTLINE_FILE = "outline.json"
_MAP_FILE = "grundlage.json"
_RESULT_FILE = "summary.md"







class _JobStore(JobState):
    """What one run keeps between stages: language, topics, plan, finished sections."""

    def __init__(self, user_id: int, job_uuid: str, versuch: int) -> None:
        self._versuch = versuch
        super().__init__(user_id, job_uuid, guard=self._claim_or_lost)

    def _claim_or_lost(self) -> None:
        """A stage that lost its claim stops writing, that is what the service asks of us."""
        if not still_mine(self._job, self._versuch):
            raise StageLost(self._job)

    def load_map(self) -> dict | None:
        roh = read_job_text(self._user, self._job, _MAP_FILE)
        return parse_job_json(self._job, _MAP_FILE, roh, None)

    def save_map(self, daten: dict) -> None:
        self._guard()
        write_job_text(self._user, self._job, _MAP_FILE, json.dumps(daten, ensure_ascii=False))

    def load_language(self) -> str | None:
        return read_job_text(self._user, self._job, "language.txt")

    def save_language(self, language: str) -> None:
        self._guard()
        write_job_text(self._user, self._job, "language.txt", language)

    def load_outline(self) -> dict | None:
        roh = read_job_text(self._user, self._job, _OUTLINE_FILE)
        return parse_job_json(self._job, _OUTLINE_FILE, roh, None)

    def save_outline(self, outline: dict) -> None:
        self._guard()
        write_job_text(self._user, self._job, _OUTLINE_FILE,
                       json.dumps(outline, ensure_ascii=False))

    def load_sections(self) -> dict[int, str]:
        fertig: dict[int, str] = {}
        for i in range(100):
            text = read_job_text(self._user, self._job, f"section_{i:02d}.txt")
            if text is None:
                break
            fertig[i] = text
        return fertig

    def save_section(self, index: int, text: str) -> None:
        self._guard()
        write_job_text(self._user, self._job, f"section_{index:02d}.txt", text)


_TITLE_MAX_CHARS = 80
# Anything a file name must not carry, on any of the systems a download lands on.
_TITLE_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _outline_title(user_id: int, job_uuid: str) -> str:
    """The title the planning call already gave this document, "" when there is none.

    The plan is on disk from that one call, so no extra call is needed to name the file.
    """
    plan = parse_job_json(job_uuid, _OUTLINE_FILE,
                       read_job_text(user_id, job_uuid, _OUTLINE_FILE), None)
    if not isinstance(plan, dict):
        return ""
    return str(plan.get("title") or "").strip()


def _docx_locale(user_id: int, job_uuid: str, fallback: str) -> str:
    """The language of the Word cover page: German for a German document, English for the rest.

    It follows the document, not the person who started the run, because a reader of the
    file only ever sees the document. A failed language probe falls back to that person.
    """
    sprache = (read_job_text(user_id, job_uuid, "language.txt") or "").strip()
    if not sprache or sprache == LANGUAGE_FALLBACK:
        return fallback
    return "de" if sprache.casefold() in ("german", "deutsch") else "en"


def _clean_title(raw: str) -> str:
    """A title reduced to what may stand in a file name, "" when nothing is left."""
    titel = " ".join(str(raw or "").split()).lstrip("#").strip()
    titel = _TITLE_FORBIDDEN.sub(" ", titel)
    titel = " ".join(titel.split()).strip(" .")
    if len(titel) > _TITLE_MAX_CHARS:
        gekuerzt = titel[:_TITLE_MAX_CHARS].rsplit(" ", 1)[0]
        titel = (gekuerzt or titel[:_TITLE_MAX_CHARS]).strip(" .")
    return titel


def _result_name(names: list[str], title: str = "") -> str:
    """The file name of the result, the document's own title when it has one.

    Without a title, several uploaded files get a collective name.
    """
    titel = _clean_title(title)
    if titel:
        return f"{titel}.md"
    if len(names) == 1:
        return f"{Path(names[0]).stem}.md"
    return f"{Path(names[0]).stem} und {len(names) - 1} weitere.md"


def _fenster(provider_id: int | None) -> int:
    """Das gemessene Fenster des Modells dieses Laufs, 0 wenn es keines gibt."""
    from src.services.model_limits import ensure_profile

    try:
        if provider_id is not None:
            from src.services.feature_provider_choices import resolve_binding
            binding = resolve_binding("chat", provider_id)
        else:
            from src.services import feature_router
            binding = feature_router.resolve("chat")
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - ohne Messung laeuft der Auftrag einfach los
        logger.warning("Zusammenfassung: Modell nicht vermessbar ({})", e)
        return 0


def _run_summary_inner(job_uuid: str, template_slug: str,
                       provider_id: int | None, versuch: int) -> None:
    """The whole run without the Celery wrapper, so a test can call it directly."""
    if not still_mine(job_uuid, versuch):
        raise StageLost(job_uuid)
    clock = StageClock()
    auftrag = db.get_job(job_uuid)
    if not auftrag:
        raise RuntimeError(f"Auftrag {job_uuid} nicht gefunden")
    user_id = auftrag["user_id"]
    locale = auftrag.get("creator_locale") or "de"

    vorlage = get_template(template_slug)
    if vorlage is None:
        raise ValueError(t("summary.templateMissing", locale))

    save_job_file(user_id, job_uuid, "summary_params.json", json.dumps({
        "template_slug": template_slug, "provider_id": provider_id,
    }).encode())

    # The material of the run, read and laid down before the task was queued.
    quellen = sources.load_sources(user_id, job_uuid)
    if not quellen:
        raise ValueError(t("summary.contentTooShort", locale, words=0, min=_MIN_WORDS))

    fertig = read_job_text(user_id, job_uuid, _RESULT_FILE)
    if not fertig:
        from src.tasks.general_tasks import _get_llm_client
        traeger = _get_llm_client(provider_id)
        caller = Caller(traeger._async_client, traeger._model, job_uuid=job_uuid,
                        window_tokens=_fenster(provider_id),
                        book=lambda antwort: log_llm_response("summary", traeger, antwort))
        store = _JobStore(user_id, job_uuid, versuch)
        try:
            fertig = asyncio.run(pl.run(caller, sources=quellen, template=vorlage,
                                        store=store, should_stop=clock.over))
        except pl.PipelineInterrupted:
            raise StageContinue from None
        write_job_text(user_id, job_uuid, _RESULT_FILE, fertig)

    # The heading of the finished text, else the plan's title: a build plan without
    # headings keeps the title out of the Markdown, the plan still carries it.
    eigener, rumpf = writing.split_title(fertig)
    titel = eigener or _outline_title(user_id, job_uuid)
    name = _result_name([q.dateiname for q in quellen], titel)
    ergebnis = save_result_file(user_id, job_uuid, ".md", fertig.encode("utf-8"))
    try:
        save_result_file(user_id, job_uuid, ".docx",
                         markdown_to_docx(rumpf, title=titel or Path(name).stem,
                                          locale=_docx_locale(user_id, job_uuid, locale)))
    except Exception as e:  # noqa: BLE001 - the Word file is an extra, the Markdown result must still count as done
        from celery.exceptions import SoftTimeLimitExceeded
        if isinstance(e, SoftTimeLimitExceeded):
            raise  # a stage timeout must reach run_summary's own handling, not be logged away here
        logger.error("Zusammenfassung {}: Word-Datei fehlgeschlagen ({})", job_uuid[:8], e)
    save_result_and_evict(user_id, job_uuid, ergebnis, name)
    db.update_job_status(job_uuid, "success")
    logger.info("Zusammenfassung {} fertig: {}", job_uuid[:8], name)


@celery_app.task(bind=True, name="summary.run", queue="general", acks_late=True,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def run_summary(self, job_uuid: str, template_slug: str,
                provider_id: int | None = None, versuch: int = 0):
    """Celery wrapper, it owns the retry paths and nothing else."""
    try:
        _run_summary_inner(job_uuid, template_slug, provider_id, versuch)
    except StageContinue:
        continue_stage(self, [job_uuid, template_slug, provider_id, versuch], job_uuid)
    except StageLost:
        logger.info("Zusammenfassung {}: Etappe gehoert nicht mehr uns", job_uuid[:8])
    except Exception as e:
        from celery.exceptions import SoftTimeLimitExceeded
        if isinstance(e, SoftTimeLimitExceeded):
            auftrag = db.get_job(job_uuid)
            locale = (auftrag and auftrag.get("creator_locale")) or "de"
            attempt_failed(job_uuid, t("job.timeoutRetry", locale))
            return
        from src.tasks._errors import handle_task_exception
        handle_task_exception(job_uuid, e, task_label="Summary")
        raise
