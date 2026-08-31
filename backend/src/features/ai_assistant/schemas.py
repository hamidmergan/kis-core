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

class PatchWorkspaceBody(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=300)
    is_active: Optional[bool] = None
    transcript_target_lang: Optional[str] = None
    diagnosis_language: Optional[str] = None
    # Language trainer for everyone in this course room, a management decision.
    language_training_active: Optional[bool] = None
    staff_note_text: Optional[str] = Field(None, max_length=2000)
    staff_note_links: Optional[list[StaffNoteLink]] = Field(None, max_length=30)


class RenewCodeBody(BaseModel):
    # None means the link never expires, same as leaving the field empty in the UI.
    expires_at: Optional[str] = None  # ISO datetime string


class CreateAccessLinkBody(BaseModel):
    # None means the link never expires.
    expires_at: Optional[str] = None  # ISO datetime string


class SetParticipantRoleBody(BaseModel):
    # Owner only, inviting stays with them alone.
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
    # Target language of the selection bar translation, code from i18n.TRANSCRIPT_LANGUAGES.
    popup_translate_lang: str = "en"
    # Personal decision whether the released language trainer is shown.
    language_training_active: bool = False


class NoteBody(BaseModel):
    content: str = Field(..., max_length=50000)
    source_uuids: Optional[list[str]] = None
    # Carry the chat details along so the citations resolve again on opening.
    source_pages: Optional[list[dict]] = None
    popup_selection: Optional[dict] = None
    auto_title: bool = True


class NoteTitleBody(BaseModel):
    title: Optional[str] = Field(None, max_length=200)


class ArtifactTitleBody(BaseModel):
    """New display name for a set, mind map or data table."""
    title: str = Field(..., max_length=200)


# ─── Lecturer endpoints ───────────────────────────────────────────────────────

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
    tool: str  # "flashcards" | "karteikarten" | "quiz" | "grammatik" | "wortschatz"
    mode: str = "glossary"  # "glossary" | "source" | "cards"
    source_uuid: Optional[str] = None  # legacy single-source clients
    source_uuids: Optional[list[str]] = None  # preferred: all selected sources
    count: int = 10
    # Only tool="grammatik": id of the workspace's grammar topic the set is built from.
    grammar_topic_id: Optional[int] = None
    # Grammar only: the chosen formats, missing means mixed.
    grammar_kinds: Optional[list[str]] = None
    # Only for vocabulary from cards, the text still comes from the sources.
    flashcard_set_id: Optional[int] = None


class GrammarExamplePair(BaseModel):
    """A pattern pair, it steers the model and shows the learner the form."""
    before: str = Field(..., max_length=500)
    after: str = Field(..., max_length=500)


class GrammarTopicPreviewBody(BaseModel):
    """The typed topic name, no prompt, just a name."""
    name: str = Field(..., max_length=120)


class GrammarTopicCreateBody(BaseModel):
    name: str = Field(..., max_length=120)
    rule: str = Field(..., max_length=4000)
    examples: list[GrammarExamplePair]


class GrammarTopicUpdateBody(BaseModel):
    examples: list[GrammarExamplePair]


class GrammarCheckBody(BaseModel):
    """One free-text answer submitted for marking."""
    answer: str = Field(..., max_length=1000)


class ExerciseProgressBody(BaseModel):
    results: list[dict]  # [{"item_id": int, "correct": bool}]
    # The exercise view sets this on its first answer.
    new_run: bool = False


# ─── Schedule ─────────────────────────────────────────────────────────────────

class ScheduleGenerateBody(BaseModel):
    source_ids: list[str]  # max 30 source UUIDs


class ScheduleEntryCreateBody(BaseModel):
    type: str  # 'deadline' | 'termin'
    title: str = Field(..., max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[str] = None  # ISO date 'YYYY-MM-DD' or None
    # When set, the appointment runs until this day.
    end_date: Optional[str] = None
    due_time: Optional[str] = None  # 'HH:MM' or None
    # When set, it ends on this day at this time.
    end_time: Optional[str] = None
    # With 'month' the appointment only knows the month, the first sorts it.
    date_precision: Optional[str] = None
    # Gesetzt heisst: Anfang bekannt, Ende ausdruecklich offen ("ab 15.09.").
    is_open_ended: bool = False
    is_optional: bool = False


class ScheduleEntryUpdateBody(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[str] = None
    end_date: Optional[str] = None
    due_time: Optional[str] = None
    end_time: Optional[str] = None
    date_precision: Optional[str] = None
    is_open_ended: Optional[bool] = None
    is_optional: Optional[bool] = None
    is_checked: Optional[bool] = None
    clear_date: bool = False  # explicitly set to NULL
    clear_time: bool = False
    clear_end_date: bool = False
    clear_end_time: bool = False


# Limits for private appointments, the same numbers are in the frontend dialog.
TITLE_MAX = 80
NOTE_MAX = 500


class PersonalEntryCreateBody(BaseModel):
    """A private appointment, it belongs to no workspace."""
    # Tighter than for extracted appointments, the title sits in a narrow column.
    title: str = Field(..., max_length=TITLE_MAX)
    description: Optional[str] = Field(None, max_length=NOTE_MAX)
    due_date: str  # ISO date 'YYYY-MM-DD'
    # When set, the appointment runs until this day.
    end_date: Optional[str] = None
    due_time: Optional[str] = None


class PersonalEntryUpdateBody(BaseModel):
    title: Optional[str] = Field(None, max_length=TITLE_MAX)
    description: Optional[str] = Field(None, max_length=NOTE_MAX)
    due_date: Optional[str] = None
    end_date: Optional[str] = None
    due_time: Optional[str] = None
    is_checked: Optional[bool] = None
    clear_end_date: bool = False
    clear_time: bool = False

