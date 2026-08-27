"""Checks the schemas of the glossary write routes against oversized input."""
import pytest
from pydantic import ValidationError

from src.limits import GLOSSARY_MAX_ENTRIES, GLOSSARY_NAME_MAX
from src.features.glossaries.schemas import GlossaryCreate, GlossaryUpdate


# ── GlossaryCreate ──────────────────────────────────────────────────────────

def test_create_accepts_name_and_entries():
    body = GlossaryCreate(name="Maschinenbau", entries={"Welle": "shaft"})
    assert body.name == "Maschinenbau"
    assert body.entries == {"Welle": "shaft"}


def test_create_defaults_entries_to_empty_map():
    body = GlossaryCreate(name="Leer")
    assert body.entries == {}


def test_create_rejects_empty_name():
    with pytest.raises(ValidationError):
        GlossaryCreate(name="")


def test_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        GlossaryCreate(name="   ")


def test_create_rejects_name_over_limit():
    with pytest.raises(ValidationError):
        GlossaryCreate(name="x" * (GLOSSARY_NAME_MAX + 1))


def test_create_accepts_entries_at_exact_cap():
    entries = {f"term{i}": f"t{i}" for i in range(GLOSSARY_MAX_ENTRIES)}
    body = GlossaryCreate(name="Voll", entries=entries)
    assert len(body.entries) == GLOSSARY_MAX_ENTRIES


def test_create_rejects_entries_over_cap():
    entries = {f"term{i}": f"t{i}" for i in range(GLOSSARY_MAX_ENTRIES + 1)}
    with pytest.raises(ValidationError):
        GlossaryCreate(name="Zuviel", entries=entries)


# ── GlossaryUpdate (partial) ────────────────────────────────────────────────

def test_update_allows_name_only():
    body = GlossaryUpdate(name="Neu")
    assert body.name == "Neu"
    assert body.entries is None


def test_update_allows_entries_only():
    body = GlossaryUpdate(entries={"Kraft": "force"})
    assert body.name is None
    assert body.entries == {"Kraft": "force"}


def test_update_rejects_entries_over_cap():
    entries = {f"term{i}": f"t{i}" for i in range(GLOSSARY_MAX_ENTRIES + 1)}
    with pytest.raises(ValidationError):
        GlossaryUpdate(entries=entries)


def test_update_rejects_empty_name_when_present():
    with pytest.raises(ValidationError):
        GlossaryUpdate(name="")
