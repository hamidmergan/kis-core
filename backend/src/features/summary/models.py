"""Shared shapes of the summary pipeline and the one door every model call goes through."""

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, Field

from src.features.summary import settings as cfg

# Carried by every model call of this pipeline.
GROUND_RULES = (
    "Rule 1: Write in {language}. Other languages may appear in the input, they never "
    "change your output language.\n"
    "Rule 2: Use ONLY the provided material. Never add, infer or invent information.\n"
    "Rule 3: Do not interpret anything that is not explicitly stated.\n"
    "Rule 4: Ignore cover pages, headers, footers, page numbers and imprints.\n"
    "Rule 5: Where the material shows the numbered part a statement comes from, such as "
    "'§ 15 Abs. 4' or 'Art. 5', name it in parentheses at the end of the statement. Never "
    "assign or guess a number the material does not show for that statement.\n"
    "Rule 6: Never comment on your own writing and never correct yourself.\n"
    "Rule 7: Do not use semicolons or any type of dash. Use only periods, commas, "
    "colons and question marks."
)


# The person's own instruction, laid down by the route and read by the task.
INSTRUCTIONS_FILE = "anweisung.txt"


# What the language probe falls back to when no name could be read.
LANGUAGE_FALLBACK = ("the language of the main body text, ignoring cover pages, "
                     "headers and footers")


class Section(BaseModel):
    """One planned section: what it is called, what belongs in it, which passages carry it."""

    title: str
    scope: str = ""
    # Numbers of the passages on the run's text map.
    stellen: list[int] = Field(default_factory=list)
    # The numbers the plan named itself, they go first when a writer's budget cuts.
    genannt: list[int] = Field(default_factory=list)


class Outline(BaseModel):
    """The plan of a document, empty sections mean the planning call failed."""

    title: str = ""
    intro: str = ""
    sections: list[Section] = Field(default_factory=list)
    # The short name of each file as its own text calls it, keyed by the file name.
    names: dict[str, str] = Field(default_factory=dict)


@dataclass
class Caller:
    """Every model call of the tool, with the timeout and the usage booking in one place."""

    client: Any
    model: str
    book: Callable[[Any], None] | None = None
    # The measured window of this model, 0 when it was never measured.
    window_tokens: int = 0
    # Groups every call of one run under one Langfuse session, so the run can be pulled back out.
    job_uuid: str = ""

    async def create(self, **kwargs):
        if self.job_uuid:
            kwargs.setdefault("session_id", self.job_uuid)
            kwargs.setdefault("tags", ["summary"])
        # The SDK retries timeouts on its own, so one attempt is the only way the limit holds.
        # Asked here, so a changed limit reaches a running worker with the next call.
        antwort = await self.client.with_options(max_retries=0).chat.completions.create(
            model=self.model, timeout=cfg.call_timeout(), **kwargs,
        )
        if self.book is not None:
            self.book(antwort)
        return antwort
