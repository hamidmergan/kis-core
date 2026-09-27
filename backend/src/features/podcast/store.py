"""Every file the podcast tool keeps in the job folder, in one place."""

import json
import re


from src.features.podcast.schemas import Line, PodcastParams
from src.storage import delete_job_file, get_job_file, is_missing, job_file_exists, save_job_file

PARAMS_FILE = "params.json"
SCRIPT_FILE = "script.json"
USER_SCRIPT_FILE = "user_script.json"
DRAFT_FILE = "entwurf.json"
VOICED_FILE = "voiced.json"
TRANSCRIPT_FILE = "transcript.txt"
PIN_FILE = "tts_pin.json"

_ID = re.compile(r"^b[0-9]{1,4}$")


def audio_name(line_id: str) -> str:
    """One finished contribution, named by its line so a reorder cannot mix them up."""
    return f"audio/{line_id}.mp3"


def _read_json(user_id: int, job_uuid: str, name: str):
    try:
        return json.loads(get_job_file(user_id, job_uuid, name))
    except Exception:
        return None


def _write_json(user_id: int, job_uuid: str, name: str, data) -> None:
    save_job_file(user_id, job_uuid, name, json.dumps(data, ensure_ascii=False).encode())


def save_params(user_id: int, job_uuid: str, params: PodcastParams) -> None:
    _write_json(user_id, job_uuid, PARAMS_FILE, params.model_dump())


def load_params(user_id: int, job_uuid: str) -> PodcastParams | None:
    raw = _read_json(user_id, job_uuid, PARAMS_FILE)
    return PodcastParams(**raw) if raw else None


def save_script(user_id: int, job_uuid: str, lines: list[Line]) -> None:
    """What the model wrote, kept apart so a person can always fall back to it."""
    _write_json(user_id, job_uuid, SCRIPT_FILE, [l.model_dump() for l in lines])


def save_draft(user_id: int, job_uuid: str, lines: list[Line]) -> None:
    """The parts written so far, so the page can show them while the rest is being written."""
    _write_json(user_id, job_uuid, DRAFT_FILE, [l.model_dump() for l in lines])


def load_draft(user_id: int, job_uuid: str) -> list[Line]:
    raw = _read_json(user_id, job_uuid, DRAFT_FILE)
    return [Line(**item) for item in raw] if isinstance(raw, list) else []


def save_user_script(user_id: int, job_uuid: str, lines: list[Line]) -> None:
    _write_json(user_id, job_uuid, USER_SCRIPT_FILE, [l.model_dump() for l in lines])


def load_lines(user_id: int, job_uuid: str) -> list[Line]:
    """The checked script wins, the model's own is the fallback."""
    for name in (USER_SCRIPT_FILE, SCRIPT_FILE):
        raw = _read_json(user_id, job_uuid, name)
        if raw:
            return [Line(**item) for item in raw]
    return []


def next_ids(lines: list[Line]) -> list[Line]:
    """The backend owns the ids, a line without one gets the next free number."""
    used = {l.id for l in lines if _ID.match(l.id or "")}
    nummer = 0
    out: list[Line] = []
    for line in lines:
        if _ID.match(line.id or "") and line.id not in {o.id for o in out}:
            out.append(line)
            continue
        while f"b{nummer}" in used:
            nummer += 1
        neu = f"b{nummer}"
        used.add(neu)
        out.append(line.model_copy(update={"id": neu}))
    return out


def load_voiced(user_id: int, job_uuid: str) -> dict[str, dict]:
    """Per line what was voiced, so only a changed one is spoken again."""
    return _read_json(user_id, job_uuid, VOICED_FILE) or {}


def save_voiced(user_id: int, job_uuid: str, voiced: dict[str, dict]) -> None:
    _write_json(user_id, job_uuid, VOICED_FILE, voiced)


def fingerprint(line: Line, voice_id: str, speed: float, provider_id: int = 0) -> dict:
    """What makes a contribution sound different, nothing else."""
    return {"text": line.text.strip(), "voice_id": voice_id, "speed": round(speed, 2),
            "provider_id": provider_id}


def needs_voice(line: Line, voiced: dict[str, dict], voice_id: str, speed: float,
                provider_id: int = 0) -> bool:
    return voiced.get(line.id) != fingerprint(line, voice_id, speed, provider_id)


def save_pin(user_id: int, job_uuid: str, pin: dict) -> None:
    """Provider and voice of every chosen voice, fixed once at the start of a voicing run."""
    _write_json(user_id, job_uuid, PIN_FILE, pin)


def load_pin(user_id: int, job_uuid: str) -> dict | None:
    """None only when no pin exists, a failed read raises so the stage cannot pick anew."""
    try:
        raw = get_job_file(user_id, job_uuid, PIN_FILE)
    except Exception as e:
        if is_missing(e):
            return None
        raise
    try:
        pin = json.loads(raw)
    except ValueError:
        # A broken file never heals, so it counts as absent instead of blocking the job for good.
        return None
    return pin if isinstance(pin, dict) else None


def pin_covers(pin: dict | None, params: PodcastParams) -> bool:
    """Whether the pin still has an entry for every chosen voice of the cast."""
    stimmen = (pin or {}).get("voices") or {}
    return bool(stimmen) and all(
        pin_key(p.provider_id or params.provider_id, p.voice_id) in stimmen
        for p in params.persons if p.voice_id)


def delete_pin(user_id: int, job_uuid: str) -> None:
    """A new voicing run decides the provider anew."""
    delete_job_file(user_id, job_uuid, PIN_FILE)


def pin_key(provider_id: int, voice_id: str) -> str:
    return f"{provider_id}/{voice_id}"


def pinned_voice(pin: dict | None, provider_id: int, voice_id: str) -> tuple[int, str]:
    """Who really speaks for a chosen voice, the chosen one itself when nothing is fixed."""
    eintrag = ((pin or {}).get("voices") or {}).get(pin_key(provider_id, voice_id))
    if not eintrag:
        return provider_id, voice_id
    return int(eintrag["provider_id"]), str(eintrag["voice_id"])


def save_line_audio(user_id: int, job_uuid: str, line_id: str, data: bytes) -> None:
    save_job_file(user_id, job_uuid, audio_name(line_id), data)


def get_line_audio(user_id: int, job_uuid: str, line_id: str) -> bytes | None:
    try:
        return get_job_file(user_id, job_uuid, audio_name(line_id))
    except Exception:
        return None


def has_line_audio(user_id: int, job_uuid: str, line_id: str) -> bool:
    return job_file_exists(user_id, job_uuid, audio_name(line_id))


def save_transcript(user_id: int, job_uuid: str, text: str) -> None:
    save_job_file(user_id, job_uuid, TRANSCRIPT_FILE, text.encode())
