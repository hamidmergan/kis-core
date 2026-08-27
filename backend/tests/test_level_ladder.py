"""The level ladder, shared by assessment, chat and tools."""

import json

from src.services.aia_level_ladder import (
    DEFAULT_LEVEL_DESCRIPTIONS,
    LEVELS,
    build_levels_block,
    description_for_level,
    parse_level_descriptions,
    resolve_prompt_setting,
)


def test_every_level_has_a_shipped_description():
    assert tuple(DEFAULT_LEVEL_DESCRIPTIONS) == LEVELS
    for level in LEVELS:
        assert DEFAULT_LEVEL_DESCRIPTIONS[level].strip()


def test_parse_empty_returns_defaults():
    assert parse_level_descriptions("") == DEFAULT_LEVEL_DESCRIPTIONS
    assert parse_level_descriptions("   ") == DEFAULT_LEVEL_DESCRIPTIONS


def test_parse_merges_partial_override_onto_defaults():
    out = parse_level_descriptions(json.dumps({"A2": "Meine eigene A2-Beschreibung."}))
    assert out["A2"] == "Meine eigene A2-Beschreibung."
    assert out["A1"] == DEFAULT_LEVEL_DESCRIPTIONS["A1"]
    assert out["C2"] == DEFAULT_LEVEL_DESCRIPTIONS["C2"]


def test_parse_ignores_unknown_keys_and_bad_json():
    assert parse_level_descriptions("{kaputt") == DEFAULT_LEVEL_DESCRIPTIONS
    out = parse_level_descriptions(json.dumps({"D1": "gibt es nicht", "A1": "Doch."}))
    assert "D1" not in out
    assert out["A1"] == "Doch."


def test_build_block_lists_every_level_in_order():
    block = build_levels_block(DEFAULT_LEVEL_DESCRIPTIONS)
    lines = block.splitlines()
    assert len(lines) == 6
    for line, level in zip(lines, LEVELS):
        assert line.startswith(f"- {level}: ")
    assert DEFAULT_LEVEL_DESCRIPTIONS["B1"] in block


def test_build_block_skips_an_empty_level():
    block = build_levels_block({"A1": "Nur A1.", "A2": "   "})
    assert block == "- A1: Nur A1."


def test_description_for_level_picks_the_matching_one():
    assert description_for_level("B2", {"B2": "Ausführlich."}) == "Ausführlich."
    assert description_for_level(None, DEFAULT_LEVEL_DESCRIPTIONS) == ""
    assert description_for_level("C2", {"A1": "eins"}) == ""


def test_resolve_prompt_setting_treats_the_old_default_as_unset():
    assert resolve_prompt_setting("", "ALT", "NEU") == "NEU"
    assert resolve_prompt_setting(None, "ALT", "NEU") == "NEU"
    assert resolve_prompt_setting("  ALT  ", "ALT", "NEU") == "NEU"
    assert resolve_prompt_setting("mein eigener Text", "ALT", "NEU") == "mein eigener Text"
