"""Reworking a slide script stays inside the slide, also for a marked passage."""

from types import SimpleNamespace

import pytest

from src.services.openai_compat_llm import _scripts


class FakeClient:
    """Catches the messages instead of asking a provider."""

    def __init__(self):
        self.gesehen: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.gesehen = kw["messages"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Neuer Text."))])


@pytest.fixture
def llm(monkeypatch):
    monkeypatch.setattr(_scripts, "_verbrauch", lambda *a, **k: None)
    client = FakeClient()
    dienst = _scripts._ScriptsMixin()
    dienst._client = client
    dienst._model = "m"
    dienst._extra_body = None
    return dienst, client


FOLIE = "Die Spannung wird in Volt gemessen, der Widerstand in Ohm."


def test_markierte_stelle_bekommt_den_folientext_dazu(llm):
    dienst, client = llm
    dienst.refine_script("erklaer das genauer", current_script="Ein Satz ueber Spannung.",
                         slide_text=FOLIE, selected_text="ueber Spannung")
    gesamt = " ".join(m["content"] for m in client.gesehen)
    assert "Volt" in gesamt


def test_markierte_stelle_verbietet_neue_fakten(llm):
    dienst, client = llm
    dienst.refine_script("erklaer das genauer", current_script="Ein Satz.",
                         slide_text=FOLIE, selected_text="Ein Satz")
    system = client.gesehen[0]["content"]
    assert "not in the slide" in system.lower()


def test_ohne_markierung_bleibt_die_regel_bestehen(llm):
    dienst, client = llm
    dienst.refine_script("kuerzer", current_script="Ein Satz.", slide_text=FOLIE)
    system = client.gesehen[0]["content"]
    assert "do not add any new information" in system.lower()


def test_leeres_skript_faellt_auf_den_folientext_zurueck(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", current_script="", slide_text=FOLIE)
    gesamt = " ".join(m["content"] for m in client.gesehen)
    assert "Volt" in gesamt


def test_ohne_angabe_der_stelle_bleibt_der_prompt_stumm(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", current_script="", slide_text=FOLIE)
    assert "slide 1 of" not in " ".join(m["content"] for m in client.gesehen).lower()


def test_nennt_die_stelle_im_foliensatz(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", slide_text=FOLIE, position=(3, 10))
    assert "slide 3 of 10" in client.gesehen[0]["content"].lower()


def test_erste_folie_begruesst(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", slide_text=FOLIE, position=(1, 10))
    system = client.gesehen[0]["content"].lower()
    assert "greeting" in system and "welcome" in system


def test_erste_folie_ohne_begruessung_wenn_abgeschaltet(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", slide_text=FOLIE, position=(1, 10), add_greeting=False)
    assert "do not use any greeting" in client.gesehen[0]["content"].lower()


def test_letzte_folie_ohne_schlusswort(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", slide_text=FOLIE, position=(10, 10))
    assert "closing" in client.gesehen[0]["content"].lower()


def test_folie_in_der_mitte_bekommt_keine_zusatzregel(llm):
    dienst, client = llm
    dienst.refine_script("schreib den Text", slide_text=FOLIE, position=(5, 10))
    system = client.gesehen[0]["content"].lower()
    assert "greeting" not in system and "closing" not in system


def test_stelle_gilt_auch_fuer_die_markierte_passage(llm):
    dienst, client = llm
    dienst.refine_script("kuerzer", current_script="Ein Satz.", slide_text=FOLIE,
                         selected_text="Ein Satz", position=(1, 10))
    assert "slide 1 of 10" in client.gesehen[0]["content"].lower()


class TestRouteReichtDieStelleDurch:
    """Die Route muss der Modellschicht sagen, wo die Folie steht."""

    def _aufruf(self, monkeypatch, **felder):
        import asyncio

        from src.routes.screencast import scripts as modul
        from src.routes.screencast._models import RegenerateSlideScriptRequest

        gesehen = {}

        class FakeLlm:
            def refine_script(self, *args, **kw):
                gesehen["args"] = args
                gesehen["kw"] = kw
                return "Neuer Text."

        monkeypatch.setattr(modul, "get_llm_client", lambda: FakeLlm())
        body = RegenerateSlideScriptRequest(slide_text="Die Folie.", user_prompt="kuerzer", **felder)
        asyncio.run(modul.screencast_regenerate_slide_script(body, current_user={"id": 1}, locale="de"))
        return gesehen

    def test_gibt_stelle_und_gesamtzahl_weiter(self, monkeypatch):
        gesehen = self._aufruf(monkeypatch, slide_index=0, slide_count=12)
        assert gesehen["kw"]["position"] == (1, 12)

    def test_ohne_angabe_bleibt_die_stelle_offen(self, monkeypatch):
        gesehen = self._aufruf(monkeypatch)
        assert gesehen["kw"]["position"] is None
