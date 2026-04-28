"""Pydantic request/response models for AI assistant routes."""

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
    direct_text: Optional[bool] = False  # True = no RAG, call LLM directly
    source_uuid: Optional[str] = None  # Source PDF UUID (for popup actions)
    source_filename: Optional[str] = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None  # Selected text (for highlight on pill click)
    enrollment_id: Optional[int] = None  # For per-link chat separation


class UserSettingsBody(BaseModel):
    chat_lang: str
    studio_enabled: bool = True
    language_training_active: bool


class NoteBody(BaseModel):
    content: str = Field(..., max_length=50000)
    source_uuids: Optional[list[str]] = None
    # Carry chat metadata so the chat citation renderer can resolve exact-highlight
    # state (popup-action selections) when the note is later opened.
    source_pages: Optional[list[dict]] = None
    popup_selection: Optional[dict] = None
    auto_title: bool = True


class NoteTitleBody(BaseModel):
    title: Optional[str] = Field(None, max_length=200)


# ─── Lecturer endpoints ───────────────────────────────────────────────────────

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

class FlashcardsGenerateBody(BaseModel):
    active_source_ids: list[str]
    count: int = 10

class DataTableGenerateBody(BaseModel):
    active_source_ids: list[str]

class CreateSetBody(BaseModel):
    tool: str  # "flashcards" | "lueckentext" | "vokabeltest"
    mode: str = "glossary"  # "glossary" | "source"
    source_uuid: Optional[str] = None
    count: int = 10


class ExerciseProgressBody(BaseModel):
    results: list[dict]  # [{"item_id": int, "correct": bool}]
    new_run: bool = False


# ─── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleGenerateBody(BaseModel):
    source_ids: list[str]  # max 30 source UUIDs


class ScheduleEntryCreateBody(BaseModel):
    type: str  # 'deadline' | 'termin'
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[str] = None  # ISO date 'YYYY-MM-DD' or None
    due_time: Optional[str] = None  # 'HH:MM' or None
    is_optional: bool = False


class ScheduleEntryUpdateBody(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    is_optional: Optional[bool] = None
    is_checked: Optional[bool] = None
    clear_date: bool = False  # explicitly set to NULL
    clear_time: bool = False

