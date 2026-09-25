"""The slides step: edit, regenerate, delete, insert, reorder, redraw a picture, finish."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies import get_current_user
from src.features.praesentation import bau, folien, gliederung, store, vorlage, vorschau
from src.features.praesentation.schemas import (
    MAX_BILDER_JE_FOLIE, MAX_GIST_CHARS, MAX_PROMPT_CHARS, MAX_TITLE_CHARS,
    Outline, OutlineRow, Slide, bildstellen,
)
from src.i18n import get_locale, t
from src.limits import PRAESENTATION_MAX_SLIDES, PRAESENTATION_SLIDE_CONTEXT_CHARS
from src.routes.praesentation._shared import RegenRequest, llm_antwort, nicht_beschaeftigt, own_job, verlauf
from src.tasks.podcast_tasks._shared import clear_cancel
from src.tasks.praesentation_tasks import run_praesentation_build

router = APIRouter(tags=["praesentation"])


class OrderRequest(BaseModel):
    ids: list[str]


class InsertRequest(BaseModel):
    """A new slide is asked for by its heading, by an instruction, or by both."""

    after: str | None = None
    title: str = Field(default="", max_length=MAX_TITLE_CHARS)
    instruction: str = Field(default="", max_length=MAX_GIST_CHARS)


class NotesRequest(BaseModel):
    """Whether the speaker notes go into the built file, the texts stay either way."""

    include: bool


class ImageRequest(BaseModel):
    """The picture descriptions as the person left them, in the order the slide shows its images."""

    prompts: list[str] = Field(default_factory=list, max_length=MAX_BILDER_JE_FOLIE)


def _stand(job_uuid: str, current_user: dict, locale: str):
    job = own_job(job_uuid, current_user, locale)
    nicht_beschaeftigt(job, locale)
    user_id = job["user_id"]
    params = store.load_params(user_id, job_uuid)
    analyse = store.load_template_meta(user_id, job_uuid)
    slides = store.load_slides(user_id, job_uuid)
    if not params or analyse is None:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    return job, user_id, params, analyse, slides


def _bau(job_uuid: str, user_id: int, locale: str, nur: dict | None, final: bool = False) -> None:
    clear_cancel(job_uuid)
    db.reset_attempts(job_uuid)
    db.update_job_status(job_uuid, "pending",
                         progress={"step": "texte" if nur is None or nur.get("text") else "bilder", "final": final})
    task = run_praesentation_build.apply_async(args=[job_uuid, user_id, locale, 1, 0, nur, final])
    db.set_job_celery_task_id(job_uuid, task.id)


def _speichern(user_id: int, job_uuid: str, slides: list[Slide], gists: dict[str, str] | None = None) -> None:
    store.save_user_slides(user_id, job_uuid, slides)
    outline = store.load_outline(user_id, job_uuid) or Outline()
    alt = {r.id: r for r in outline.rows}
    rows = [alt.get(s.id) or OutlineRow(id=s.id, role=s.role, title=s.title, gist=(gists or {}).get(s.id, ""))
            for s in slides]
    store.save_user_outline(user_id, job_uuid, Outline(title=outline.title, subtitle=outline.subtitle, rows=rows))


def _bilder(user_id: int, job_uuid: str, s: Slide) -> dict[str, bytes]:
    aus = {}
    for k in range(len(s.images)):
        data = store.get_image(user_id, job_uuid, s.id, k)
        if data:
            aus[bau.bild_schluessel(s.id, k)] = data
    if s.body and s.body.kind == "image":
        data = store.get_image(user_id, job_uuid, s.id, "body")
        if data:
            aus[bau.bild_schluessel(s.id, "body")] = data
    return aus



def _stellen_der_folie(user_id: int, job_uuid: str, row: OutlineRow) -> str:
    """The passages the slide was planned on, empty when it has none."""
    if not row.stellen:
        return ""
    from src.services import sources as quellen
    from src.services.text_map import Karte

    return Karte(quellen.load_sources(user_id, job_uuid)).passagen(
        row.stellen, budget=PRAESENTATION_SLIDE_CONTEXT_CHARS)


def _material(user_id: int, job_uuid: str) -> str:
    """Das Material des Laufs als ein Block, aus sources.json."""
    from src.services import sources as quellen

    return quellen.as_block(quellen.load_sources(user_id, job_uuid))

def _nummern_nachziehen(user_id: int, job_uuid: str, params, analyse, vorher: list[Slide],
                        nachher: list[Slide]) -> list[str]:
    """Re-renders the previews whose slide number changed, the ids of those that did."""
    alt = {s.id: i for i, s in enumerate(vorher)}
    geaendert = [(i + 1, s) for i, s in enumerate(nachher) if alt.get(s.id) != i and s.role != "deckblatt"]
    if not geaendert:
        return []
    try:
        outline = store.load_outline(user_id, job_uuid)
        bilder: dict[str, bytes] = {}
        for _, s in geaendert:
            bilder.update(_bilder(user_id, job_uuid, s))
        pngs = vorschau.mehrere(store.load_template(user_id, job_uuid) or b"", analyse, [s for _, s in geaendert],
                                bilder, outline.title if outline else "", params.notes_in_deck,
                                t("praesentation.aiNotice", params.language), nummern=[n for n, _ in geaendert],
                                datum=bau.datum_text(params.language))
    except Exception as e:  # noqa: BLE001 - the order is saved, only the numbers in the pictures are stale
        logger.warning("Präsentation {}: Vorschau nach neuer Reihenfolge fehlgeschlagen: {}", job_uuid[:8], e)
        return []
    for (_, s), png in zip(geaendert, pngs):
        store.save_preview(user_id, job_uuid, s.id, png)
    return [s.id for _, s in geaendert]


@router.put("/praesentation/{job_uuid}/slides/order")
async def save_order(job_uuid: str, body: OrderRequest, current_user: dict = Depends(get_current_user),
                     locale: str = Depends(get_locale)):
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    nach_id = {s.id: s for s in slides}
    if sorted(body.ids) != sorted(nach_id):
        raise HTTPException(status_code=422, detail=t("praesentation.rowNotFound", locale))
    nachher = [nach_id[i] for i in body.ids]
    _speichern(user_id, job_uuid, nachher)
    if job["status"] == "success":
        db.reset_job_to_awaiting(job_uuid)
    neu = await asyncio.to_thread(_nummern_nachziehen, user_id, job_uuid, params, analyse, slides, nachher)
    return {"ids": body.ids, "previews": neu}


@router.put("/praesentation/{job_uuid}/slides/{slide_id}")
async def save_slide(job_uuid: str, slide_id: str, body: Slide, current_user: dict = Depends(get_current_user),
                     locale: str = Depends(get_locale)):
    """Saves the fields, role and layout stay as the system set them, then renders this one slide."""
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    stelle = next((i for i, s in enumerate(slides) if s.id == slide_id), -1)
    if stelle < 0:
        raise HTTPException(status_code=404, detail=t("praesentation.rowNotFound", locale))
    alt = slides[stelle]
    neu = body.model_copy(update={"id": alt.id, "role": alt.role, "layout": alt.layout})
    slides[stelle] = neu
    _speichern(user_id, job_uuid, slides)
    outline = store.load_outline(user_id, job_uuid)
    try:
        vorlage_bytes = store.load_template(user_id, job_uuid) or b""
        png = await asyncio.to_thread(vorschau.einzeln, vorlage_bytes, analyse, neu, _bilder(user_id, job_uuid, neu),
                                      outline.title if outline else "", params.notes_in_deck,
                                      t("praesentation.aiNotice", params.language), stelle + 1,
                                      bau.datum_text(params.language), params.presenter)
        store.save_preview(user_id, job_uuid, neu.id, png)
    except Exception as e:  # noqa: BLE001 - the text is saved, only the picture is stale
        logger.warning("Präsentation {}: Einzelvorschau fehlgeschlagen: {}", job_uuid[:8], e)
    if job["status"] == "success":
        db.reset_job_to_awaiting(job_uuid)
    return neu.model_dump()


@router.post("/praesentation/{job_uuid}/slides/{slide_id}/regen")
async def regen_slide(job_uuid: str, slide_id: str, body: RegenRequest,
                      current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """Returns the new slide content, saving stays the caller's job."""
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    alt = next((s for s in slides if s.id == slide_id), None)
    if alt is None or alt.layout is None:
        raise HTTPException(status_code=404, detail=t("praesentation.rowNotFound", locale))
    outline = store.load_outline(user_id, job_uuid) or Outline()
    row = next((r for r in outline.rows if r.id == slide_id), None) or OutlineRow(id=alt.id, role=alt.role, title=alt.title)
    form = vorlage.form_fuer(analyse.layout(alt.layout), analyse)
    wunsch = next((tr.content for tr in reversed(body.messages) if tr.role == "user"), "")
    # A slide added later carries material of its own, it beats the material of the run.
    quelle = (store.load_slide_source(user_id, job_uuid, slide_id)
              or _stellen_der_folie(user_id, job_uuid, row)
              or _material(user_id, job_uuid)[:PRAESENTATION_SLIDE_CONTEXT_CHARS])
    try:
        antwort = llm_antwort(folien.regen_messages(alt, row, form, params, verlauf(body), body.selected_text, quelle))
        neu = folien.parse_answer(antwort, [row], {row.id: form}, params.notes)[0]
    except Exception as e:  # noqa: BLE001 - the provider is the only source of failure here
        logger.warning("Präsentation: Folie neu vorschlagen gescheitert: {}", e)
        raise HTTPException(status_code=502, detail=t("praesentation.regenFailed", locale)) from e
    neu.layout = alt.layout
    return neu.model_dump()


