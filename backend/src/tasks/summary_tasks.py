"""Celery task of the summary tool: read the sources, cut, read, plan, write, in stages."""

import json
from pathlib import Path

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.summary import pipeline as pl
from src.features.summary.docx_export import markdown_to_docx
from src.features.summary.models import Caller
from src.features.summary.splitting import original_names, part_size_for_chat, split_sources
from src.features.summary.templates import get_template
from src.features.summary.textlayer import NoReadableText, read_text_layer
from src.i18n import t
from src.limits import (
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
    SUMMARY_MAX_CHARS_PER_SOURCE,
    SUMMARY_MAX_PARTS_PER_JOB,
    SUMMARY_MAX_TOTAL_CHARS,
)
from src.security.usage_log import log_llm_response
from src.services.job_recovery import attempt_failed, still_mine
from src.storage import (
    delete_file,
    get_job_file,
    job_file_exists,
    open_input_file,
    save_job_file,
    save_result_and_evict,
    save_result_file,
)
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage

_MIN_WORDS = 20
_SOURCES_FILE = "sources.json"
_FACTS_FILE = "facts.json"
_OUTLINE_FILE = "outline.json"
_RESULT_FILE = "summary.md"


def _read_text(user_id: int, job_uuid: str, name: str) -> str | None:
    if not job_file_exists(user_id, job_uuid, name):
        return None
    try:
        return get_job_file(user_id, job_uuid, name).decode("utf-8")
    except Exception as e:  # noqa: BLE001 - an unreadable piece is simply redone
        logger.warning("Zusammenfassung {}: {} nicht lesbar ({})", job_uuid[:8], name, e)
        return None


def _write_text(user_id: int, job_uuid: str, name: str, text: str) -> None:
    save_job_file(user_id, job_uuid, name, text.encode("utf-8"))


