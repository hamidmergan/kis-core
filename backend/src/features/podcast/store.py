"""Every file the podcast tool keeps in the job folder, in one place."""

import json
import re


from src.features.podcast.schemas import Line, PodcastParams
from src.storage import get_job_file, job_file_exists, save_job_file

SOURCE_FILE = "source.txt"
PARAMS_FILE = "params.json"
SCRIPT_FILE = "script.json"
USER_SCRIPT_FILE = "user_script.json"
VOICED_FILE = "voiced.json"
TRANSCRIPT_FILE = "transcript.txt"

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


def save_source(user_id: int, job_uuid: str, text: str) -> None:
    save_job_file(user_id, job_uuid, SOURCE_FILE, text.encode())


def load_source(user_id: int, job_uuid: str) -> str:
    try:
        return get_job_file(user_id, job_uuid, SOURCE_FILE).decode()
    except Exception:
        return ""


def save_params(user_id: int, job_uuid: str, params: PodcastParams) -> None:
    _write_json(user_id, job_uuid, PARAMS_FILE, params.model_dump())


def load_params(user_id: int, job_uuid: str) -> PodcastParams | None:
    raw = _read_json(user_id, job_uuid, PARAMS_FILE)
    return PodcastParams(**raw) if raw else None


def save_script(user_id: int, job_uuid: str, lines: list[Line]) -> None:
    """What the model wrote, kept apart so a person can always fall back to it."""
    _write_json(user_id, job_uuid, SCRIPT_FILE, [l.model_dump() for l in lines])


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


def fingerprint(line: Line, voice_id: str, speed: float) -> dict:
    """What makes a contribution sound different, nothing else."""
    return {"text": line.text.strip(), "voice_id": voice_id, "speed": round(speed, 2)}


def needs_voice(line: Line, voiced: dict[str, dict], voice_id: str, speed: float) -> bool:
    return voiced.get(line.id) != fingerprint(line, voice_id, speed)


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
