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
    PRAESENTATION_BATCH, PRAESENTATION_IMAGE_PARALLELISM, PRAESENTATION_WRITE_PARALLELISM,
    STAGE_SOFT_TIME_LIMIT, STAGE_TIME_LIMIT,
)
from src.services import feature_router
from src.services.feature_provider_choices import binding_for
from src.services.text_map import Karte
from src.services.json_llm import call_json_llm
from src.services import sources as quellen
from src.services.job_recovery import attempt_failed, still_mine
from src.services.provider_slots import ProviderFull
from src.services.upstream_errors import is_upstream_busy
from src.storage import save_result_and_evict
from src.tasks._stage import StageClock, StageContinue, StageLost, continue_stage
from src.tasks.podcast_tasks._shared import JobCancelled, assert_not_cancelled
from src.utils.heartbeat import job_heartbeat

_VERSUCHE = 3
_DATEINAME = re.compile(r"[^\w\s\-]", re.U)


def _fortschritt(final: bool, step: str, **extra) -> dict:
    """One progress snapshot, tagged with the finalize intent so a resume never loses it."""
    return {"step": step, "final": final, **extra}


# Lowest priority in its queue, outlines and scripts of a few minutes pass the stages of ten minutes.
@celery_app.task(bind=True, name="praesentation.build", queue="long", acks_late=True, priority=9,
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
        _wuensche_verorten(job_uuid, user_id, params, quellenliste, outline, offen)
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
                            t("praesentation.aiNotice", params.language), datum=bau.datum_text(params.language),
                            vortragend=params.presenter)
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
        attempt_failed(job_uuid, t("praesentation.buildFailed", locale), busy=is_upstream_busy(e))
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


