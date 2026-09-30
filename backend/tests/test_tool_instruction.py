"""Die Anweisung der Lernwerkzeuge entscheidet den Weg: auffuellen, suchen oder fallenlassen."""

import types

import pytest

from src.features.ai_assistant.tasks import _instruction as anweisung


@pytest.fixture
def kein_vorcall(monkeypatch):
    """Der Vor-Call darf in keinem dieser Tests ein Modell fragen."""
    def _nie(*args, **kwargs):
        raise AssertionError("der Vor-Call haette nicht laufen duerfen")

    monkeypatch.setattr(anweisung, "classify", _nie)


def _weg(monkeypatch, antwort):
    """Der Vor-Call antwortet mit einem festen Weg, ohne Modell."""
    gefragt = []

    def _fake(text):
        gefragt.append(text)
        return antwort

    monkeypatch.setattr(anweisung, "classify", _fake)
    return gefragt


def _eingebettet(monkeypatch, ids=(1, 2)):
    monkeypatch.setattr(anweisung, "_ready_ids", lambda source_ids: list(ids))


def _nah(monkeypatch, abstand=0.4):
    monkeypatch.setattr(anweisung, "probe", lambda ws, ids, text: abstand)


def _treffer(monkeypatch, chunks):
    gesucht = []

    def _fake(ws, ids, text, budget):
        gesucht.append((ws, ids, text, budget))
        return chunks

    monkeypatch.setattr(anweisung, "search", _fake)
    return gesucht


STELLE = {"source_id": 1, "page_number": 3, "content": "Die Kuehlung arbeitet mit Wasser."}


# --- resolve: die Wegwahl ----------------------------------------------------

