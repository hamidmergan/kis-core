"""Celery task of the pages tool: plan and blocks, then the pictures, in stages."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.pages import pipeline as pl
from src.features.pages import schema
from src.features.summary.models import INSTRUCTIONS_FILE, Caller
from src.i18n import t
from src.limits import (
    PAGES_DRAW_WAIT_MINUTES,
    PAGES_IMAGE_MAX_PX,
    PAGES_IMAGE_QUALITY,
    PAGES_TRANSLATE_WAIT_MINUTES,
    STAGE_SOFT_TIME_LIMIT,
    STAGE_TIME_LIMIT,
)
from src.security.usage_log import log_llm_response
from src.services import provider_transport, sources
from src.services.job_files import JobState, parse_job_json, read_job_text, write_job_text
from src.services.job_recovery import attempt_failed, still_mine
from src.services.job_statistik import angaben_merken, route_kennung, wer_antwortete
from src.storage import (
    delete_job_file,
    get_job_file,
    job_file_exists,
    job_prefix,
    list_keys,
    save_job_file,
    save_result_and_evict,
)
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.utils import local_date

DRAFT_FILE = "draft.json"
PAGE_FILE = "page.json"
USER_PAGE_FILE = "user_page.json"
PARAMS_FILE = "pages_params.json"
_FAILED_IMAGES = "images_failed.json"


class PagesCaller(Caller):
    """The summary's door for model calls, tagged as pages in the traces."""

    async def create(self, **kwargs):
        kwargs.setdefault("tags", ["pages"])
        return await super().create(**kwargs)


class _JobStore(JobState):
    """What one run keeps between stages, the summary's files plus blocks and frame."""

    def __init__(self, user_id: int, job_uuid: str, versuch: int) -> None:
        self._versuch = versuch
        super().__init__(user_id, job_uuid, guard=self._claim_or_lost)

    def _claim_or_lost(self) -> None:
        if not still_mine(self._job, self._versuch):
            raise StageLost(self._job)

    def _json(self, name: str):
        return parse_job_json(self._job, name, read_job_text(self._user, self._job, name), None)

    def _put(self, name: str, daten) -> None:
        self._guard()
        write_job_text(self._user, self._job, name, json.dumps(daten, ensure_ascii=False))

    def load_map(self):
        return self._json("grundlage.json")

    def save_map(self, daten: dict) -> None:
        self._put("grundlage.json", daten)

    def load_language(self) -> str | None:
        return read_job_text(self._user, self._job, "language.txt")

    def save_language(self, language: str) -> None:
        self._guard()
        write_job_text(self._user, self._job, "language.txt", language)

    def load_outline(self):
        return self._json("outline.json")

    def save_outline(self, outline: dict) -> None:
        self._put("outline.json", outline)

    def load_sections(self) -> dict[int, str]:
        return {}

    def save_section(self, index: int, text: str) -> None:
        pass

    def load_blocks(self) -> dict[int, dict]:
        # Sections finish out of order, so the folder is listed instead of counted up.
        fertig: dict[int, dict] = {}
        for key in list_keys(f"{job_prefix(self._user, self._job)}/blocks_"):
            treffer = re.search(r"blocks_(\d{2})\.json$", key)
            daten = self._json(treffer.group(0)) if treffer else None
            if isinstance(daten, dict):
                fertig[int(treffer.group(1))] = daten
        return fertig

    def save_blocks(self, index: int, data: dict) -> None:
        self._put(f"blocks_{index:02d}.json", data)

    def load_frame(self):
        return self._json("frame.json")

    def save_frame(self, data: dict) -> None:
        self._put("frame.json", data)


def webp(data: bytes) -> bytes:
    """A picture shrunk to the page's width and stored as WebP, a fraction of the PNG."""
    from PIL import Image

    with Image.open(io.BytesIO(data)) as bild:
        bild = bild.convert("RGB")
        bild.thumbnail((PAGES_IMAGE_MAX_PX, PAGES_IMAGE_MAX_PX))
        raus = io.BytesIO()
        bild.save(raus, "WEBP", quality=PAGES_IMAGE_QUALITY, method=4)
        return raus.getvalue()


def _image_wishes(page: dict) -> list[dict]:
    return [b for s in page["sections"] for b in s["blocks"] if b["kind"] == "image"]


