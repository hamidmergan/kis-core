"""Only the routers of the chosen profile are mounted."""
from src.app import create_app
from src.modules import MODULE_AIA, MODULE_TOOLS

BEIDE = frozenset({MODULE_AIA, MODULE_TOOLS})
NUR_AIA = frozenset({MODULE_AIA})
NUR_TOOLS = frozenset({MODULE_TOOLS})


def _pfade(modules) -> set[str]:
    return set(create_app(modules=modules).openapi()["paths"])


def test_beide_module_haengen_alles_ein():
    pfade = _pfade(BEIDE)
    assert "/tts/providers-with-voices" in pfade
    assert "/ai-assistant/workspaces" in pfade


def test_ohne_tools_fehlen_die_werkzeug_pfade():
    pfade = _pfade(NUR_AIA)
    assert "/tts/providers-with-voices" not in pfade
    assert "/translate/config" not in pfade
    assert not any(p.startswith("/glossaries") for p in pfade)


def test_ohne_tools_bleiben_die_assistenten_pfade():
    pfade = _pfade(NUR_AIA)
    assert "/ai-assistant/workspaces" in pfade


def test_ohne_aia_fehlen_die_assistenten_pfade():
    pfade = _pfade(NUR_TOOLS)
    assert not any(p.startswith("/ai-assistant") for p in pfade)


def test_ohne_aia_bleiben_die_werkzeug_pfade():
    pfade = _pfade(NUR_TOOLS)
    assert "/tts/providers-with-voices" in pfade


def test_gemeinsame_pfade_bleiben_in_jedem_profil():
    for profil in (BEIDE, NUR_AIA, NUR_TOOLS):
        pfade = _pfade(profil)
        assert "/health" in pfade
        assert "/auth/status" in pfade
        assert any(p.startswith("/jobs") for p in pfade)
