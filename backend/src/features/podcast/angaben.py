"""What a podcast was made with, for the info next to the result."""

from src import database as db
from src.features.podcast import store
from src.features.podcast.schemas import PodcastParams
from src.services import tts_job_provider


def angaben(params: PodcastParams, pin: dict | None) -> dict:
    """Language, material and who speaks with which role and voice, providers as they really speak."""
    besetzung, anbieter = [], []
    for person in params.persons:
        pid, stimme = store.pinned_voice(pin, person.provider_id or params.provider_id, person.voice_id)
        name = (db.get_provider(pid) or {}).get("name") or ""
        if name and name not in anbieter:
            anbieter.append(name)
        besetzung.append({"name": person.name, "rolle": person.role,
                          "stimme": tts_job_provider.voice_name(pid, stimme) if stimme else ""})
    return {"anbieter": ", ".join(anbieter), "sprache": params.language,
            "material": params.source_label, "besetzung": besetzung}
