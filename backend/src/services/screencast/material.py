"""Extra documents for the scripts: every slide gets the passages of the material that belong to it."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from loguru import logger

from src.limits import SCREENCAST_MATERIAL_PER_SLIDE, SCREENCAST_MATERIAL_SLIDES_PER_CALL
from src.services import sources as quellen
from src.services import text_map as tm
from src.services.job_files import parse_job_json, read_job_text, write_job_text
from src.storage import delete_job_file

FOLIEN_MATERIAL = "folien_material.json"
KARTE = "material_karte.json"
_ZWECK = "spoken scripts that explain the slides of a lecture"
_FOLIENTEXT = 400


def _fenster() -> int:
    """The measured window of the chat model, 0 when there is none."""
    from src.services import feature_router
    from src.services.model_limits import ensure_profile

    try:
        binding = feature_router.resolve("chat")
        profil = ensure_profile(binding.provider, binding.model or "")
        return profil.window_tokens if profil.measured else 0
    except Exception as e:  # noqa: BLE001 - without a measurement the smallest allowed window applies
        logger.warning("Screencast: Modell nicht vermessbar ({})", e)
        return 0


def _sauber(text: str) -> str:
    """The separators of the batch format must not appear inside the material."""
    return text.replace("|||", "| | |").replace("===", "= = =")


def nachrichten(material: str, modus: str, folien: list[tuple[int, str]]) -> list[dict]:
    """One assignment call: the material and a group of slides, answered with passage numbers."""
    liste = "\n".join(f"[Slide {nr}] {' '.join(text.split())[:_FOLIENTEXT] or '(no text)'}"
                      for nr, text in folien)
    system = (
        "You prepare the scripts of a narrated slide video for a university lecture. "
        "Besides the slides the lecturer provides additional material. For every slide "
        "listed below, name the parts of the material that explain, deepen or give examples "
        "for exactly what that slide says. A slide with nothing matching in the material "
        "gets an empty list. Different slides may use the same parts.\n"
        + tm.hinweis(modus) + "\n"
        'Answer with one JSON object only: {"slides": [{"slide": 1, "refs": [3, "10-12"]}]}'
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"/no_think\nMATERIAL:\n{material}\n\nSLIDES:\n{liste}"}]


def parse(raw: str | None, g: tm.Grundlage, karte: tm.Karte, erlaubt: set[int]) -> dict[int, list[int]]:
    """The passage numbers per slide number out of one answer."""
    daten = tm._json_objekt(raw)
    eintraege = daten.get("slides") if isinstance(daten, dict) else None
    aus: dict[int, list[int]] = {}
    for e in eintraege if isinstance(eintraege, list) else []:
        if not isinstance(e, dict):
            continue
        try:
            nr = int(e.get("slide"))
        except (TypeError, ValueError):
            continue
        if nr in erlaubt:
            aus[nr] = g.stellen(e.get(tm.REFS), karte)
    return aus


def _grundlage(user_id: int, job_uuid: str, karte: tm.Karte, llm, sprache: str) -> tm.Grundlage:
    gemerkt = tm.grundlage_aus_dict(
        parse_job_json(job_uuid, KARTE, read_job_text(user_id, job_uuid, KARTE), None), karte)
    if gemerkt:
        return gemerkt
    g = tm.grundlage(karte, _fenster(), language=sprache, zweck=_ZWECK, frage=_frage(llm))
    write_job_text(user_id, job_uuid, KARTE, json.dumps(tm.grundlage_als_dict(g), ensure_ascii=False))
    return g


def _frage(llm):
    from src.services.json_llm import call_json_llm

    def _alle(liste: list[list[dict]]) -> list[str | None]:
        def _eine(n):
            try:
                return call_json_llm(llm, n, endpoint="screencast").choices[0].message.content
            except Exception as e:  # noqa: BLE001 - a lost call costs its slides their material, not the run
                logger.warning("Screencast: Materialaufruf gescheitert ({})", e)
                return None
        with ThreadPoolExecutor(max_workers=max(1, len(liste))) as pool:
            return list(pool.map(_eine, liste))
    return _alle


def material_je_folie(user_id: int, job_uuid: str, slide_texts: list[str], *,
                      sprache: str = "English", llm=None) -> list[str] | None:
    """The passages for every slide, None when the job carries no extra material."""
    quellenliste = quellen.load_sources(user_id, job_uuid)
    if not quellenliste:
        return None
    karte = tm.Karte(quellenliste)
    if not len(karte):
        return None
    if llm is None:
        from src.services import feature_router
        llm = feature_router.make_llm_client(feature_router.resolve("chat"))

    g = _grundlage(user_id, job_uuid, karte, llm, sprache)
    folien = [(i + 1, text) for i, text in enumerate(slide_texts)]
    gruppen = [folien[s:s + SCREENCAST_MATERIAL_SLIDES_PER_CALL]
               for s in range(0, len(folien), SCREENCAST_MATERIAL_SLIDES_PER_CALL)]
    antworten = _frage(llm)([nachrichten(g.material, g.modus, gr) for gr in gruppen])
    stellen: dict[int, list[int]] = {}
    for antwort, gruppe in zip(antworten, gruppen):
        stellen.update(parse(antwort, g, karte, {nr for nr, _ in gruppe}))

    material = [
        _sauber(karte.passagen(stellen[nr], budget=SCREENCAST_MATERIAL_PER_SLIDE)) if stellen.get(nr) else ""
        for nr, _ in folien
    ]
    write_job_text(user_id, job_uuid, FOLIEN_MATERIAL, json.dumps(material, ensure_ascii=False))
    logger.info("Screencast {}: Material fuer {} von {} Folien, {} Stellen, ueber {}",
                job_uuid[:8], sum(1 for m in material if m), len(material), len(karte),
                "den ganzen Text" if g.modus == tm.STELLEN else f"{len(g.themen)} Themen")
    return material


def material_einer_folie(user_id: int, job_uuid: str, index: int) -> str:
    """What the last generation handed this slide, empty when there was nothing."""
    liste = parse_job_json(job_uuid, FOLIEN_MATERIAL, read_job_text(user_id, job_uuid, FOLIEN_MATERIAL), [])
    if isinstance(liste, list) and 0 <= index < len(liste) and isinstance(liste[index], str):
        return liste[index]
    return ""


def verwerfen(user_id: int, job_uuid: str) -> None:
    """New or no material, so the old map and assignment no longer hold."""
    for name in (KARTE, FOLIEN_MATERIAL):
        try:
            delete_job_file(user_id, job_uuid, name)
        except Exception:  # noqa: BLE001 - a file that is not there is already gone
            pass
