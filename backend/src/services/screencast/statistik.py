"""Zahlen zum Screencast-Lauf, phasenweise in die meta.json des Jobs."""

import time
from contextlib import contextmanager

from loguru import logger

from src.storage import load_result_meta, save_result_meta


def notiere(user_id: int, job_uuid: str, phase: str, werte: dict) -> None:
    """Haengt die Werte einer Phase unter stats an, ohne Bestehendes zu verlieren."""
    try:
        meta = load_result_meta(user_id, job_uuid) or {}
        stats = dict(meta.get("stats") or {})
        stats[phase] = werte
        save_result_meta(user_id, job_uuid, {**meta, "stats": stats})
    except Exception as e:
        logger.warning("Statistik {} fuer {} nicht gespeichert: {}", phase, job_uuid, e)


@contextmanager
def messe(user_id: int, job_uuid: str, phase: str):
    """Misst die Dauer der Phase und schreibt sie mit, auch wenn sie scheitert."""
    werte: dict = {}
    start = time.monotonic()
    try:
        yield werte
    except BaseException as e:
        werte["fehler"] = str(e)
        raise
    finally:
        werte["dauer_s"] = round(time.monotonic() - start, 2)
        notiere(user_id, job_uuid, phase, werte)


def anbieter_und_modell(provider_id: int, feature: str) -> dict:
    """Name des Anbieters und das Modell, das die Route fuer ihn benutzt."""
    from src import database as db

    provider = db.get_provider(provider_id) or {}
    route = db.get_route(feature) or {}
    je_anbieter = route.get("provider_models") or {}
    return {
        "anbieter": provider.get("name") or "",
        "modell": je_anbieter.get(str(provider_id)) or route.get("model_name") or "",
        "route": feature,
    }


def route_kennung(feature: str) -> dict:
    """Anbieter und Modell einer Route ohne eigene Anbieterwahl, etwa die Skripte."""
    from src.services import feature_router

    try:
        binding = feature_router.resolve(feature)
    except Exception as e:
        logger.warning("Route {} nicht aufloesbar: {}", feature, e)
        return {"anbieter": "", "modell": "", "route": feature}
    return {
        "anbieter": (binding.provider or {}).get("name") or "",
        "modell": binding.model or "",
        "route": feature,
    }


def zeichen_zahlen(scripts: list[str]) -> dict:
    """Wie viel Text die Vertonung zu sprechen hat, verteilt auf die Folien."""
    laengen = [len(s.strip()) for s in scripts]
    return {
        "folien": len(scripts),
        "zeichen": sum(laengen),
        "laengste_folie_zeichen": max(laengen, default=0),
        "leere_folien": sum(1 for laenge in laengen if laenge == 0),
    }
