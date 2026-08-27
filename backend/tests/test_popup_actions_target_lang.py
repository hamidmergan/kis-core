"""The selection bar target language sits in the prompt, unknown falls back to English."""

import pytest

from src.features.ai_assistant.routes.popup import get_popup_actions


async def _translate_prompt(**kwargs):
    data = await get_popup_actions(**kwargs)
    action = next(a for a in data["actions"] if a["key"] == "translate")
    return action["prompt"]


@pytest.mark.asyncio
async def test_spanisch_steht_im_prompt():
    prompt = await _translate_prompt(locale="de", target="es")
    assert "Spanish" in prompt


@pytest.mark.asyncio
async def test_tuerkisch_steht_im_englischen_prompt():
    prompt = await _translate_prompt(locale="en", target="tr")
    assert "Turkish" in prompt


@pytest.mark.asyncio
async def test_ohne_angabe_englisch():
    prompt = await _translate_prompt(locale="de", target="en")
    assert "English" in prompt


@pytest.mark.asyncio
async def test_unbekannter_code_faellt_auf_englisch_zurueck():
    prompt = await _translate_prompt(locale="de", target="klingonisch")
    assert "English" in prompt


@pytest.mark.asyncio
async def test_alte_deutsch_englisch_regel_ist_weg():
    prompt = await _translate_prompt(locale="de", target="fr")
    assert "ins Englische" not in prompt
    assert "ins Deutsche" not in prompt


@pytest.mark.asyncio
async def test_erklaeren_bleibt_unberuehrt():
    data = await get_popup_actions(locale="de", target="fr")
    action = next(a for a in data["actions"] if a["key"] == "simplify")
    assert "French" not in action["prompt"]
    assert "Sprache des Originaltexts" in action["prompt"]