def _draw_images(user_id: int, job_uuid: str, page: dict, clock: StageClock, versuch: int) -> None:
    """Draws every named picture that is missing, a failed one is dropped, a busy one waits."""
    from src.features.praesentation import bild
    from src.services.provider_slots import ProviderFull

    gescheitert = set(json.loads(read_job_text(user_id, job_uuid, _FAILED_IMAGES) or "[]"))
    offen = [b for b in _image_wishes(page)
             if b["src"] not in gescheitert and not job_file_exists(user_id, job_uuid, b["src"])]
    if not offen:
        return
    groesse = {pl.HERO_IMAGE: pl.hero_size(page)}
    db.update_job_status(job_uuid, "running", progress={"step": "images", "part": 0,
                                                        "total": len(offen)})

    def eins(wunsch: dict) -> bool:
        if clock.over():
            return False
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        try:
            roh = bild.erzeuge(wunsch["prompt"], groesse.get(wunsch["src"], pl.SECTION_SIZE))
        except ProviderFull:
            logger.info("Pages {}: Bild {} wartet auf einen Platz", job_uuid[:8], wunsch["src"])
            return False
        except Exception as e:  # noqa: BLE001 - a page without a picture is still a page
            logger.warning("Pages {}: Bild {} fehlgeschlagen: {}", job_uuid[:8], wunsch["src"], e)
            gescheitert.add(wunsch["src"])
            return True
        save_job_file(user_id, job_uuid, wunsch["src"], webp(roh))
        db.touch_job_heartbeat(job_uuid)
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        erledigt = list(pool.map(eins, offen))
    write_job_text(user_id, job_uuid, _FAILED_IMAGES, json.dumps(sorted(gescheitert)))
    if not all(erledigt):
        raise StageContinue


def _run_pages_inner(job_uuid: str, provider_id: int | None, versuch: int) -> None:
    """The whole run without the Celery wrapper, so a test can call it directly."""
    if not still_mine(job_uuid, versuch):
        raise StageLost(job_uuid)
    clock = StageClock()
    provider_transport.record_answering()
    auftrag = db.get_job(job_uuid)
    if not auftrag:
        raise RuntimeError(f"Auftrag {job_uuid} nicht gefunden")
    user_id = auftrag["user_id"]
    locale = auftrag.get("creator_locale") or "de"

    quellen = sources.load_sources(user_id, job_uuid)
    if not quellen:
        raise ValueError(t("summary.contentTooShort", locale, words=0, min=20))

    params = parse_job_json(job_uuid, PARAMS_FILE, read_job_text(user_id, job_uuid, PARAMS_FILE), None) or {}
    entwurf = parse_job_json(job_uuid, DRAFT_FILE, read_job_text(user_id, job_uuid, DRAFT_FILE), None)
    if not entwurf:
        from src.tasks.general_tasks import _get_llm_client
        from src.tasks.summary_tasks import _fenster

        traeger = _get_llm_client(provider_id)
        caller = PagesCaller(traeger._async_client, traeger._model, job_uuid=job_uuid,
                             window_tokens=_fenster(provider_id), extra_body=dict(traeger._extra_body),
                             book=lambda antwort: log_llm_response("pages", traeger, antwort))
        store = _JobStore(user_id, job_uuid, versuch)
        anweisung = (read_job_text(user_id, job_uuid, INSTRUCTIONS_FILE) or "").strip()
        try:
            entwurf = asyncio.run(pl.run(caller, sources=quellen, store=store,
                                         should_stop=clock.over, instructions=anweisung,
                                         image_style=params.get("image_style") or ""))
        except pl.PipelineInterrupted:
            raise StageContinue from None
        except pl.NoPlan:
            raise RuntimeError(t("pages.noPlan", locale)) from None
        write_job_text(user_id, job_uuid, DRAFT_FILE, json.dumps(entwurf, ensure_ascii=False))

    _draw_images(user_id, job_uuid, entwurf, clock, versuch)

    entwurf.pop("names", None)
    # A picture that could not be drawn leaves the page instead of standing there empty.
    for s in entwurf["sections"]:
        s["blocks"] = [b for b in s["blocks"]
                       if b["kind"] != "image" or job_file_exists(user_id, job_uuid, b["src"])]
    seite = pl.finish(schema.clean_page(entwurf), today=local_date.today())
    titel = schema.title_of(seite) or "Page"
    pfad = save_job_file(user_id, job_uuid, PAGE_FILE,
                         json.dumps(seite, ensure_ascii=False).encode("utf-8"))
    save_result_and_evict(user_id, job_uuid, pfad, f"{schema.text(titel, 80)}.json")
    angaben_merken(user_id, job_uuid, {
        "anbieter": wer_antwortete("chat", provider_id),
        "bildanbieter": route_kennung("image_gen")["anbieter"] if schema.images_of(seite) else "",
        "workspace": params.get("workspace") or "",
        "bildstil": (params.get("image_style") or "") if schema.images_of(seite) else "",
    })
    db.update_job_status(job_uuid, "success")
    logger.info("Pages {} fertig: {}", job_uuid[:8], titel)


