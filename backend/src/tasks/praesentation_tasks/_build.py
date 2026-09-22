"""Writes the slides in batches, draws the pictures, builds the deck and its previews, in stages."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.features.praesentation import bau, bild
from src.features.praesentation import folien, gliederung, store, teilung, vorlage, vorschau
from src.features.praesentation.schemas import Outline, OutlineRow, Slide
from src.features.praesentation.vorlage import Analyse
from src.i18n import t
from src.limits import (
    PRAESENTATION_BATCH, PRAESENTATION_IMAGE_PARALLELISM, STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT,
)
from src.services import feature_router
from src.services.text_map import Karte
from src.services.json_llm import call_json_llm
from src.services import sources as quellen
from src.services.job_recovery import attempt_failed, still_mine
from src.storage import save_result_and_evict
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.utils.heartbeat import job_heartbeat

_VERSUCHE = 3
_DATEINAME = re.compile(r"[^\w\s\-]", re.U)


def _fortschritt(final: bool, step: str, **extra) -> dict:
    """One progress snapshot, tagged with the finalize intent so a resume never loses it."""
    return {"step": step, "final": final, **extra}


@celery_app.task(bind=True, name="praesentation.build", queue="general", acks_late=True,
                 soft_time_limit=STAGE_SOFT_TIME_LIMIT, time_limit=STAGE_TIME_LIMIT)
def run_praesentation_build(self, job_uuid: str, user_id: int, locale: str = "de",
                            etappe: int = 1, versuch: int = 0, nur: dict | None = None, final: bool = False):
    try:
        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        clock = StageClock()
        params = store.load_params(user_id, job_uuid)
        quellenliste = quellen.load_sources(user_id, job_uuid)
        quelle = quellen.as_block(quellenliste)
        analyse = store.load_template_meta(user_id, job_uuid)
        vorlage_bytes = store.load_template(user_id, job_uuid)
        outline = store.load_outline(user_id, job_uuid)
        if not params or analyse is None or vorlage_bytes is None or outline is None:
            raise RuntimeError("Auftrag ohne Vorlage, Gliederung oder Einstellungen")
        erzwungen_text = set((nur or {}).get("text") or [])
        erzwungen_bild = set((nur or {}).get("bild") or [])

        slides = {s.id: s for s in store.load_slides(user_id, job_uuid)}
        layouts = _layouts_zuweisen(outline, slides, analyse)

        offen = [r for r in outline.rows if r.id not in slides or r.id in erzwungen_text]
        if offen:
            _texte_schreiben(job_uuid, user_id, params, quelle, quellenliste,
                             analyse, outline, slides, layouts, offen, erzwungen_text,
                             clock, final)
        geordnet = [slides[r.id] for r in outline.rows if r.id in slides]

        fehlend = _fehlende_bilder(user_id, job_uuid, geordnet, analyse, erzwungen_bild)
        if fehlend:
            _bilder_erzeugen(job_uuid, user_id, params.style_text, fehlend, clock, versuch, final)

        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "bau"))
        with job_heartbeat(job_uuid):
            geordnet = teilung.teile_ueberlauf(geordnet, analyse)
            store.save_slides(user_id, job_uuid, geordnet)
            store.save_user_slides(user_id, job_uuid, geordnet)
            store.save_user_outline(user_id, job_uuid, _outline_angleichen(outline, geordnet))
            bilder = _bilder_laden(user_id, job_uuid, geordnet)
            deck = bau.baue(vorlage_bytes, analyse, geordnet, bilder, outline.title, params.notes_in_deck,
                            t("praesentation.aiNotice", params.language))
            deck_path = store.save_deck(user_id, job_uuid, deck)
            db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "vorschau"))
            try:
                for s, png in zip(geordnet, vorschau.render(deck)):
                    store.save_preview(user_id, job_uuid, s.id, png)
            except Exception as e:  # noqa: BLE001 - a missing preview must not cost the deck
                logger.warning("Präsentation {}: Vorschau fehlgeschlagen: {}", job_uuid[:8], e)

        if final:
            name = (_DATEINAME.sub("", outline.title).strip() or "Praesentation")[:80]
            # The exact value the storage helper returned, the same idiom the podcast render uses.
            save_result_and_evict(user_id, job_uuid, deck_path, f"{name}.pptx")
            db.update_job_status(job_uuid, "success", progress=_fortschritt(final, "done"))
        else:
            db.update_job_status(job_uuid, "awaiting_user", progress=_fortschritt(final, "slides_done"))
        logger.info("Präsentation {}: {} Folien gebaut", job_uuid[:8], len(geordnet))
        return {"slides": len(geordnet)}

    except StageContinue:
        continue_stage(self, [job_uuid, user_id, locale, etappe + 1, versuch, nur, final], job_uuid)
        return {"etappe": etappe}
    except StageLost:
        logger.info("Präsentation {}: Etappe gehört nicht mehr uns, nichts getan", job_uuid[:8])
        return {"lost": True}
    except JobCancelled:
        db.reset_job_to_awaiting(job_uuid)
        return {"cancelled": True}
    except Exception as e:
        logger.error("Präsentation-Bau {} fehlgeschlagen: {}", job_uuid[:8], e)
        attempt_failed(job_uuid, t("praesentation.buildFailed", locale))
        raise


def _layouts_zuweisen(outline: Outline, slides: dict[str, Slide], analyse: Analyse) -> dict[str, int]:
    """One layout per row, kept where a slide already has one, rotated for the new ones."""
    zaehler: dict[str, int] = {}
    aus: dict[str, int] = {}
    for r in outline.rows:
        s = slides.get(r.id)
        if s is not None and s.layout is not None:
            aus[r.id] = s.layout
        else:
            aus[r.id] = vorlage.layout_fuer(analyse, r.role, zaehler).index
    return aus


def _eigenes_material(user_id, job_uuid, offen, erzwungen_text: set[str]) -> dict[str, str]:
    """Only a slide asked for by hand can carry material of its own, so only those are looked up."""
    aus: dict[str, str] = {}
    for r in offen:
        if r.id not in erzwungen_text:
            continue
        text = store.load_slide_source(user_id, job_uuid, r.id)
        if text.strip():
            aus[r.id] = text
    return aus


def _texte_schreiben(job_uuid, user_id, params, quelle, quellenliste, analyse,
                     outline, slides, layouts, offen, erzwungen_text, clock, final) -> None:
    llm = feature_router.make_llm_client(feature_router.resolve("chat"))
    karte = Karte(quellenliste)
    eigen = _eigenes_material(user_id, job_uuid, offen, erzwungen_text)
    # A slide with its own material goes alone, it must not share a call with the run's snapshot.
    rest = [r for r in offen if r.id not in eigen]
    pakete = [[r] for r in offen if r.id in eigen]
    pakete += [rest[i:i + PRAESENTATION_BATCH] for i in range(0, len(rest), PRAESENTATION_BATCH)]
    fertig = 0
    db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "texte", current=0, total=len(offen)))
    with job_heartbeat(job_uuid):
        for n, paket in enumerate(pakete):
            assert_not_cancelled(job_uuid)
            formen = {r.id: vorlage.form_fuer(analyse.layout(layouts[r.id]), analyse) for r in paket}
            # A slide with material of its own keeps it, the rest get their passages.
            if paket[0].id in eigen:
                nachrichten = folien.build_messages(eigen[paket[0].id], params, paket, formen)
            else:
                je_folie = folien.material_je_folie(paket, karte, outline.rows)
                nachrichten = folien.build_messages(quelle, params, paket, formen,
                                                    je_folie or None)
            letzter = ""
            for _ in range(_VERSUCHE):
                antwort = call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""
                try:
                    neue = folien.parse_answer(antwort, paket, formen, params.notes)
                    break
                except gliederung.Unusable as e:
                    letzter = str(e)
                    logger.warning("Präsentation {}: Folienpaket unbrauchbar: {}", job_uuid[:8], e)
            else:
                raise RuntimeError(letzter or "Das Modell lieferte keine brauchbaren Folien")
            for s in neue:
                s.layout = layouts[s.id]
                slides[s.id] = s
            fertig += len(paket)
            geordnet = [slides[r.id] for r in outline.rows if r.id in slides]
            store.save_slides(user_id, job_uuid, geordnet)
            store.save_user_slides(user_id, job_uuid, geordnet)
            db.touch_job_heartbeat(job_uuid)
            db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "texte", current=fertig, total=len(offen)))
            # The finished batch is saved, whatever is left goes to the next stage.
            if clock.over() and n < len(pakete) - 1:
                raise StageContinue


def _fehlende_bilder(user_id, job_uuid, slides: list[Slide], analyse: Analyse, erzwungen: set[str]) -> list[tuple]:
    """(slide_id, slot, prompt, size) for every picture that is missing or asked for anew."""
    aus: list[tuple] = []
    for s in slides:
        layout = analyse.layout(s.layout) if s.layout is not None else None
        if layout is None:
            continue
        felder = layout.der_art("bild")
        for k, spec in enumerate(s.images[:len(felder)]):
            if s.id in erzwungen or not store.has_image(user_id, job_uuid, s.id, k):
                aus.append((s.id, k, spec.prompt or s.title, bild.bildgroesse(felder[k].width, felder[k].height)))
        if s.body and s.body.kind == "image" and layout.der_art("fliesstext"):
            feld = layout.der_art("fliesstext")[0]
            if s.id in erzwungen or not store.has_image(user_id, job_uuid, s.id, "body"):
                aus.append((s.id, "body", s.body.prompt or s.title, bild.bildgroesse(feld.width, feld.height)))
    return aus


def _bilder_erzeugen(job_uuid, user_id, style_text, fehlend: list[tuple], clock: StageClock, versuch: int,
                     final: bool) -> None:
    """Draws in parallel, keeps every finished picture, defers the rest to the next stage."""
    sperre = Lock()
    fertig = 0
    db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "bilder", current=0, total=len(fehlend)))

    def eins(auftrag) -> bool:
        nonlocal fertig
        if clock.over():
            return False
        assert_not_cancelled(job_uuid)
        if not still_mine(job_uuid, versuch):
            raise StageLost(job_uuid)
        sid, slot, prompt, size = auftrag
        try:
            data = bild.erzeuge(bild.prompt_fuer(style_text, prompt), size)
        except Exception as e:  # noqa: BLE001 - one missing picture must not stop the deck
            logger.warning("Präsentation {}: Bild {} {} fehlgeschlagen: {}", job_uuid[:8], sid, slot, e)
            with sperre:
                fertig += 1
            return True
        store.save_image(user_id, job_uuid, sid, slot, data)
        with sperre:
            fertig += 1
            db.touch_job_heartbeat(job_uuid)
            db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "bilder", current=fertig, total=len(fehlend)))
        return True

    with ThreadPoolExecutor(max_workers=PRAESENTATION_IMAGE_PARALLELISM) as pool:
        erledigt = list(pool.map(eins, fehlend))
    if not all(erledigt):
        raise StageContinue


def _bilder_laden(user_id, job_uuid, slides: list[Slide]) -> dict[str, bytes]:
    aus: dict[str, bytes] = {}
    for s in slides:
        for k in range(len(s.images)):
            data = store.get_image(user_id, job_uuid, s.id, k)
            if data:
                aus[bau.bild_schluessel(s.id, k)] = data
        if s.body and s.body.kind == "image":
            data = store.get_image(user_id, job_uuid, s.id, "body")
            if data:
                aus[bau.bild_schluessel(s.id, "body")] = data
    return aus


def _outline_angleichen(outline: Outline, slides: list[Slide]) -> Outline:
    """The outline follows the slides, so split slides get a row and deleted ones lose theirs."""
    alt = {r.id: r for r in outline.rows}
    rows = [alt.get(s.id) or OutlineRow(id=s.id, role=s.role, title=s.title, gist="") for s in slides]
    return Outline(title=outline.title, subtitle=outline.subtitle, rows=rows)
