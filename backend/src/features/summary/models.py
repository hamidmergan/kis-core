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
    "Rule 5: Keep section numbers such as 'Paragraf 211' or 'Art. 5' only where the "
    "material attaches them to that exact term. Never assign or guess one.\n"
    "Rule 6: Never comment on your own writing and never correct yourself.\n"
    "Rule 7: Do not use semicolons or any type of dash. Use only periods, commas, "
    "colons and question marks."
)


# What the language probe falls back to when no name could be read.
LANGUAGE_FALLBACK = ("the language of the main body text, ignoring cover pages, "
                     "headers and footers")


class Section(BaseModel):
    """One planned section: what it is called and what belongs in it."""

    title: str
    scope: str = ""


class Outline(BaseModel):
    """The plan of a document, empty sections mean the planning call failed."""

    title: str = ""
    intro: str = ""
    sections: list[Section] = Field(default_factory=list)


@dataclass
class Caller:
    """Every model call of the tool, with the timeout and the usage booking in one place."""

    client: Any
    model: str
    book: Callable[[Any], None] | None = None
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
