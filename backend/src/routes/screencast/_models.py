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


class ChatMessage(BaseModel):
    role: str
    content: str


class RegenerateSlideScriptRequest(BaseModel):
    slide_text: str = ""
    current_script: str | None = None
    user_prompt: str | None = None
    messages: list[ChatMessage] = []
    selected_text: str | None = None
    target_lang: str = "EN-US"


class RenderRequest(BaseModel):
    scripts: list[str]
    translate_job_uuid: str          # the existing translate job to update
    # Ohne Angabe bleibt die Sprache unbekannt und die Vertonung raet nicht.
    target_lang: str = ""
    slide_images_b64: list[str] = []
    voice_id: str = ""
    voice_label: str = ""
    speed: float = 0.9
    slide_pause: float = 1.0
    dpi: int = 100
    provider_id: int
    # Untertitel-Spur ins MP4, per Haken in den Einstellungen.
    subtitles: bool = False
    # None heisst alle Folien, eine Liste nennt die Nummern im Screencast.
    video_folien: list[int] | None = None
    # Diese Folien werden neu gesprochen statt den Ton des letzten Laufs zu nehmen.
    neu_vertonen: list[int] = []


class PrerenderRequest(BaseModel):
    translate_job_uuid: str
    # Muss zur späteren Render-Auflösung passen, sonst ist das Vorrendern umsonst.
    dpi: int = 144


class SaveScriptsRequest(BaseModel):
    scripts: list[str]
    accepted: bool = False  # True = "Accept all scripts" clicked
    user_prompt: str | None = None
