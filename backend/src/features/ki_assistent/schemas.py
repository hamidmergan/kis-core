"""Pydantic request/response models for KI-Assistent routes."""

from typing import Optional

from pydantic import BaseModel, Field

class CreateModuleForm(BaseModel):
    title: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    expires_at: Optional[str] = None  # ISO datetime string


class PatchModuleBody(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    is_active: Optional[bool] = None


class RenewCodeBody(BaseModel):
    expires_at: str  # ISO datetime string


class CreateAccessLinkBody(BaseModel):
    expires_at: str  # ISO datetime string


class EnrollBody(BaseModel):
    enroll_code: str


class ChatBody(BaseModel):
    question: str
    active_source_ids: Optional[list[str]] = None
    direct_text: Optional[bool] = False  # True = kein RAG, direkt LLM aufrufen
    source_uuid: Optional[str] = None  # Quell-PDF UUID (bei Popup-Aktionen)
    source_filename: Optional[str] = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None  # Markierter Text (für Highlight bei Pill-Click)
    enrollment_id: Optional[int] = None  # Für per-Link Chat-Trennung


class UserSettingsBody(BaseModel):
    chat_lang: str
    studio_enabled: bool = True
    sprachtraining_active: bool


class NoteBody(BaseModel):
    content: str = Field(..., max_length=50000)


# ─── Dozenten-Endpunkte ───────────────────────────────────────────────────────

class GlossaryGenerateBody(BaseModel):
    active_source_ids: list[str]  # max 3 source UUIDs


class ExerciseGenerateBody(BaseModel):
    active_source_ids: list[str]

class GlossaryExtractBody(BaseModel):
    text: str
    source_uuid: str
    page_number: int

class MindmapGenerateBody(BaseModel):
    active_source_ids: list[str]

class LernkartenGenerateBody(BaseModel):
    active_source_ids: list[str]
    count: int = 10

class DatentabelleGenerateBody(BaseModel):
    active_source_ids: list[str]

class CreateSetBody(BaseModel):
    tool: str  # "lernkarten" | "lueckentext" | "vokabeltest"
    mode: str = "glossar"  # "glossar" | "quelle"
    source_uuid: Optional[str] = None
    count: int = 10


class ExerciseProgressBody(BaseModel):
    results: list[dict]  # [{"item_id": int, "correct": bool}]
    new_run: bool = False

