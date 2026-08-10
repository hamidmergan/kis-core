"""Pydantic request/response models for AI assistant routes."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from src.limits import AIA_QUESTION_MAX_CHARS


class StaffNoteLink(BaseModel):
    url: str = Field(..., max_length=500)
    label: str = Field(..., max_length=100)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        v = v.strip()
        lower = v.lower()
        if not (lower.startswith("http://") or lower.startswith("https://") or lower.startswith("mailto:")):
            raise ValueError("url must start with http(s):// or mailto:")
        return v

    @field_validator("label")
    @classmethod
    def _validate_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label must not be empty")
        return v

class CreateWorkspaceForm(BaseModel):
    title: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    expires_at: Optional[str] = None  # ISO datetime string


class PatchWorkspaceBody(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    is_active: Optional[bool] = None
    transcript_target_lang: Optional[str] = None
    diagnosis_language: Optional[str] = None
    # Sprachtrainer for everyone in this workspace. Admin decision, see the
    # rank check in patch_workspace.
    language_training_active: Optional[bool] = None
    staff_note_text: Optional[str] = Field(None, max_length=2000)
    staff_note_links: Optional[list[StaffNoteLink]] = Field(None, max_length=30)


class RenewCodeBody(BaseModel):
    # None means the link never expires, same as leaving the field empty in the UI.
    expires_at: Optional[str] = None  # ISO datetime string


class CreateAccessLinkBody(BaseModel):
    # None means the link never expires. Not every course has an end date, and a
    # forced one only leads to links that quietly stop working mid-semester.
    expires_at: Optional[str] = None  # ISO datetime string


class SetParticipantRoleBody(BaseModel):
    # Owner-only. A tutor manages the workspace like the owner, except that
    # inviting stays with the owner alone.
    role: Literal["student", "tutor"]


class EnrollBody(BaseModel):
    enroll_code: str


class ChatBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=AIA_QUESTION_MAX_CHARS)
    active_source_ids: Optional[list[str]] = None
    direct_text: Optional[bool] = False  # True = no RAG, call LLM directly
    source_uuid: Optional[str] = None  # Source PDF UUID (for popup actions)
    source_filename: Optional[str] = None
    source_page: Optional[int] = None
    source_text: Optional[str] = None  # Selected text (for highlight on pill click)
    action_key: Optional[str] = None  # Popup action key (e.g. "translate", "simplify")
    enrollment_id: Optional[int] = None  # For per-link chat separation


class UserSettingsBody(BaseModel):
    chat_lang: str
    studio_enabled: bool = True
    # Zielsprache der Auswahlleisten-Übersetzung, Code aus i18n.TRANSCRIPT_LANGUAGES.
    popup_translate_lang: str = "en"
    # Eigene Entscheidung, ob der vom Kurs freigegebene Sprachtrainer angezeigt
    # wird. Standard aus.
    language_training_active: bool = False


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
    tool: str  # "flashcards" | "karteikarten" | "quiz" | "grammatik"
    mode: str = "glossary"  # "glossary" | "source"
    source_uuid: Optional[str] = None  # legacy single-source clients
    source_uuids: Optional[list[str]] = None  # preferred: all selected sources
    count: int = 10
    # Only tool="grammatik": id of the workspace's grammar topic the set is built from.
    grammar_topic_id: Optional[int] = None


class GrammarExamplePair(BaseModel):
    """Ein Musterpaar. Steuert das Modell und ist zugleich das, was der Dozent
    prüft und der Lernende sieht."""
    before: str = Field(..., max_length=500)
    after: str = Field(..., max_length=500)


class GrammarTopicPreviewBody(BaseModel):
    """Der getippte Themenname. Kein Prompt, nur ein Name."""
    name: str = Field(..., max_length=120)


class GrammarTopicCreateBody(BaseModel):
    name: str = Field(..., max_length=120)
    rule: str = Field(..., max_length=4000)
    examples: list[GrammarExamplePair]
    # Die vier Anweisungszeilen aus der Vorschau. Optional: aeltere Clients schicken sie
    # nicht, dann arbeitet der erste Uebungslauf das Thema nach.
    task_lines: dict[str, str] | None = None


class GrammarTopicUpdateBody(BaseModel):
    examples: list[GrammarExamplePair]


class GrammarCheckBody(BaseModel):
    """One free-text answer submitted for marking."""
    answer: str = Field(..., max_length=1000)


class ExerciseProgressBody(BaseModel):
    results: list[dict]  # [{"item_id": int, "correct": bool}]


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

