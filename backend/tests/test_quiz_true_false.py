"""True/false as the third exercise kind of the quiz."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training import _source_mc as mod


def _make_client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _ctx():
    return types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")


def _system_of(calls):
    return calls[0][0]["content"]


def _user_of(calls):
    return calls[0][1]["content"]


@pytest.mark.parametrize("bestellt,erwartet", [
    (15, (5, 5, 5)),
    (10, (4, 3, 3)),
    (5, (2, 2, 1)),
    (3, (1, 1, 1)),
    (2, (1, 1, 0)),
    (1, (1, 0, 0)),
])
def test_aufteilung_der_anzahl(bestellt, erwartet):
    """A counted requirement instead of a rough statement."""
    assert mod._split_counts(bestellt) == erwartet


@pytest.mark.parametrize("bestellt", [1, 2, 3, 5, 7, 10, 15, 20])
def test_aufteilung_ergibt_immer_die_bestellte_zahl(bestellt):
    assert sum(mod._split_counts(bestellt)) == bestellt


# --- the row that comes out of a model answer --------------------------------

def test_alle_drei_arten_landen_in_derselben_zeilenform(monkeypatch):
    """The three kinds share one row shape."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1},
        {"sentence": "Der Prozess der ___ senkt den Druck.",
         "options": ["a", "b", "c", "d"], "correct_idx": 2},
        {"statement": "Die Anlage arbeitet bei Frost weniger wirtschaftlich.",
         "answer": True},
        {"statement": "Die Leistungszahl steigt bei Frost.", "answer": False},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 4, locale="de")
    assert [i["front"] for i in items] == [
        "Was ist X?",
        "Der Prozess der ___ senkt den Druck.",
        "Die Anlage arbeitet bei Frost weniger wirtschaftlich.",
        "Die Leistungszahl steigt bei Frost.",
    ]
    assert [i["back"] for i in items] == ["b", "c", "Richtig", "Falsch"]
    assert items[2]["options"] == ["Richtig", "Falsch"]
    assert items[2]["correct_idx"] == 0
    assert items[3]["correct_idx"] == 1


def test_beschriftung_folgt_der_sprache(monkeypatch):
    """The label comes from the code, not from the model."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"statement": "The plant runs less efficiently in frost.", "answer": True},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="en",
                                           language="English")
    assert items[0]["options"] == ["True", "False"]
    assert items[0]["back"] == "True"


def test_richtig_falsch_mit_vier_optionen_faellt_durch(monkeypatch):
    """Four options still occur and have to be rejected."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"statement": "Gute Aussage.", "answer": True},
        {"statement": "Vier Optionen.", "answer": True,
         "options": ["a", "b", "c", "d"], "correct_idx": 0},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 2, locale="de")
    assert [i["front"] for i in items] == ["Gute Aussage."]


def test_urteil_muss_ein_echter_boolescher_wert_sein(monkeypatch):
    """A string 'true' is no verdict and would yield the wrong answer."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"statement": "Gute Aussage.", "answer": False},
        {"statement": "Urteil als Text.", "answer": "true"},
        {"statement": "Urteil fehlt ganz."},
        {"statement": "", "answer": True},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 4, locale="de")
    assert [i["front"] for i in items] == ["Gute Aussage."]


def test_abgeschriebene_musteraufgabe_faellt_durch(monkeypatch):
    """The sample example sits behind the material and is barred in the code as well."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    musteraussage = mod._EXAMPLE_ITEMS[0][0]
    content = json.dumps({"title": "T", "exercises": [
        {"statement": musteraussage, "answer": True},
        {"statement": "Eine eigene Aussage.", "answer": True},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 2, locale="de")
    assert [i["front"] for i in items] == ["Eine eigene Aussage."]


# --- what is in the prompt --------------------------------------------------

def test_prompt_bestellt_gezaehlte_anteile(monkeypatch):
    """A statement of intent is not enough, it takes a number."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]})
    client, calls = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 15, locale="de")
    system = _system_of(calls)
    assert "5 comprehension" in system
    assert "5 gap" in system
    assert "5 true/false" in system
    assert "roughly half and half" not in system


def test_prompt_traegt_die_regeln_der_testkonstruktion(monkeypatch):
    """Without the rules the exercise would be solvable without the source."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]})
    client, calls = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 15, locale="de")
    system = _system_of(calls)
    assert "About half of the statements must be false" in system
    assert "Never use absolute words" in system
    assert "No negation inside the statement" in system
    assert "changing exactly one detail" in system


def test_die_beiden_verbote_des_hoerverstehens_bleiben_draussen(monkeypatch):
    """They forbade exactly what the quiz wants: definitions and technical terms."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]})
    client, calls = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 15, locale="de")
    system = _system_of(calls)
    assert "NOT A KNOWLEDGE QUIZ" not in system
    assert "tests vocabulary" not in system


def test_musterbeispiele_stehen_hinter_dem_quellmaterial(monkeypatch):
    """Before the material the example gets copied, behind it it works as a form."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]})
    client, calls = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 15, locale="de")
    system, user = _system_of(calls), _user_of(calls)
    beispiel = mod._EXAMPLE_ITEMS[0][0]
    assert beispiel not in system
    assert user.index("ctx") < user.index(beispiel)


