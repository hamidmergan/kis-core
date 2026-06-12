"""Request schemas for the per-user terminology glossaries."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from src.limits import GLOSSARY_MAX_ENTRIES, GLOSSARY_NAME_MAX


def _validate_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("name must not be blank")
    return stripped


def _validate_entries(value: dict[str, str]) -> dict[str, str]:
    if len(value) > GLOSSARY_MAX_ENTRIES:
        raise ValueError(f"at most {GLOSSARY_MAX_ENTRIES} entries allowed")
    return value


class GlossaryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=GLOSSARY_NAME_MAX)
    entries: dict[str, str] = Field(default_factory=dict)

    _name = field_validator("name")(_validate_name)
    _entries = field_validator("entries")(_validate_entries)


class GlossaryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=GLOSSARY_NAME_MAX)
    entries: Optional[dict[str, str]] = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: Optional[str]) -> Optional[str]:
        return None if value is None else _validate_name(value)

    @field_validator("entries")
    @classmethod
    def _check_entries(cls, value: Optional[dict[str, str]]) -> Optional[dict[str, str]]:
        return None if value is None else _validate_entries(value)