def _parse_json(job_uuid: str, name: str, raw: str | None, default):
    """Same fallback as an unreadable file: a broken one is treated as absent."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Zusammenfassung {}: {} beschaedigt ({})", job_uuid[:8], name, e)
        return default


def _touch(job_uuid: str, part: int, total: int) -> None:
    """A best-effort heartbeat while reading, so ten large sources never trip the watchdog."""
    try:
        db.update_job_status(job_uuid, "running",
                              progress={"step": "extract", "part": part, "total": total})
        db.touch_job_heartbeat(job_uuid)
    except Exception as e:  # noqa: BLE001 - a missed beat is not worth failing the read for
        logger.warning("Zusammenfassung {}: Herzschlag beim Lesen fehlt ({})", job_uuid[:8], e)


def _zahl(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _read_sources(user_id: int, job_uuid: str, sources: list[dict], locale: str,
                  provider_id: int | None) -> list[dict]:
    """Reads every source once and turns it into the units the map phase works on."""
    vorhanden = _parse_json(job_uuid, _SOURCES_FILE, _read_text(user_id, job_uuid, _SOURCES_FILE), None)
    if vorhanden is not None:
        return vorhanden

    gelesen: list[dict] = []
    gesamt = 0
    woerter = 0
    for i, quelle in enumerate(sources):
        name = quelle["filename"]
        ext = Path(name).suffix.lower().lstrip(".")
        try:
            with open_input_file(quelle["input_path"], f".{ext}") as lokal:
                text = read_text_layer(lokal, ext)
        except NoReadableText:
            raise ValueError(t("summary.sourceOnlyImages", locale, name=name)) from None
        _touch(job_uuid, i + 1, len(sources))
        if not text.strip():
            continue
        if len(text) > SUMMARY_MAX_CHARS_PER_SOURCE:
            raise ValueError(t("summary.sourceTooLarge", locale, name=name,
                               chars=_zahl(len(text)), max=_zahl(SUMMARY_MAX_CHARS_PER_SOURCE)))
        gelesen.append({"source_id": f"q{i + 1}", "filename": name, "content": text})
        gesamt += len(text)
        woerter += len(text.split())

    if woerter < _MIN_WORDS:
        raise ValueError(t("summary.contentTooShort", locale, words=woerter, min=_MIN_WORDS))
    if gesamt > SUMMARY_MAX_TOTAL_CHARS:
        raise ValueError(t("summary.materialTooLarge", locale,
                           chars=_zahl(gesamt), max=_zahl(SUMMARY_MAX_TOTAL_CHARS)))

    groesse = part_size_for_chat(provider_id)
    einheiten = split_sources(gelesen, maximum=groesse, threshold=groesse)
    if len(einheiten) > SUMMARY_MAX_PARTS_PER_JOB:
        raise ValueError(t("summary.tooManyParts", locale, parts=len(einheiten),
                           max=SUMMARY_MAX_PARTS_PER_JOB))
    _write_text(user_id, job_uuid, _SOURCES_FILE, json.dumps(einheiten, ensure_ascii=False))
    logger.info("Zusammenfassung {}: {} Quelle(n), {} Zeichen, {} Einheit(en), Teilgroesse {}",
                job_uuid[:8], len(gelesen), gesamt, len(einheiten), groesse)
    return einheiten


class _JobStore:
    """The job folder as the pipeline sees it, plus the progress row counted in files."""

    def __init__(self, user_id: int, job_uuid: str, versuch: int, units: list[dict]) -> None:
        self._user = user_id
        self._job = job_uuid
        self._versuch = versuch
        self._origins = {u["source_id"]: u.get("origin", u["source_id"]) for u in units}
        self._files = len(set(self._origins.values()))
        self._facts: dict[str, str | None] = {}

    def _guard(self) -> None:
        if not still_mine(self._job, self._versuch):
            raise StageLost(self._job)

    def load_language(self) -> str | None:
        return _read_text(self._user, self._job, "language.txt")

    def save_language(self, language: str) -> None:
        self._guard()
        _write_text(self._user, self._job, "language.txt", language)

    def load_extractions(self) -> dict[str, str | None]:
        roh = _read_text(self._user, self._job, _FACTS_FILE)
        self._facts = _parse_json(self._job, _FACTS_FILE, roh, {})
        return dict(self._facts)

    def save_extraction(self, source_id: str, text: str | None) -> None:
        self._guard()
        self._facts[source_id] = text
        _write_text(self._user, self._job, _FACTS_FILE, json.dumps(self._facts, ensure_ascii=False))
        self.progress("map")

    def _files_done(self) -> int:
        """Uploaded documents whose every part has been read."""
        offen = {h for sid, h in self._origins.items() if sid not in self._facts}
        return self._files - len(offen)

    def load_outline(self) -> dict | None:
        roh = _read_text(self._user, self._job, _OUTLINE_FILE)
        return _parse_json(self._job, _OUTLINE_FILE, roh, None)

    def save_outline(self, outline: dict) -> None:
        self._guard()
        _write_text(self._user, self._job, _OUTLINE_FILE, json.dumps(outline, ensure_ascii=False))

    def load_sections(self) -> dict[int, str]:
        fertig: dict[int, str] = {}
        for i in range(100):
            text = _read_text(self._user, self._job, f"section_{i:02d}.txt")
            if text is None:
                break
            fertig[i] = text
        return fertig

    def save_section(self, index: int, text: str) -> None:
        self._guard()
        _write_text(self._user, self._job, f"section_{index:02d}.txt", text)

    def heartbeat(self) -> None:
        self._guard()
        db.touch_job_heartbeat(self._job)

    def progress(self, step: str, part: int | None = None, total: int | None = None) -> None:
        self._guard()
        # The map phase counts units, the person is shown the files they picked.
        if step == "map":
            part, total = self._files_done(), self._files
        fortschritt: dict = {"step": step}
        if part is not None and total is not None:
            fortschritt |= {"part": part, "total": total}
        db.update_job_status(self._job, "running", progress=fortschritt)
        db.touch_job_heartbeat(self._job)


def _result_name(names: list[str]) -> str:
    """The file name of the result, several uploaded files get a collective name."""
    if len(names) == 1:
        return f"{Path(names[0]).stem}.md"
    return f"{Path(names[0]).stem} und {len(names) - 1} weitere.md"


def _run_summary_inner(job_uuid: str, sources: list[dict], template_slug: str,
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
        "sources": sources, "template_slug": template_slug, "provider_id": provider_id,
    }).encode())

    # Only the first stage reads, a later one must not flash "reading" before "map".
    if not job_file_exists(user_id, job_uuid, _SOURCES_FILE):
        db.update_job_status(job_uuid, "running", progress={"step": "extract"})
    einheiten = _read_sources(user_id, job_uuid, sources, locale, provider_id)

    fertig = _read_text(user_id, job_uuid, _RESULT_FILE)
    if not fertig:
        from src.tasks.general_tasks import _get_llm_client
        traeger = _get_llm_client(provider_id)
        caller = Caller(traeger._async_client, traeger._model,
                        book=lambda antwort: log_llm_response("summary", traeger, antwort))
        store = _JobStore(user_id, job_uuid, versuch, einheiten)
        try:
            fertig = pl.run_pipeline_sync(caller, units=einheiten, template=vorlage,
                                          store=store, should_stop=clock.over)
        except pl.PipelineInterrupted:
            raise StageContinue from None
        _write_text(user_id, job_uuid, _RESULT_FILE, fertig)

    name = _result_name(original_names(einheiten))
    ergebnis = save_result_file(user_id, job_uuid, ".md", fertig.encode("utf-8"))
    try:
        save_result_file(user_id, job_uuid, ".docx", markdown_to_docx(fertig))
    except Exception as e:  # noqa: BLE001 - the Word file is an extra, the Markdown result must still count as done
        logger.error("Zusammenfassung {}: Word-Datei fehlgeschlagen ({})", job_uuid[:8], e)
    save_result_and_evict(user_id, job_uuid, ergebnis, name)
    db.update_job_status(job_uuid, "success")
    for quelle in sources:
        delete_file(quelle["input_path"])
    logger.info("Zusammenfassung {} fertig: {}", job_uuid[:8], name)


@celery_app.task(bind=True, name="summary.run", queue="general", acks_late=True,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def run_summary(self, job_uuid: str, sources: list[dict], template_slug: str,
                provider_id: int | None = None, versuch: int = 0):
    """Celery wrapper, it owns the retry paths and nothing else."""
    try:
        _run_summary_inner(job_uuid, sources, template_slug, provider_id, versuch)
    except StageContinue:
        continue_stage(self, [job_uuid, sources, template_slug, provider_id, versuch], job_uuid)
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
