"""The shapes the podcast tool passes between route, task and job folder."""

from pydantic import BaseModel, Field

ROLES: tuple[str, ...] = ("host", "expert", "student", "critic")
STYLES: tuple[str, ...] = ("teaching", "casual", "interview")
LANGUAGES: tuple[str, ...] = ("de", "en")

# Speaking tempo, the same range and default the screencast offers.
SPEED_MIN, SPEED_MAX, SPEED_DEFAULT = 0.7, 1.2, 0.9

# A model keeps a count of paragraphs far better than a total word count, so the target
# is stated as (contributions, words each) and the sum only follows from it. One long turn in
# three among shorter replies averages about 27 words, measured on 30.09.2026.
LENGTH_PLAN: dict[str, tuple[int, int]] = {"short": (27, 27), "medium": (54, 27), "long": (107, 27)}
LENGTH_WORDS: dict[str, int] = {name: n * je for name, (n, je) in LENGTH_PLAN.items()}


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
    speed: float = SPEED_DEFAULT
    persons: list[Person]
    length: str = "medium"
    style: str = "teaching"
    provider_id: int = 0
    # The chat provider that writes the script, None runs on the admin route.
    llm_provider_id: int | None = None
    voice_label: str = ""
    source_label: str = ""
    # Written by hand from an empty script, so no model is ever asked for this one.
    self_written: bool = False
    # The instruction named something the material does not cover, so it dropped out.
    instruction_unmatched: bool = False
    # What the instruction turned out to be, decided once per run, see services/anweisung.py.
    instruction_way: str = ""
    # Sifted down to what the material contains at the start, so every later call can use it.
    glossary: dict[str, str] = Field(default_factory=dict)
