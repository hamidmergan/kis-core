"""The shapes the podcast tool passes between route, task and job folder."""

from pydantic import BaseModel, Field

ROLES: tuple[str, ...] = ("host", "expert", "student", "critic")
STYLES: tuple[str, ...] = ("teaching", "casual", "interview")
LANGUAGES: tuple[str, ...] = ("de", "en")

# Target length in words, spoken at roughly 140 words per minute.
LENGTH_WORDS: dict[str, int] = {"short": 700, "medium": 1400, "long": 2800}


class Person(BaseModel):
    """One voice of the podcast."""

    name: str = Field(min_length=1, max_length=60)
    role: str = "host"
    voice_id: str = ""
    # Voices may come from different providers, so each person names their own.
    provider_id: int = 0


class Line(BaseModel):
    """One contribution of one person, the unit that gets voiced."""

    id: str = ""
    speaker: int = 0
    text: str = ""


class PodcastParams(BaseModel):
    """Everything the two tasks need, written once at the start."""

    language: str = "de"
    instructions: str = ""
    persons: list[Person]
    length: str = "medium"
    style: str = "teaching"
    provider_id: int = 0
    voice_label: str = ""
    source_label: str = ""