# --- attribution of the source chips ----------------------------------------

def test_zwei_zuordnungslaeufe_je_aufgabenart(monkeypatch):
    """Multiple choice via the pure search, true/false layered."""
    gesehen = {}
    monkeypatch.setattr(
        mod, "attach_chips",
        lambda items, claims, ctx, **k: gesehen.update(mc=(list(items), list(claims))))
    monkeypatch.setattr(
        mod, "attach_chips_cited",
        lambda items, claims, ctx, **k: gesehen.update(tf=(list(items), list(claims))))
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1},
        {"statement": "Eine Aussage über die Quelle.", "answer": True,
         "source_label": "Datei.pdf", "page_number": 9},
    ]})
    client, _ = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 2, locale="de")

    mc_items, mc_claims = gesehen["mc"]
    tf_items, tf_claims = gesehen["tf"]
    assert [i["front"] for i in mc_items] == ["Was ist X?"]
    assert [i["front"] for i in tf_items] == ["Eine Aussage über die Quelle."]
    # The search runs on the statement alone, never plus the fixed label.
    assert mc_claims == ["Was ist X? b"]
    assert tf_claims == ["Eine Aussage über die Quelle."]
    assert "Richtig" not in tf_claims[0]
    # What the model named itself goes along to the layered attribution.
    assert tf_items[0]["_source_label"] == "Datei.pdf"
    assert tf_items[0]["_page"] == 9


def test_die_markierung_der_aufgabenart_wird_wieder_entfernt(monkeypatch):
    """_tf exists only for the attribution and must not travel into the pool."""
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    monkeypatch.setattr(mod, "attach_chips_cited", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"statement": "Eine Aussage.", "answer": True},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert "_tf" not in items[0]


def test_ein_satz_ganz_ohne_richtig_falsch_ruft_nur_die_suche(monkeypatch):
    """Without true/false the layered attribution must not run at all."""
    gerufen = []
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: gerufen.append("mc"))
    monkeypatch.setattr(mod, "attach_chips_cited", lambda *a, **k: gerufen.append("tf"))
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1}]})
    client, _ = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert gerufen == ["mc"]


def test_das_modell_liest_kurzzeichen_und_die_aussage_behaelt_ihre_datei(monkeypatch):
    """Ein Dateiname kostet bis zu 25 Token je Aufgabe, das Modell schreibt Q1 und die Belegprüfung sieht den Namen."""
    gesehen = {}
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    monkeypatch.setattr(
        mod, "attach_chips_cited",
        lambda items, claims, ctx, **k: gesehen.update(tf=[dict(i) for i in items]))
    content = json.dumps({"title": "T", "exercises": [
        {"statement": "Eine Aussage über die Quelle.", "answer": True,
         "source_label": "Q1", "page_number": 9},
    ]})
    client, calls = _make_client(content)
    ctx = types.SimpleNamespace(source_hint="Quelle", multi_label="T",
                                context="[02_Seminar.pdf, S. 9] Inhalt",
                                source_by_name={"02_Seminar.pdf": {"id": 1}})
    mod.generate_mc_from_source(client, "m", ctx, 1, locale="de")

    assert "02_Seminar.pdf" not in json.dumps(calls[0], ensure_ascii=False)
    assert "[Q1, S. 9] Inhalt" in calls[0][1]["content"]
    assert gesehen["tf"][0]["_source_label"] == "02_Seminar.pdf"
    assert gesehen["tf"][0]["_page"] == 9