class TestWegwahl:
    def test_leere_anweisung_geht_keinen_weg(self, kein_vorcall):
        for leer in ("", "   ", None):
            ergebnis = anweisung.resolve(7, [1], leer, 1000)
            assert ergebnis.text == ""
            assert ergebnis.chunks is None
            assert ergebnis.unmatched is False
            assert ergebnis.way == anweisung.NONE

    def test_unsinn_faellt_weg_ohne_messung(self, monkeypatch):
        _weg(monkeypatch, anweisung.NONSENSE)
        monkeypatch.setattr(anweisung, "probe", lambda *a: pytest.fail("keine Messung bei Unsinn"))
        ergebnis = anweisung.resolve(7, [1], "asdf qwertz", 1000)
        assert ergebnis.text == ""
        assert ergebnis.chunks is None
        assert ergebnis.unmatched is True
        assert ergebnis.way == anweisung.UNMATCHED

    def test_stil_anweisung_bleibt_im_prompt_und_beim_material(self, monkeypatch):
        _weg(monkeypatch, anweisung.FILL)
        ergebnis = anweisung.resolve(7, [1], "halte es einfach", 1000)
        assert ergebnis.text == "halte es einfach"
        assert ergebnis.chunks is None
        assert ergebnis.unmatched is False
        assert ergebnis.way == anweisung.STYLE

    def test_themen_anweisung_nah_am_material_nimmt_die_gefundenen_stellen(self, monkeypatch):
        gefragt = _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)
        _nah(monkeypatch)
        gesucht = _treffer(monkeypatch, [STELLE])
        ergebnis = anweisung.resolve(7, [1, 2], "nur die Kuehlung", 5000)
        assert gefragt == ["nur die Kuehlung"]
        assert gesucht == [(7, [1, 2], "nur die Kuehlung", 5000)]
        assert ergebnis.chunks == [STELLE]
        assert ergebnis.text == "nur die Kuehlung"
        assert ergebnis.unmatched is False
        assert ergebnis.way == anweisung.SEARCH

    def test_themen_anweisung_neben_dem_material_faellt_weg(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)
        _nah(monkeypatch, abstand=0.8)
        gesucht = _treffer(monkeypatch, [STELLE])
        ergebnis = anweisung.resolve(7, [1], "erklaere Quantenphysik", 1000)
        assert gesucht == []
        assert ergebnis.text == ""
        assert ergebnis.chunks is None
        assert ergebnis.unmatched is True
        assert ergebnis.way == anweisung.UNMATCHED

    def test_suche_ohne_treffer_gilt_als_daneben(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)
        _nah(monkeypatch)
        _treffer(monkeypatch, [])
        ergebnis = anweisung.resolve(7, [1], "nur die Kuehlung", 1000)
        assert ergebnis.text == ""
        assert ergebnis.unmatched is True
        assert ergebnis.way == anweisung.UNMATCHED

    def test_treffer_ohne_text_gelten_als_daneben(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)
        _nah(monkeypatch)
        _treffer(monkeypatch, [{"source_id": 1, "page_number": 3, "content": "  "},
                               {"source_id": 2, "page_number": 1, "content": None}])
        ergebnis = anweisung.resolve(7, [1, 2], "nur die Kuehlung", 1000)
        assert ergebnis.text == ""
        assert ergebnis.chunks is None
        assert ergebnis.unmatched is True
        assert ergebnis.way == anweisung.UNMATCHED

    def test_leere_stellen_fallen_aus_den_treffern(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)
        _nah(monkeypatch)
        _treffer(monkeypatch, [STELLE, {"source_id": 2, "page_number": 1, "content": ""}])
        ergebnis = anweisung.resolve(7, [1, 2], "nur die Kuehlung", 1000)
        assert ergebnis.chunks == [STELLE]
        assert ergebnis.way == anweisung.SEARCH

    def test_nichts_eingebettet_fuellt_auf_und_behaelt_die_anweisung(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch, ids=())
        ergebnis = anweisung.resolve(7, [1], "nur die Kuehlung", 1000)
        assert ergebnis.text == "nur die Kuehlung"
        assert ergebnis.chunks is None
        assert ergebnis.unmatched is False
        assert ergebnis.way == anweisung.FILL

    def test_gescheiterte_suche_fuellt_auf_und_behaelt_die_anweisung(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)
        _nah(monkeypatch)

        def _kaputt(ws, ids, text, budget):
            raise RuntimeError("Embedding weg")

        monkeypatch.setattr(anweisung, "search", _kaputt)
        ergebnis = anweisung.resolve(7, [1], "nur die Kuehlung", 1000)
        assert ergebnis.text == "nur die Kuehlung"
        assert ergebnis.chunks is None
        assert ergebnis.way == anweisung.FILL

    def test_gescheiterte_messung_zaehlt_als_nah(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        _eingebettet(monkeypatch)

        def _kaputt(ws, ids, text):
            raise RuntimeError("kein Vektor")

        monkeypatch.setattr(anweisung, "probe", _kaputt)
        _treffer(monkeypatch, [STELLE])
        ergebnis = anweisung.resolve(7, [1], "nur die Kuehlung", 1000)
        assert ergebnis.chunks == [STELLE]
        assert ergebnis.way == anweisung.SEARCH

    def test_ohne_kursraum_wird_nicht_gesucht(self, monkeypatch):
        _weg(monkeypatch, anweisung.SEARCH)
        ergebnis = anweisung.resolve(None, [1], "nur die Kuehlung", 1000)
        assert ergebnis.text == "nur die Kuehlung"
        assert ergebnis.chunks is None
        assert ergebnis.way == anweisung.FILL


# --- classify: der Vor-Call ---------------------------------------------------

def _client(content):
    gefragt = []

    def create(model, messages, **kwargs):
        gefragt.append((messages, kwargs))
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    return client, gefragt


class TestVorcall:
    def test_thema_heisst_suchen(self, monkeypatch):
        client, gefragt = _client('{"art": "THEMA"}')
        monkeypatch.setattr(anweisung, "_get_llm_client", lambda: (client, "m", "p"))
        assert anweisung.classify("nur Kapitel 3") == anweisung.SEARCH
        assert "nur Kapitel 3" in gefragt[0][0][1]["content"]

    def test_stil_heisst_auffuellen(self, monkeypatch):
        client, _ = _client('{"art": "STIL"}')
        monkeypatch.setattr(anweisung, "_get_llm_client", lambda: (client, "m", "p"))
        assert anweisung.classify("leichte Fragen") == anweisung.FILL

    def test_unsinn_heisst_unsinn(self, monkeypatch):
        client, _ = _client('{"art": "UNSINN"}')
        monkeypatch.setattr(anweisung, "_get_llm_client", lambda: (client, "m", "p"))
        assert anweisung.classify("asdf qwertz") == anweisung.NONSENSE

    def test_unlesbare_antwort_heisst_auffuellen(self, monkeypatch):
        client, _ = _client("<think>hm</think> keine Ahnung")
        monkeypatch.setattr(anweisung, "_get_llm_client", lambda: (client, "m", "p"))
        assert anweisung.classify("nur Kapitel 3") == anweisung.FILL

    def test_ohne_anbieter_heisst_auffuellen(self, monkeypatch):
        def _kaputt():
            raise RuntimeError("kein Anbieter")

        monkeypatch.setattr(anweisung, "_get_llm_client", _kaputt)
        assert anweisung.classify("nur Kapitel 3") == anweisung.FILL


# --- clean und prompt_block ---------------------------------------------------

def test_clean_glaettet_und_kappt():
    assert anweisung.clean(None) == ""
    assert anweisung.clean("  nur \n\n Kapitel   3  ") == "nur Kapitel 3"
    assert len(anweisung.clean("x" * (anweisung.MAX_CHARS + 50))) == anweisung.MAX_CHARS


def test_prompt_block_ist_leer_ohne_anweisung():
    assert anweisung.prompt_block("") == ""
    assert anweisung.prompt_block("   ") == ""


def test_prompt_block_traegt_die_anweisung_und_den_waechter():
    block = anweisung.prompt_block("nur Kapitel 3")
    assert "nur Kapitel 3" in block
    assert "never overrides" in block
    assert "Never invent" in block


# --- spots_by_source: die Treffer je Quelle -----------------------------------

def test_prompt_block_on_the_search_way_keeps_everything_on_the_topic():
    block = anweisung.prompt_block("nur Zitierarten", narrowed=True)
    assert "nur Zitierarten" in block
    assert "must be about what the instruction names" in block
    # The count stays full, the model rephrases instead of drifting to another topic.
    assert "rather than switching to another topic" in block


def test_prompt_block_without_the_search_way_has_no_topic_clause():
    assert "must be about what the instruction names" not in anweisung.prompt_block("leichte Fragen")


def test_spots_are_grouped_per_source_in_hit_order():
    treffer = [
        {"source_id": 2, "page_number": 5, "content": "B"},
        {"source_id": 1, "page_number": 3, "content": "A"},
        {"source_id": 2, "page_number": 6, "content": "B2"},
        {"source_id": 1, "page_number": 1, "content": "  "},
    ]
    gruppen = anweisung.spots_by_source(treffer)
    assert list(gruppen) == [2, 1]
    assert [c["page_number"] for c in gruppen[2]] == [5, 6]
    # An empty spot carries nothing into the prompt and is left out.
    assert [c["page_number"] for c in gruppen[1]] == [3]


def test_no_spots_means_no_groups():
    assert anweisung.spots_by_source([]) == {}
