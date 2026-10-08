"""Numbers about a job run, phase by phase into the job's meta.json."""

import json
import time
from contextlib import contextmanager
from pathlib import Path

from loguru import logger

from src.storage import load_result_meta, save_result_meta


def notiere(user_id: int, job_uuid: str, phase: str, werte: dict) -> None:
    """Appends the values of a phase under stats without losing existing ones."""
    try:
        meta = load_result_meta(user_id, job_uuid) or {}
        stats = dict(meta.get("stats") or {})
        stats[phase] = werte
        save_result_meta(user_id, job_uuid, {**meta, "stats": stats})
    except Exception as e:
        logger.warning("Statistik {} fuer {} nicht gespeichert: {}", phase, job_uuid, e)


def wer_antwortete(feature: str, provider_id: int | None = None) -> str:
    """The providers that really answered, fallback included, the chosen one when no call went through the door."""
    from src.services import provider_transport

    namen = provider_transport.answered()
    return ", ".join(namen) if namen else route_kennung(feature, provider_id)["anbieter"]


def anbieter_name(provider_id: int | None) -> str:
    """The provider's name for the info under a result, empty when it cannot be read."""
    from src import database as db

    try:
        return (db.get_provider(provider_id) or {}).get("name") or "" if provider_id else ""
    except Exception as e:
        logger.warning("Anbieter {} nicht lesbar: {}", provider_id, e)
        return ""


def angaben_merken(user_id: int, job_uuid: str, angaben: dict) -> None:
    """Keeps what a result was made with next to it, for the info under the result."""
    try:
        meta = load_result_meta(user_id, job_uuid) or {}
        gefuellt = {k: v for k, v in angaben.items() if v not in (None, "")}
        save_result_meta(user_id, job_uuid, {**meta, "angaben": gefuellt})
    except Exception as e:
        logger.warning("Angaben fuer {} nicht gespeichert: {}", job_uuid, e)


def _job_text(user_id: int, job_uuid: str, name: str) -> str:
    """A text file from the job folder, empty when it is not there."""
    from src.storage import get_job_file

    try:
        return get_job_file(user_id, job_uuid, name).decode("utf-8")
    except Exception:
        return ""


def angaben_lesen(job: dict) -> dict:
    """What a result was made with, older jobs fill the gaps from the files they kept."""
    from src.features.summary.models import INSTRUCTIONS_FILE

    uid, uuid, tool = job["user_id"], job["job_uuid"], job["tool"]
    angaben = dict((load_result_meta(uid, uuid) or {}).get("angaben") or {})
    if tool == "tts":
        params = json.loads(_job_text(uid, uuid, "tts_params.json") or "{}")
        if params.get("provider_id"):
            angaben.setdefault("anbieter", anbieter_name(params["provider_id"]))
            if params.get("voice_id") and not angaben.get("sprache"):
                from src.dependencies import _voice_language_for
                angaben["sprache"] = _voice_language_for(params["provider_id"], params["voice_id"])
        angaben.setdefault("stimme", params.get("voice_label"))
    elif tool == "summary":
        params = json.loads(_job_text(uid, uuid, "summary_params.json") or "{}")
        angaben.setdefault("vorlage", params.get("template_slug"))
        if params.get("provider_id"):
            angaben.setdefault("anbieter", anbieter_name(params["provider_id"]))
        angaben.setdefault("anweisung", _job_text(uid, uuid, INSTRUCTIONS_FILE).strip())
    elif tool == "pages":
        angaben.setdefault("anweisung", _job_text(uid, uuid, INSTRUCTIONS_FILE).strip())
    elif tool == "podcast":
        from src.features.podcast import store as podcast_store
        from src.features.podcast.angaben import angaben as podcast_angaben

        params = podcast_store.load_params(uid, uuid)
        if params:
            if not angaben:
                angaben = podcast_angaben(params, podcast_store.load_pin(uid, uuid))
            angaben.setdefault("anweisung", params.instructions.strip())
        # The script's provider is already measured for the admins, the info reuses it.
        skript = ((load_result_meta(uid, uuid) or {}).get("stats") or {}).get("skript") or {}
        angaben.setdefault("textanbieter", skript.get("anbieter"))
    elif tool == "praesentation":
        from src.features.praesentation import store as praesentation_store
        from src.features.praesentation.angaben import angaben as praesentation_angaben

        params = praesentation_store.load_params(uid, uuid)
        if params:
            for k, v in praesentation_angaben(params).items():
                angaben.setdefault(k, v)
    elif tool in ("screencast_translate", "screencast_render"):
        # The render keeps the voice that really spoke, after a fallback too.
        params = json.loads(_job_text(uid, uuid, "render_params.json") or "{}")
        pid, stimme = params.get("provider_id"), params.get("voice_id") or ""
        if pid:
            from src.dependencies import _voice_language_for
            from src.services.tts_job_provider import voice_name

            angaben.setdefault("anbieter", anbieter_name(pid))
            # Voices that speak every language have none, there the target of the translation tells.
            ziel = ((load_result_meta(uid, uuid) or {}).get("target_lang") or "").split("-")[0].lower()
            angaben.setdefault("sprache", _voice_language_for(pid, stimme) or ziel)
            angaben.setdefault("stimme", params.get("voice_label") or (voice_name(pid, stimme) if stimme else ""))
    elif tool in ("image_generate", "image_edit", "image_analyze"):
        # Pictures keep their settings at the top of the meta, older ones without the provider.
        meta = load_result_meta(uid, uuid) or {}
        for k in ("anbieter", "stil", "format", "qualitaet", "groesse", "aufgabe", "frage"):
            angaben.setdefault(k, meta.get(k))
        if tool != "image_analyze":
            angaben.setdefault("prompt", meta.get("beschreibung"))
    elif tool == "transcription":
        # The result's extension tells the format, named like the choice on the page.
        endung = Path(job.get("result_filename") or "").suffix.lstrip(".")
        angaben.setdefault("format", "text" if endung == "txt" else endung)
    return {k: v for k, v in angaben.items() if v not in (None, "")}


