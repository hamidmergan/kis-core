"""Pydantic models for the screencast endpoints."""

from pydantic import BaseModel


class ExtractTextsRequest(BaseModel):
    pptx_b64: str


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


class PrepareRequest(BaseModel):
    translated_pptx_b64: str


class RenderRequest(BaseModel):
    scripts: list[str]
    translate_job_uuid: str          # the existing translate job to update
    slide_images_b64: list[str] = []
    voice_id: str = ""
    voice_label: str = ""
    speed: float = 1.0
    slide_pause: float = 0.5
    dpi: int = 100
    provider: str = "elevenlabs"


class PrerenderRequest(BaseModel):
    translate_job_uuid: str


class SaveScriptsRequest(BaseModel):
    scripts: list[str]
    accepted: bool = False  # True = "Accept all scripts" clicked
    user_prompt: str | None = None