def _wuensche_verorten(job_uuid, user_id, params, quellenliste, outline: Outline, offen) -> None:
    """A slide added by hand gets its passages before it is written, without them it would be made up.

    When the material says nothing on the wish, the slide takes a subject the deck still lacks.
    """
    from src.services import text_map as tm

    wuensche = [r for r in offen if r.wunsch and not r.stellen]
    if not wuensche:
        return
    llm = feature_router.make_llm_client(binding_for("chat", params.llm_provider_id))
    karte = Karte(quellenliste)
    g = (tm.grundlage_aus_dict(store.load_map(user_id, job_uuid), karte)
         or tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[]))
    for r in wuensche:
        assert_not_cancelled(job_uuid)
        nachrichten = gliederung.einzel_messages(g.material, g.modus, params, r.wunsch, outline.rows)
        try:
            antwort = call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""
            abgedeckt, titel, gist, stellen = gliederung.parse_einzel(antwort, lambda refs: g.stellen(refs, karte))
        except gliederung.Unusable as e:
            logger.warning("Präsentation {}: neue Folie {} nicht verortet: {}", job_uuid[:8], r.id, e)
            continue
        # A title the person typed stays when the material carries it, else the new subject names it.
        if not r.title or not abgedeckt:
            r.title = titel
        r.gist, r.stellen, r.wunsch = gist, stellen, ""
        logger.info("Präsentation {}: neue Folie {} auf {} Stellen{}", job_uuid[:8], r.id, len(stellen),
                    "" if abgedeckt else ", Wunsch nicht im Material, eigenes Thema")
    store.save_user_outline(user_id, job_uuid, outline)


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
    llm = feature_router.make_llm_client(binding_for("chat", params.llm_provider_id))
    karte = Karte(quellenliste)
    eigen = _eigenes_material(user_id, job_uuid, offen, erzwungen_text)
    # A slide with its own material goes alone, it must not share a call with the run's snapshot.
    rest = [r for r in offen if r.id not in eigen]
    pakete = [[r] for r in offen if r.id in eigen]
    pakete += [rest[i:i + PRAESENTATION_BATCH] for i in range(0, len(rest), PRAESENTATION_BATCH)]
    fertig = 0
    db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "texte", current=0, total=len(offen)))

    # Planned over the whole deck, the batches run at once and cannot see each other's cards.
    alle_formen = {r.id: vorlage.form_fuer(analyse.layout(layouts[r.id]), analyse) for r in outline.rows if r.id in layouts}
    karten = folien.karten_folien(outline.rows, alle_formen)

    def schreibe(paket: list[OutlineRow]) -> list[Slide]:
        assert_not_cancelled(job_uuid)
        formen = {r.id: alle_formen[r.id] if r.id in karten else folien.ohne_karten(alle_formen[r.id]) for r in paket}
        # A slide with material of its own keeps it, the rest get their passages.
        if paket[0].id in eigen:
            nachrichten = folien.build_messages(eigen[paket[0].id], params, paket, formen)
        else:
            je_folie = folien.material_je_folie(paket, karte, outline.rows)
            nachrichten = folien.build_messages(quelle, params, paket, formen, je_folie or None)
        letzter = ""
        for _ in range(_VERSUCHE):
            antwort = call_json_llm(llm, nachrichten, endpoint="praesentation").choices[0].message.content or ""
            try:
                neue = folien.parse_answer(antwort, paket, formen, params.notes)
            except gliederung.Unusable as e:
                letzter = str(e)
                logger.warning("Präsentation {}: Folienpaket unbrauchbar: {}", job_uuid[:8], e)
                continue
            return _nachfassen(llm, nachrichten, antwort, neue, paket, formen, params.notes, job_uuid)
        raise RuntimeError(letzter or "Das Modell lieferte keine brauchbaren Folien")

    # A few batches at once, each wave saved before the next, so a stage never loses a finished one.
    wellen = [pakete[i:i + PRAESENTATION_WRITE_PARALLELISM]
              for i in range(0, len(pakete), PRAESENTATION_WRITE_PARALLELISM)]
    with job_heartbeat(job_uuid):
        for n, welle in enumerate(wellen):
            with ThreadPoolExecutor(max_workers=len(welle)) as pool:
                ergebnisse = list(pool.map(schreibe, welle))
            for neue in ergebnisse:
                for s in neue:
                    s.layout = layouts[s.id]
                    slides[s.id] = s
                fertig += len(neue)
            geordnet = [slides[r.id] for r in outline.rows if r.id in slides]
            store.save_slides(user_id, job_uuid, geordnet)
            store.save_user_slides(user_id, job_uuid, geordnet)
            db.touch_job_heartbeat(job_uuid)
            db.update_job_status(job_uuid, "running", progress=_fortschritt(final, "texte", current=fertig, total=len(offen)))
            # The finished wave is saved, whatever is left goes to the next stage.
            if clock.over() and n < len(wellen) - 1:
                raise StageContinue


def _nachfassen(llm, nachrichten, antwort, neue: list[Slide], paket: list[OutlineRow], formen: dict,
                notes: bool, job_uuid: str) -> list[Slide]:
    """Thin slides are asked for once more, the second version wins only when it carries more points."""
    duenn = folien.zu_duenn(neue, formen)
    if not duenn:
        return neue
    logger.info("Präsentation {}: zu wenige Punkte, frage nach: {}", job_uuid[:8], duenn)
    try:
        roh = call_json_llm(llm, folien.nachfrage(nachrichten, antwort, duenn),
                            endpoint="praesentation").choices[0].message.content or ""
        zweite = {s.id: s for s in folien.parse_answer(roh, [r for r in paket if r.id in duenn], formen, notes)}
    except Exception as e:  # noqa: BLE001 - the first version is still a usable slide
        logger.warning("Präsentation {}: Nachfrage gescheitert, erste Fassung bleibt: {}", job_uuid[:8], e)
        return neue
    return [zweite[s.id] if s.id in zweite and folien.punkte(zweite[s.id]) > folien.punkte(s) else s for s in neue]


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
        except ProviderFull:
            # Only our own line was full, the picture waits for the next stage instead of missing.
            logger.info("Präsentation {}: Bild {} {} wartet auf einen Platz", job_uuid[:8], sid, slot)
            return False
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