@contextmanager
def messe_vorab(werte: dict):
    """Measures a phase that runs before the job exists, ``notiere`` records it afterwards."""
    start = time.monotonic()
    try:
        yield werte
    except BaseException as e:
        werte["fehler"] = str(e)
        raise
    finally:
        werte["dauer_s"] = round(time.monotonic() - start, 2)


@contextmanager
def messe(user_id: int, job_uuid: str, phase: str):
    """Measures the phase duration and records it, even when it fails."""
    werte: dict = {}
    try:
        with messe_vorab(werte):
            yield werte
    finally:
        notiere(user_id, job_uuid, phase, werte)


def anbieter_und_modell(provider_id: int, feature: str) -> dict:
    """Name of the provider and the model the route uses for it."""
    from src import database as db
    from src.services import own_tts

    provider = db.get_provider(provider_id) or {}
    # An own interface speaks with its fixed model, the admin route does not apply to it.
    if own_tts.is_own(provider):
        return {"anbieter": provider.get("name") or "", "modell": own_tts.model_for(provider), "route": feature}
    route = db.get_route(feature) or {}
    je_anbieter = route.get("provider_models") or {}
    return {
        "anbieter": provider.get("name") or "",
        "modell": je_anbieter.get(str(provider_id)) or route.get("model_name") or "",
        "route": feature,
    }


def anbieter_und_modelle(provider_ids: list[int], feature: str) -> dict:
    """Like ``anbieter_und_modell``, but for a run that spreads over several providers."""
    einzeln = [anbieter_und_modell(pid, feature) for pid in dict.fromkeys(provider_ids)]

    def verbinde(schluessel: str) -> str:
        return ", ".join(dict.fromkeys(e[schluessel] for e in einzeln if e[schluessel]))

    return {"anbieter": verbinde("anbieter"), "modell": verbinde("modell"), "route": feature}


def route_kennung(feature: str, provider_id: int | None = None) -> dict:
    """Provider and model a run used, the admin route unless a provider was chosen."""
    from src.services import feature_provider_choices

    try:
        binding = feature_provider_choices.binding_for(feature, provider_id)
    except Exception as e:
        logger.warning("Route {} nicht aufloesbar: {}", feature, e)
        return {"anbieter": "", "modell": "", "route": feature}
    return {
        "anbieter": (binding.provider or {}).get("name") or "",
        "modell": binding.model or "",
        "route": feature,
    }


def zeichen_zahlen(scripts: list[str]) -> dict:
    """How much text the voicing has to speak, spread over the slides."""
    laengen = [len(s.strip()) for s in scripts]
    return {
        "folien": len(scripts),
        "zeichen": sum(laengen),
        "laengste_folie_zeichen": max(laengen, default=0),
        "leere_folien": sum(1 for laenge in laengen if laenge == 0),
    }
