"""Pydantic models for the screencast endpoints."""

from pydantic import BaseModel


class GenerateScriptsRequest(BaseModel):
    slide_texts: list[str]
    glossary_json: str = ""
    translate_job_uuid: str | None = None
    add_greeting: bool = True
    add_closing: bool = True
    min_chars: int = 1500
    max_chars: int = 2000
    source_lang: str = "DE"
    target_lang: str = "EN-US"


class RenderRequest(BaseModel):
    scripts: list[str]
    translate_job_uuid: str          # the existing translate job to update
    # Without a value the language stays unknown and the voicing does not guess.
    target_lang: str = ""
    slide_images_b64: list[str] = []
    voice_id: str = ""
    voice_label: str = ""
    speed: float = 0.9
    slide_pause: float = 1.0
    dpi: int = 100
    provider_id: int
    # Subtitle track in the MP4, via a checkbox in the settings.
    subtitles: bool = False
    # None means all slides, a list names the numbers in the screencast.
    video_folien: list[int] | None = None
    # These slides are voiced again instead of taking the audio of the last run.
    neu_vertonen: list[int] = []


class PrerenderRequest(BaseModel):
    translate_job_uuid: str
    # Must match the later render resolution, otherwise pre-rendering is wasted.
    dpi: int = 144


class SaveScriptsRequest(BaseModel):
    scripts: list[str]
    accepted: bool = False  # True = "Accept all scripts" clicked
    user_prompt: str | None = None
