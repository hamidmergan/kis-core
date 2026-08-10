"""Die dritte Aufgabenart des Quiz: Richtig/Falsch.

Richtig/Falsch war bis zum 2026-08-10 die einzige Form des Werkzeugs Hörverstehen. Mit
dessen Abschaffung zieht sie ins Quiz um, dort als dritte Art neben Verständnisfrage und
Lückensatz. Die Regeln aus der Testkonstruktion sind wörtlich mitgekommen, sie waren am
echten Lauf nachgemessen.
"""

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
    """Gezählte Vorgabe statt 'etwa ein Drittel'. Der Rest geht der Reihe nach an
    Verständnisfrage, Lückensatz, Richtig/Falsch."""
    assert mod._split_counts(bestellt) == erwartet


@pytest.mark.parametrize("bestellt", [1, 2, 3, 5, 7, 10, 15, 20])
def test_aufteilung_ergibt_immer_die_bestellte_zahl(bestellt):
    assert sum(mod._split_counts(bestellt)) == bestellt


# --- die Zeile, die aus einer Modellantwort entsteht -------------------------

def test_alle_drei_arten_landen_in_derselben_zeilenform(monkeypatch):
    """Verständnisfrage, Lückensatz und Richtig/Falsch teilen sich eine Zeilenform.
    Die Ansicht unterscheidet sie an der Anzahl der Optionen und am ___ im Text, nicht
    an einem eigenen Feld."""
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
    """Die Beschriftung kommt aus dem Code. Das Modell schrieb sonst mal 'Wahr', mal
    klein, und die Ansicht zeigt die Optionen unverändert an."""
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
    """Der Prompt bestellt zwei Optionen, das Modell liefert gelegentlich trotzdem vier.
    Beim Hörverstehen war genau das der Grund für diese Prüfung im Code."""
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
    """Die Zeichenkette "true" ist kein Urteil. Ohne diese Prüfung stünde die Aufgabe
    mit correct_idx=1 im Satz, also mit der falschen Lösung."""
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
    """Das Musterbeispiel steht hinter dem Quellmaterial, damit es als Form wirkt und
    nicht als Aufgabe 1 abgeschrieben wird. Beim Grammatik-Quiz wurde es trotzdem
    abgeschrieben, deshalb wird es zusätzlich im Code gesperrt."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    musteraussage = mod._EXAMPLE_ITEMS[0][0]
    content = json.dumps({"title": "T", "exercises": [
        {"statement": musteraussage, "answer": True},
        {"statement": "Eine eigene Aussage.", "answer": True},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 2, locale="de")
    assert [i["front"] for i in items] == ["Eine eigene Aussage."]


# --- was im Prompt steht ----------------------------------------------------

def test_prompt_bestellt_gezaehlte_anteile(monkeypatch):
    """Nicht 'roughly half and half'. Beim Grammatik-Quiz drillte das Modell auf eine
    Absichtserklärung hin zehnmal dieselbe Form."""
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
    """Ohne sie ist die Aufgabe ohne die Quelle lösbar und das Modell schreibt fast nur
    wahre Sätze. Am 2026-08-09 gemessen: mit den Regeln hielt es sich an etwa 13 von 15."""
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
    """Sie verboten genau das, was das Quiz will: Definitionen und Fachbegriffe."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]})
    client, calls = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 15, locale="de")
    system = _system_of(calls)
    assert "NOT A KNOWLEDGE QUIZ" not in system
    assert "tests vocabulary" not in system


def test_musterbeispiele_stehen_hinter_dem_quellmaterial(monkeypatch):
    """Diese Reihenfolge entschied beim Grammatik-Quiz über 0 gegen 8 brauchbare
    Aufgaben: davor wird das Beispiel als Aufgabe 1 abgeschrieben, dahinter wirkt es
    als Form."""
    monkeypatch.setattr(mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Q", "options": ["a", "b", "c", "d"], "correct_idx": 0}]})
    client, calls = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 15, locale="de")
    system, user = _system_of(calls), _user_of(calls)
    beispiel = mod._EXAMPLE_ITEMS[0][0]
    assert beispiel not in system
    assert user.index("ctx") < user.index(beispiel)


# --- Zuordnung der Quellen-Chips --------------------------------------------

def test_zwei_zuordnungslaeufe_je_aufgabenart(monkeypatch):
    """Ankreuzen über die reine Suche, Richtig/Falsch über die gestaffelte Zuordnung.

    Eine Richtig/Falsch-Aussage ist per Regel immer umformuliert. Beim Hörverstehen
    wurde deshalb von reiner Suche auf die gestaffelte Zuordnung umgestellt, weil sonst
    die halbe Übung ohne Quellenangabe dastand.
    """
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
    # Suchtext beim Ankreuzen: Frage plus Antwort. Bei Richtig/Falsch die Aussage allein,
    # nie plus "Richtig", sonst sucht die Zuordnung nach der festen Beschriftung.
    assert mc_claims == ["Was ist X? b"]
    assert tf_claims == ["Eine Aussage über die Quelle."]
    assert "Richtig" not in tf_claims[0]
    # Was das Modell selbst genannt hat, geht an die gestaffelte Zuordnung mit.
    assert tf_items[0]["_source_label"] == "Datei.pdf"
    assert tf_items[0]["_page"] == 9


def test_die_markierung_der_aufgabenart_wird_wieder_entfernt(monkeypatch):
    """_tf ist nur für die Zuordnung da. Bliebe es stehen, wanderte ein internes Feld
    in den Vorrat und in den fertigen Satz."""
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: None)
    monkeypatch.setattr(mod, "attach_chips_cited", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"statement": "Eine Aussage.", "answer": True},
    ]})
    client, _ = _make_client(content)
    items, _ = mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert "_tf" not in items[0]


def test_ein_satz_ganz_ohne_richtig_falsch_ruft_nur_die_suche(monkeypatch):
    """Bei sehr kleinen Sätzen fällt Richtig/Falsch weg. Dann darf die gestaffelte
    Zuordnung gar nicht erst laufen, sie kostet sonst einen Suchlauf über nichts."""
    gerufen = []
    monkeypatch.setattr(mod, "attach_chips", lambda *a, **k: gerufen.append("mc"))
    monkeypatch.setattr(mod, "attach_chips_cited", lambda *a, **k: gerufen.append("tf"))
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1}]})
    client, _ = _make_client(content)
    mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert gerufen == ["mc"]
