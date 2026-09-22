"""Every intermediate state of a run as a file in the job folder, the user's version wins."""

from __future__ import annotations

import json
import re


from src.features.praesentation import vorlage
from src.features.praesentation.schemas import Outline, PraesentationParams, Slide
from src.storage import (
    get_job_file, job_file_exists, job_prefix, save_job_file,
)

MAP_FILE = "grundlage.json"
PARAMS_FILE = "params.json"
TEMPLATE_FILE = "template.pptx"
TEMPLATE_META_FILE = "template_meta.json"
OUTLINE_FILE = "outline.json"
USER_OUTLINE_FILE = "user_outline.json"
SLIDES_FILE = "slides.json"
USER_SLIDES_FILE = "user_slides.json"
DECK_FILE = "deck.pptx"
SLIDE_SOURCE_DIR = "slide_source"
_ID = re.compile(r"^s(\d+)$")


def image_name(slide_id: str, slot: int | str) -> str:
    return f"images/{slide_id}_{slot}.png"


def preview_name(slide_id: str) -> str:
    return f"preview/{slide_id}.png"


def slide_source_name(slide_id: str) -> str:
    return f"{SLIDE_SOURCE_DIR}/{slide_id}.txt"


def deck_key(user_id: int, job_uuid: str) -> str:
    return f"{job_prefix(user_id, job_uuid)}/{DECK_FILE}"


def _read_json(user_id: int, job_uuid: str, name: str):
    try:
        return json.loads(get_job_file(user_id, job_uuid, name))
    except Exception:
        return None


def _write_json(user_id: int, job_uuid: str, name: str, data) -> None:
    save_job_file(user_id, job_uuid, name, json.dumps(data, ensure_ascii=False).encode())


def save_slide_source(user_id: int, job_uuid: str, slide_id: str, text: str) -> None:
    """The material of one slide, searched for it alone instead of taken from the run's snapshot."""
    save_job_file(user_id, job_uuid, slide_source_name(slide_id), text.encode())


def load_slide_source(user_id: int, job_uuid: str, slide_id: str) -> str:
    try:
        return get_job_file(user_id, job_uuid, slide_source_name(slide_id)).decode()
    except Exception:
        return ""


def clear_slide_source(user_id: int, job_uuid: str, slide_id: str) -> None:
    """Emptied rather than deleted, so both storage backends behave the same."""
    save_slide_source(user_id, job_uuid, slide_id, "")


def save_params(user_id: int, job_uuid: str, params: PraesentationParams) -> None:
    _write_json(user_id, job_uuid, PARAMS_FILE, params.model_dump())


def load_params(user_id: int, job_uuid: str) -> PraesentationParams | None:
    data = _read_json(user_id, job_uuid, PARAMS_FILE)
    return PraesentationParams(**data) if isinstance(data, dict) else None


def save_template(user_id: int, job_uuid: str, data: bytes) -> None:
    save_job_file(user_id, job_uuid, TEMPLATE_FILE, data)


def load_template(user_id: int, job_uuid: str) -> bytes | None:
    try:
        return get_job_file(user_id, job_uuid, TEMPLATE_FILE)
    except Exception:
        return None


def save_template_meta(user_id: int, job_uuid: str, analyse: vorlage.Analyse) -> None:
    _write_json(user_id, job_uuid, TEMPLATE_META_FILE, vorlage.als_dict(analyse))


def load_template_meta(user_id: int, job_uuid: str) -> vorlage.Analyse | None:
    data = _read_json(user_id, job_uuid, TEMPLATE_META_FILE)
    return vorlage.aus_dict(data) if isinstance(data, dict) else None


def save_outline(user_id: int, job_uuid: str, outline: Outline) -> None:
    _write_json(user_id, job_uuid, OUTLINE_FILE, outline.model_dump())


def save_user_outline(user_id: int, job_uuid: str, outline: Outline) -> None:
    _write_json(user_id, job_uuid, USER_OUTLINE_FILE, outline.model_dump())


def load_outline(user_id: int, job_uuid: str) -> Outline | None:
    for name in (USER_OUTLINE_FILE, OUTLINE_FILE):
        data = _read_json(user_id, job_uuid, name)
        if isinstance(data, dict):
            return Outline(**data)
    return None


def save_slides(user_id: int, job_uuid: str, slides: list[Slide]) -> None:
    _write_json(user_id, job_uuid, SLIDES_FILE, [s.model_dump() for s in slides])


def save_user_slides(user_id: int, job_uuid: str, slides: list[Slide]) -> None:
    _write_json(user_id, job_uuid, USER_SLIDES_FILE, [s.model_dump() for s in slides])


def load_slides(user_id: int, job_uuid: str) -> list[Slide]:
    for name in (USER_SLIDES_FILE, SLIDES_FILE):
        data = _read_json(user_id, job_uuid, name)
        if isinstance(data, list):
            return [Slide(**s) for s in data]
    return []


def save_image(user_id: int, job_uuid: str, slide_id: str, slot: int | str, data: bytes) -> None:
    save_job_file(user_id, job_uuid, image_name(slide_id, slot), data)


def get_image(user_id: int, job_uuid: str, slide_id: str, slot: int | str) -> bytes | None:
    try:
        return get_job_file(user_id, job_uuid, image_name(slide_id, slot))
    except Exception:
        return None


def has_image(user_id: int, job_uuid: str, slide_id: str, slot: int | str) -> bool:
    return job_file_exists(user_id, job_uuid, image_name(slide_id, slot))


def save_deck(user_id: int, job_uuid: str, data: bytes) -> str:
    """Returns the storage helper's own path/key, the value a job's result_path must hold."""
    return save_job_file(user_id, job_uuid, DECK_FILE, data)


def get_deck(user_id: int, job_uuid: str) -> bytes | None:
    try:
        return get_job_file(user_id, job_uuid, DECK_FILE)
    except Exception:
        return None


def has_deck(user_id: int, job_uuid: str) -> bool:
    return job_file_exists(user_id, job_uuid, DECK_FILE)


def save_preview(user_id: int, job_uuid: str, slide_id: str, data: bytes) -> None:
    save_job_file(user_id, job_uuid, preview_name(slide_id), data)


def get_preview(user_id: int, job_uuid: str, slide_id: str) -> bytes | None:
    try:
        return get_job_file(user_id, job_uuid, preview_name(slide_id))
    except Exception:
        return None


def has_preview(user_id: int, job_uuid: str, slide_id: str) -> bool:
    return job_file_exists(user_id, job_uuid, preview_name(slide_id))


def neue_id(ids: set[str]) -> str:
    """The next free slide id, counting past the highest one ever used."""
    hoechste = max((int(m.group(1)) for i in ids if (m := _ID.match(i))), default=0)
    return f"s{hoechste + 1}"


def save_map(user_id: int, job_uuid: str, daten: dict) -> None:
    """Die Planungsgrundlage des Laufs, damit eine neue Etappe die Themen nicht neu bezahlt."""
    _write_json(user_id, job_uuid, MAP_FILE, daten)


def load_map(user_id: int, job_uuid: str) -> dict | None:
    roh = _read_json(user_id, job_uuid, MAP_FILE)
    return roh if isinstance(roh, dict) else None
