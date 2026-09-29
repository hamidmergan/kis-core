"""The shapes the presentation tool passes between route, task and job folder."""

from pydantic import BaseModel, Field, field_validator

from src.features.praesentation.raster import (
    MAX_BALKEN, MAX_KARTEN, MAX_KENNZAHLEN, MAX_SCHRITTE, MAX_STUFEN, MAX_SYMBOLE,
)
from src.limits import PRAESENTATION_MAX_SLIDES, PRAESENTATION_MIN_SLIDES

ROLLEN: tuple[str, ...] = (
    "deckblatt", "abschnitt", "text", "zwei_spalten", "text_mit_bild", "bild_gross", "abschluss",
)
# The model picks from these for the middle of the deck, first and last slide are forced.
WAEHLBARE_ROLLEN: tuple[str, ...] = ("abschnitt", "text", "zwei_spalten", "text_mit_bild", "bild_gross")
LANGUAGES: tuple[str, ...] = ("de", "en")
# How many slides an outline may hold, the model picks its own number inside this range.
FOLIEN_GRENZEN: tuple[int, int] = (PRAESENTATION_MIN_SLIDES, PRAESENTATION_MAX_SLIDES)
BODY_KINDS: tuple[str, ...] = ("bullets", "table", "chart", "image", "cards", "bars", "highlight",
                               "steps", "figures", "levels", "symbols")
CHART_TYPES: tuple[str, ...] = ("bar", "line", "pie")
SYSTEM_VORLAGE = "thl"

# The one cap per field, shared by the LLM answer parser (folien.py) and this schema,
# so a hand-built PUT body cannot exceed what a model-written slide is ever allowed to hold.
MAX_TITLE_CHARS = 120
MAX_SUBTITLE_CHARS = 160
MAX_NOTES_CHARS = 1500
MAX_PROMPT_CHARS = 600
MAX_HEADING_CHARS = 80
MAX_PRESENTER_CHARS = 80
# What a person may write into a row's gist, the field the insert dialog fills too.
MAX_GIST_CHARS = 300
MAX_SERIES_NAME_CHARS = 60
MAX_TEXT_ITEMS = 8
MAX_TABLE_ROWS = 6
MAX_CHART_CATEGORIES = 6
MAX_CHART_SERIES = 4
MAX_ICON_CHARS = 40
MAX_BAR_TEXT_CHARS = 40
# The word or number in the highlight box, it has to fit one line in large type.
MAX_KEY_CHARS = 24
# A generous ceiling: a real layout offers one or two picture fields, an uploaded one may offer more.
MAX_BILDER_JE_FOLIE = 8


class OutlineRow(BaseModel):
    """One planned slide: what it is, what it shows, and which passages it rests on."""

    id: str = ""
    role: str = "text"
    title: str = ""
    gist: str = ""
    # Numbers of the passages on the run's text map. Empty for a slide that draws on
    # everything, such as an agenda or the closing slide.
    stellen: list[int] = Field(default_factory=list)


class Outline(BaseModel):
    title: str = ""
    subtitle: str = ""
    rows: list[OutlineRow] = Field(default_factory=list)


class Series(BaseModel):
    name: str = Field(default="", max_length=MAX_SERIES_NAME_CHARS)
    values: list[float] = Field(default_factory=list, max_length=MAX_CHART_CATEGORIES)


class Card(BaseModel):
    icon: str = Field(default="", max_length=MAX_ICON_CHARS)
    title: str = Field(default="", max_length=MAX_HEADING_CHARS)
    text: str = Field(default="", max_length=MAX_GIST_CHARS)


class Bar(BaseModel):
    """One labelled bar, its length set by value and its label by text, the number when that is empty."""

    label: str = Field(default="", max_length=MAX_HEADING_CHARS)
    value: float = 0.0
    text: str = Field(default="", max_length=MAX_BAR_TEXT_CHARS)


class Entry(BaseModel):
    """One step of a sequence or one level of a hierarchy: a short title and one sentence."""

    title: str = Field(default="", max_length=MAX_HEADING_CHARS)
    text: str = Field(default="", max_length=MAX_GIST_CHARS)


class Figure(BaseModel):
    """A key number written with its unit, and what it counts."""

    value: str = Field(default="", max_length=MAX_KEY_CHARS)
    label: str = Field(default="", max_length=MAX_HEADING_CHARS)


