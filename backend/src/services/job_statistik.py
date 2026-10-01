"""Numbers about a job run, phase by phase into the job's meta.json."""

import time
from contextlib import contextmanager

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

    provider = db.get_provider(provider_id) or {}
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