@celery_app.task(bind=True, name="pages.run", queue="long", acks_late=True, priority=9,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def run_pages(self, job_uuid: str, provider_id: int | None = None, versuch: int = 0):
    """Celery wrapper, it owns the retry paths and nothing else."""
    try:
        _run_pages_inner(job_uuid, provider_id, versuch)
    except StageContinue:
        continue_stage(self, [job_uuid, provider_id, versuch], job_uuid)
    except StageLost:
        logger.info("Pages {}: Etappe gehoert nicht mehr uns", job_uuid[:8])
    except Exception as e:
        from celery.exceptions import SoftTimeLimitExceeded
        if isinstance(e, SoftTimeLimitExceeded):
            auftrag = db.get_job(job_uuid)
            locale = (auftrag and auftrag.get("creator_locale")) or "de"
            attempt_failed(job_uuid, t("job.timeoutRetry", locale))
            return
        from src.tasks._errors import handle_task_exception
        handle_task_exception(job_uuid, e, task_label="Pages")
        raise


def load_page(user_id: int, job_uuid: str) -> tuple[dict | None, bool]:
    """The page as last saved, and whether that is the person's own edit."""
    for name, eigen in ((USER_PAGE_FILE, True), (PAGE_FILE, False)):
        try:
            return json.loads(get_job_file(user_id, job_uuid, name)), eigen
        except Exception:  # noqa: BLE001 - a missing file means the next one
            continue
    return None, False


# --- Pictures drawn from the editor -------------------------------------------------------------

def draw_state(user_id: int, job_uuid: str, name: str) -> str:
    """done, failed or pending; a picture waiting longer than its limit counts as failed."""
    if job_file_exists(user_id, job_uuid, name):
        return "done"
    marke = parse_job_json(job_uuid, f"{name}.state", read_job_text(user_id, job_uuid, f"{name}.state"), None)
    if not isinstance(marke, dict) or marke.get("state") == "failed":
        return "failed"
    seit = datetime.fromisoformat(marke["at"])
    return "failed" if datetime.now(timezone.utc) - seit > timedelta(minutes=PAGES_DRAW_WAIT_MINUTES) else "pending"


def draws_of(user_id: int, job_uuid: str) -> list[int]:
    """The numbers of every picture the page ever had drawn or asked for."""
    nummern = set()
    for key in list_keys(f"{job_prefix(user_id, job_uuid)}/img_"):
        treffer = re.search(r"img_(\d{1,3})\.", key)
        if treffer:
            nummern.add(int(treffer.group(1)))
    return sorted(nummern)


def mark_draw(user_id: int, job_uuid: str, name: str, state: str) -> None:
    write_job_text(user_id, job_uuid, f"{name}.state", json.dumps(
        {"state": state, "at": datetime.now(timezone.utc).isoformat()}))


@celery_app.task(bind=True, name="pages.image", acks_late=True, max_retries=20)
def draw_image(self, user_id: int, job_uuid: str, name: str, prompt: str, size: str):
    """One picture the owner asked for in the editor, a busy provider means waiting, not failing."""
    from src.features.praesentation import bild
    from src.services.provider_slots import ProviderFull

    try:
        roh = bild.erzeuge(prompt, size)
    except ProviderFull as e:
        logger.info("Pages {}: Bild {} wartet auf einen Platz", job_uuid[:8], name)
        raise self.retry(countdown=15) from e
    except Exception as e:  # noqa: BLE001 - the editor shows the failure, the page stays as it was
        logger.warning("Pages {}: Bild {} fehlgeschlagen: {}", job_uuid[:8], name, e)
        mark_draw(user_id, job_uuid, name, "failed")
        return
    save_job_file(user_id, job_uuid, name, webp(roh))
    logger.info("Pages {}: Bild {} neu gezeichnet", job_uuid[:8], name)


# --- Other languages ----------------------------------------------------------------------------

def _known(key: str) -> str:
    """Only a listed language becomes part of a file name, nothing a request made up."""
    from src.features.pages.translate import LANGUAGES

    if key not in LANGUAGES:
        raise ValueError(f"unknown language {key!r}")
    return key


def variant_file(key: str) -> str:
    return f"page_{_known(key)}.json"


def _state_file(key: str) -> str:
    return f"lang_{_known(key)}.json"


def stamp(page: dict) -> str:
    """Which content a translation was made from, a save without a change keeps it."""
    inhalt = {k: v for k, v in page.items() if k != "saved_at"}
    return hashlib.sha256(json.dumps(inhalt, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def load_variant(user_id: int, job_uuid: str, key: str) -> dict | None:
    from src.features.pages.translate import LANGUAGES

    if key not in LANGUAGES:
        return None
    try:
        return json.loads(get_job_file(user_id, job_uuid, variant_file(key)))
    except Exception:  # noqa: BLE001 - a missing file means no such language yet
        return None


def language_states(user_id: int, job_uuid: str) -> dict[str, dict]:
    """Every language the page has or is getting, a translation stuck past its limit counts as failed."""
    from src.features.pages.translate import LANGUAGES

    raus: dict[str, dict] = {}
    for key in list_keys(f"{job_prefix(user_id, job_uuid)}/lang_"):
        treffer = re.search(r"lang_([a-z]+)\.json$", key)
        if not treffer or treffer.group(1) not in LANGUAGES:
            continue
        name = treffer.group(1)
        daten = parse_job_json(job_uuid, _state_file(name), read_job_text(user_id, job_uuid, _state_file(name)), None)
        if not isinstance(daten, dict):
            continue
        if daten.get("state") == "running":
            seit = datetime.fromisoformat(daten["at"])
            if datetime.now(timezone.utc) - seit > timedelta(minutes=PAGES_TRANSLATE_WAIT_MINUTES):
                daten["state"] = "failed"
        raus[name] = daten
    return raus


def key_of(page: dict) -> str:
    """The language key of a page, Leichte Sprache apart from plain German."""
    return "easy" if page.get("easy") else (page.get("lang") or "de")


def readable(user_id: int, job_uuid: str, page: dict) -> list[dict]:
    """The languages a reader can switch between, the page's own first, then every finished one."""
    from src.features.pages.translate import LANGUAGES

    eigene = key_of(page)
    fertig = {k for k, v in language_states(user_id, job_uuid).items() if v.get("state") == "done"}
    keys = [eigene] + [k for k in LANGUAGES if k in fertig and k != eigene]
    return [{"key": k, "label": LANGUAGES[k]["label"]} for k in keys if k in LANGUAGES]


def in_language(user_id: int, job_uuid: str, page: dict, key: str | None) -> dict:
    """The page in the asked language when it has one, else the page itself.

    A section hidden in the page stays hidden in every language, even one translated before.
    """
    if not key or key == key_of(page) or key not in {x["key"] for x in readable(user_id, job_uuid, page)}:
        return page
    variante = load_variant(user_id, job_uuid, key)
    if not variante:
        return page
    versteckt = {s.get("id") for s in page.get("sections") or [] if s.get("hidden")}
    return {**variante, "sections": [{**s, "hidden": True} if s.get("id") in versteckt else s
                                     for s in variante.get("sections") or []]}


def viewer_images(user_id: int, job_uuid: str, page: dict) -> set[str]:
    """Every picture a reader may load, from the page and from each of its languages as readers see them."""
    bilder = set(schema.images_of(page))
    for x in readable(user_id, job_uuid, page)[1:]:
        bilder |= schema.images_of(in_language(user_id, job_uuid, page, x["key"]))
    return bilder


def set_language_state(user_id: int, job_uuid: str, key: str, state: str, source: str) -> None:
    write_job_text(user_id, job_uuid, _state_file(key), json.dumps(
        {"state": state, "source": source, "at": datetime.now(timezone.utc).isoformat()}))


def drop_language(user_id: int, job_uuid: str, key: str) -> None:
    for name in (variant_file(key), _state_file(key)):
        try:
            delete_job_file(user_id, job_uuid, name)
        except Exception:  # noqa: BLE001 - already gone is fine
            pass


def page_caller(user_id: int, job_uuid: str) -> PagesCaller:
    """The chat model the page was written with, for every later call about it."""
    from src.tasks.general_tasks import _get_llm_client
    from src.tasks.summary_tasks import _fenster

    params = parse_job_json(job_uuid, PARAMS_FILE, read_job_text(user_id, job_uuid, PARAMS_FILE), None) or {}
    provider_id = params.get("provider_id")
    traeger = _get_llm_client(provider_id)
    return PagesCaller(traeger._async_client, traeger._model, job_uuid=job_uuid,
                       window_tokens=_fenster(provider_id), extra_body=dict(traeger._extra_body),
                       book=lambda antwort: log_llm_response("pages", traeger, antwort))


@celery_app.task(name="pages.translate", acks_late=True,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def translate_page(user_id: int, job_uuid: str, key: str):
    """The page as last saved in one more language, written beside the page."""
    from src.features.pages import translate as tr

    page, _ = load_page(user_id, job_uuid)
    if not page:
        return
    quelle = stamp(page)
    try:
        neu = asyncio.run(tr.translate(page_caller(user_id, job_uuid), page, key))
    except Exception as e:  # noqa: BLE001 - the owner sees the failure and may try again
        logger.warning("Pages {}: Sprache {} fehlgeschlagen: {}", job_uuid[:8], key, e)
        set_language_state(user_id, job_uuid, key, "failed", quelle)
        return
    save_job_file(user_id, job_uuid, variant_file(key), json.dumps(neu, ensure_ascii=False).encode("utf-8"))
    set_language_state(user_id, job_uuid, key, "done", quelle)
    logger.info("Pages {}: Sprache {} fertig", job_uuid[:8], key)