class Symbol(BaseModel):
    """A term of a set, shown as an icon with its name below."""

    icon: str = Field(default="", max_length=MAX_ICON_CHARS)
    label: str = Field(default="", max_length=MAX_HEADING_CHARS)


class Body(BaseModel):
    """The one content field of a slide, bullets unless the material asks for more."""

    kind: str = "bullets"
    items: list[str] = Field(default_factory=list, max_length=MAX_TEXT_ITEMS)
    header: list[str] = Field(default_factory=list, max_length=MAX_TEXT_ITEMS)
    rows: list[list[str]] = Field(default_factory=list, max_length=MAX_TABLE_ROWS)
    chart_type: str = "bar"
    categories: list[str] = Field(default_factory=list, max_length=MAX_CHART_CATEGORIES)
    series: list[Series] = Field(default_factory=list, max_length=MAX_CHART_SERIES)
    prompt: str = Field(default="", max_length=MAX_PROMPT_CHARS)
    cards: list[Card] = Field(default_factory=list, max_length=MAX_KARTEN)
    bars: list[Bar] = Field(default_factory=list, max_length=MAX_BALKEN)
    # The highlight: one word or number in the coloured box, a sentence beside it, one term of it in colour.
    key: str = Field(default="", max_length=MAX_KEY_CHARS)
    text: str = Field(default="", max_length=MAX_GIST_CHARS)
    emphasis: str = Field(default="", max_length=MAX_HEADING_CHARS)
    steps: list[Entry] = Field(default_factory=list, max_length=MAX_SCHRITTE)
    figures: list[Figure] = Field(default_factory=list, max_length=MAX_KENNZAHLEN)
    levels: list[Entry] = Field(default_factory=list, max_length=MAX_STUFEN)
    symbols: list[Symbol] = Field(default_factory=list, max_length=MAX_SYMBOLE)


class Column(BaseModel):
    heading: str = Field(default="", max_length=MAX_HEADING_CHARS)
    items: list[str] = Field(default_factory=list, max_length=MAX_TEXT_ITEMS)


class ImageSpec(BaseModel):
    prompt: str = Field(default="", max_length=MAX_PROMPT_CHARS)


class Slide(BaseModel):
    """The filled slide, the unit that gets built and previewed."""

    id: str = ""
    role: str = "text"
    # The layout index chosen once, so a rebuild never changes the picture count.
    layout: int | None = None
    title: str = Field(default="", max_length=MAX_TITLE_CHARS)
    subtitle: str = Field(default="", max_length=MAX_SUBTITLE_CHARS)
    body: Body | None = None
    # Not capped at MAX_TEXT_ITEMS: their count follows the uploaded template's own layout, not a bullet limit.
    columns: list[Column] = Field(default_factory=list)
    images: list[ImageSpec] = Field(default_factory=list)
    notes: str = Field(default="", max_length=MAX_NOTES_CHARS)


def bildstellen(s: "Slide") -> list:
    """Everything on a slide that carries a picture description, in the order the tool numbers them."""
    stellen: list = list(s.images)
    if s.body is not None and s.body.kind == "image":
        stellen.append(s.body)
    return stellen


class PraesentationParams(BaseModel):
    """Everything the two tasks need, written once at the start."""

    language: str = "de"
    instructions: str = ""
    # Who gives the talk, shown in the bottom left of the cover when set.
    presenter: str = Field(default="", max_length=MAX_PRESENTER_CHARS)
    # What the person asked for in the first step: notes get written at all.
    notes: bool = False
    # What they decide in the slides step: whether those notes reach the file.
    notes_include: bool = True
    # The chat provider that writes the deck, None runs on the admin route.
    llm_provider_id: int | None = None
    template_id: str = SYSTEM_VORLAGE
    template_name: str = ""
    # True when the saved template could not be read and the system one stepped in.
    template_fallback: bool = False
    style_text: str = ""
    source_label: str = ""
    # Only set for a workspace run: what a slide added later can search through.
    workspace_id: int | None = None
    source_uuids: list[str] = Field(default_factory=list)

    @field_validator("presenter", mode="before")
    @classmethod
    def _ohne_rand(cls, v):
        return v.strip() if isinstance(v, str) else v

    @property
    def notes_in_deck(self) -> bool:
        """Notes reach the file only when they were written and are still wanted."""
        return self.notes and self.notes_include
