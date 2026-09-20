"""Celery task of the summary tool: read the sources, cut, read, plan, write, in stages."""

import json
import re
from pathlib import Path

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.summary import pipeline as pl
from src.features.summary import settings as cfg
from src.features.summary import window, writing
from src.features.summary.docx_export import markdown_to_docx
from src.features.summary.models import Caller
from src.features.summary.templates import get_template
from src.features.summary.textlayer import NoReadableText, read_text_layer
from src.i18n import t
from src.limits import (
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
    SUMMARY_MAX_SOURCES,
    SUMMARY_WRITE_MAX_TOKENS,
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
    """Reads every source once, each one whole, and checks it against the model's window."""
    vorhanden = _parse_json(job_uuid, _SOURCES_FILE, _read_text(user_id, job_uuid, _SOURCES_FILE), None)
    if vorhanden is not None:
        return vorhanden

    gelesen: list[dict] = []
    gesamt = 0
    woerter = 0
    # Read once per stage, so every file of this run is measured against the same number.
    je_datei = cfg.chars_per_source()
    for i, quelle in enumerate(sources):
        name = quelle["filename"]
        ext = Path(name).suffix.lower().lstrip(".")
        try:
            with open_input_file(quelle["input_path"], f".{ext}") as lokal:
                seiten = _pages_or_raise(lokal, f".{ext}", name, locale)
                text = read_text_layer(lokal, ext)
        except NoReadableText:
            raise ValueError(t("summary.sourceOnlyImages", locale, name=name)) from None
        _touch(job_uuid, i + 1, len(sources))
        if not text.strip():
            continue
        if len(text) > je_datei:
            raise ValueError(t("summary.sourceTooLarge", locale, name=name,
                               chars=_zahl(len(text)), max=_zahl(je_datei)))
        gelesen.append({"source_id": f"doc_{i + 1:02d}", "filename": name, "content": text,
                        "ext": ext, "pages": seiten})
        gesamt += len(text)
        woerter += len(text.split())

    if woerter < _MIN_WORDS:
        raise ValueError(t("summary.contentTooShort", locale, words=woerter, min=_MIN_WORDS))
    if gesamt > SUMMARY_MAX_SOURCES * je_datei:
        raise ValueError(t("summary.materialTooLarge", locale,
                           chars=_zahl(gesamt), max=_zahl(SUMMARY_MAX_SOURCES * je_datei)))

    _window_or_raise(gelesen, provider_id, locale)
    _write_text(user_id, job_uuid, _SOURCES_FILE, json.dumps(gelesen, ensure_ascii=False))
    logger.info("Zusammenfassung {}: {} Quelle(n), {} Zeichen, je Datei ein Aufruf",
                job_uuid[:8], len(gelesen), gesamt)
    return gelesen


def _pages_or_raise(path: str, ext: str, name: str, locale: str) -> int | None:
    """Rejects a document with more pages than the management allows, else returns the count."""
    from src.services.tool_limits import max_source_pages
    from src.utils.file_validation import count_pages

    seiten = count_pages(ext, path)
    grenze = max_source_pages()
    if seiten is not None and seiten > grenze:
        raise ValueError(t("summary.sourceTooManyPages", locale, name=name,
                           pages=seiten, max=grenze))
    return seiten


def _window_or_raise(sources: list[dict], provider_id: int | None, locale: str) -> None:
    """Refuses before the first call what the chosen model provably cannot read whole."""
    profil = window.profile_for_choice(provider_id)
    for quelle in sources:
        urteil = window.verdict_for(len(quelle["content"]), SUMMARY_WRITE_MAX_TOKENS, profil)
        if urteil.fits:
            continue
        raise ValueError(t("summary.modelWindowTooSmall", locale, name=quelle["filename"],
                           chars=_zahl(len(quelle["content"])),
                           needed=_zahl(urteil.needed_tokens),
                           window=_zahl(urteil.window_tokens)))


class _JobStore:
    """The job folder as the pipeline sees it, plus the progress row counted in files."""

    def __init__(self, user_id: int, job_uuid: str, versuch: int, sources: list[dict]) -> None:
        self._user = user_id
        self._job = job_uuid
        self._versuch = versuch
        self._ids = [q["source_id"] for q in sources]
        self._files = len(self._ids)
        self._facts: dict[str, list[dict]] = {}

    def _guard(self) -> None:
        if not still_mine(self._job, self._versuch):
            raise StageLost(self._job)

    def load_language(self) -> str | None:
        return _read_text(self._user, self._job, "language.txt")

    def save_language(self, language: str) -> None:
        self._guard()
        _write_text(self._user, self._job, "language.txt", language)

    def load_extractions(self) -> dict[str, list[dict]]:
        roh = _read_text(self._user, self._job, _FACTS_FILE)
        self._facts = _parse_json(self._job, _FACTS_FILE, roh, {})
        return dict(self._facts)

    def save_extraction(self, source_id: str, facts: list[dict]) -> None:
        self._guard()
        self._facts[source_id] = facts
        _write_text(self._user, self._job, _FACTS_FILE, json.dumps(self._facts, ensure_ascii=False))
        self.progress("map")

    def _files_done(self) -> int:
        """Uploaded documents that have been read."""
        return sum(1 for sid in self._ids if sid in self._facts)

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


_TITLE_MAX_CHARS = 80
# Anything a file name must not carry, on any of the systems a download lands on.
_TITLE_FORBIDDEN = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def _outline_title(user_id: int, job_uuid: str) -> str:
    """The title the planning call already gave this document, "" when there is none.

    The plan is on disk from that one call, so no extra call is needed to name the file.
    """
    plan = _parse_json(job_uuid, _OUTLINE_FILE,
                       _read_text(user_id, job_uuid, _OUTLINE_FILE), None)
    if not isinstance(plan, dict):
        return ""
    return str(plan.get("title") or "").strip()


def _docx_locale(user_id: int, job_uuid: str, fallback: str) -> str:
    """The language of the Word cover page: German for a German document, English for the rest.

    It follows the document, not the person who started the run, because a reader of the
    file only ever sees the document. A failed language probe falls back to that person.
    """
    sprache = (_read_text(user_id, job_uuid, "language.txt") or "").strip()
    if not sprache or sprache == pl.LANGUAGE_FALLBACK:
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
    quellen = _read_sources(user_id, job_uuid, sources, locale, provider_id)

    fertig = _read_text(user_id, job_uuid, _RESULT_FILE)
    if not fertig:
        from src.tasks.general_tasks import _get_llm_client
        traeger = _get_llm_client(provider_id)
        caller = Caller(traeger._async_client, traeger._model, job_uuid=job_uuid,
                        book=lambda antwort: log_llm_response("summary", traeger, antwort))
        store = _JobStore(user_id, job_uuid, versuch, quellen)
        try:
            fertig = pl.run_pipeline_sync(caller, sources=quellen, template=vorlage,
                                          store=store, should_stop=clock.over)
        except pl.PipelineInterrupted:
            raise StageContinue from None
        _write_text(user_id, job_uuid, _RESULT_FILE, fertig)

    # The heading of the finished text, else the plan's title: a build plan without
    # headings keeps the title out of the Markdown, the plan still carries it.
    eigener, rumpf = writing.split_title(fertig)
    titel = eigener or _outline_title(user_id, job_uuid)
    name = _result_name([q["filename"] for q in quellen], titel)
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