@router.post("/praesentation/{job_uuid}/slides/{slide_id}/image")
async def regen_image(job_uuid: str, slide_id: str, body: ImageRequest,
                      current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """Takes the picture descriptions as edited, then draws them anew in the build task."""
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    stelle = next((i for i, s in enumerate(slides) if s.id == slide_id), -1)
    if stelle < 0:
        raise HTTPException(status_code=404, detail=t("praesentation.rowNotFound", locale))
    s = slides[stelle]
    if body.prompts:
        for ziel, text in zip(bildstellen(s), body.prompts):
            ziel.prompt = text.strip()[:MAX_PROMPT_CHARS]
        _speichern(user_id, job_uuid, slides)
    _bau(job_uuid, user_id, locale, {"text": [], "bild": [slide_id]})
    return {"job_uuid": job_uuid}


@router.delete("/praesentation/{job_uuid}/slides/{slide_id}")
async def delete_slide(job_uuid: str, slide_id: str, current_user: dict = Depends(get_current_user),
                       locale: str = Depends(get_locale)):
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    s = next((s for s in slides if s.id == slide_id), None)
    if s is None:
        raise HTTPException(status_code=404, detail=t("praesentation.rowNotFound", locale))
    if s.role in ("deckblatt", "abschluss") or len(slides) <= 2:
        raise HTTPException(status_code=422, detail=t("praesentation.badParams", locale))
    nachher = [x for x in slides if x.id != slide_id]
    _speichern(user_id, job_uuid, nachher)
    store.clear_slide_source(user_id, job_uuid, slide_id)
    if job["status"] == "success":
        db.reset_job_to_awaiting(job_uuid)
    neu = await asyncio.to_thread(_nummern_nachziehen, user_id, job_uuid, params, analyse, slides, nachher)
    return {"ok": True, "previews": neu}


@router.post("/praesentation/{job_uuid}/slides")
async def insert_slide(job_uuid: str, body: InsertRequest, current_user: dict = Depends(get_current_user),
                       locale: str = Depends(get_locale)):
    """A new row after the named slide, its role chosen from the neighbour, content by the task."""
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    titel = body.title.strip()
    anweisung = body.instruction.strip()
    if not titel and not anweisung:
        raise HTTPException(status_code=422, detail=t("praesentation.badParams", locale))
    if len(slides) >= PRAESENTATION_MAX_SLIDES:
        raise HTTPException(status_code=422, detail=t("praesentation.tooManySlides", locale, max=PRAESENTATION_MAX_SLIDES))
    stelle = next((i for i, s in enumerate(slides) if s.id == body.after), 0) if body.after else 0
    stelle = min(stelle, len(slides) - 2) if len(slides) >= 2 else stelle
    nachbar = slides[stelle].role if slides else "text"
    rollen = vorlage.waehlbare_rollen(analyse)
    if nachbar == "text" and "text_mit_bild" in rollen:
        rolle = "text_mit_bild"
    elif "text" in rollen:
        rolle = "text"
    else:
        rolle = rollen[0] if rollen else "text"
    neu_id = store.neue_id({s.id for s in slides})
    # Seeded from what is already on the deck, or every insert would land on the role's first layout.
    zaehler: dict[str, int] = {}
    for s in slides:
        if s.layout is not None:
            zaehler[s.role] = zaehler.get(s.role, 0) + 1
    layout = vorlage.layout_fuer(analyse, rolle, zaehler).index
    neu = Slide(id=neu_id, role=rolle, layout=layout, title=titel)
    slides.insert(stelle + 1, neu)
    _speichern(user_id, job_uuid, slides, {neu_id: anweisung})
    # SEAM: a slide added later used to get its own searched material. The search went
    # with the old reading layer, so for now it shares the material of the run.
    store.save_slide_source(user_id, job_uuid, neu_id, "")
    _bau(job_uuid, user_id, locale, {"text": [neu_id], "bild": [neu_id]})
    return {"id": neu_id, "role": rolle}


@router.put("/praesentation/{job_uuid}/notes")
async def save_notes_include(job_uuid: str, body: NotesRequest, current_user: dict = Depends(get_current_user),
                             locale: str = Depends(get_locale)):
    """Only the switch, nothing is rebuilt here, the next finalize picks it up."""
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    params.notes_include = body.include
    store.save_params(user_id, job_uuid, params)
    # The finished file still carries the notes, so it has to be built once more.
    if job["status"] == "success":
        db.reset_job_to_awaiting(job_uuid)
    return {"include": params.notes_include}


@router.post("/praesentation/{job_uuid}/finalize")
async def finalize(job_uuid: str, current_user: dict = Depends(get_current_user),
                   locale: str = Depends(get_locale)):
    job, user_id, params, analyse, slides = _stand(job_uuid, current_user, locale)
    if not slides:
        raise HTTPException(status_code=422, detail=t("praesentation.noDeck", locale))
    _bau(job_uuid, user_id, locale, None, final=True)
    return {"job_uuid": job_uuid}
