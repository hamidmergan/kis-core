"""Aufgaben aus dem Vorrat holen und Neues einlagern.

Getestet wird die Verteilungslogik ueber mehrere Quellen und das Einlagern; die
Datenbankseite (eindeutiger Index, Zufall, Ausschluss des Gesehenen) haengt an echtem
Postgres und ist dort geprueft, nicht hier.
"""

import types

import pytest

from src.features.ai_assistant.tasks.language_training import _pool


# --- wer ueberhaupt mitmacht --------------------------------------------------

@pytest.mark.parametrize("tool", ["flashcards", "karteikarten", "quiz"])
def test_the_three_source_tools_use_the_pool(tool):
    assert _pool.uses_pool(tool, "source") is True


def test_the_grammar_tool_is_in_too():
    # Ihre Aufgaben haengen zusaetzlich am gewaehlten Thema, ihr Vorrat trennt deshalb
    # auch danach. Kleinere Vorraete, aber nie teurer als vorher.
    assert _pool.uses_pool("grammatik", "source") is True


def test_the_glossary_mode_stays_out():
    # Zieht aus einer fertigen Begriffsliste und hat das Problem gar nicht.
    assert _pool.uses_pool("quiz", "glossary") is False


# --- welches Niveau ------------------------------------------------------------

def test_without_an_adaptive_suffix_the_level_is_none(monkeypatch):
    """Der Zusatz ist genau dann leer, wenn eine der drei Schranken zu ist.

    Dann erzeugt das Werkzeug in seiner Grundformulierung, und die gehoert in den Vorrat
    ohne Niveau. So koennen Zusatz und Vorrat nicht auseinanderlaufen.
    """
    monkeypatch.setattr("src.database.get_user_language_level",
                        lambda _u: {"language_level": "B1"})
    assert _pool.pool_level("", 7) is None


def test_with_a_suffix_the_stored_level_decides(monkeypatch):
    monkeypatch.setattr("src.database.get_user_language_level",
                        lambda _u: {"language_level": "B1"})
    assert _pool.pool_level("... auf B1 ...", 7) == "B1"


def test_an_unreadable_level_falls_back_to_the_level_free_pool(monkeypatch):
    def boom(_u):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_user_language_level", boom)
    assert _pool.pool_level("...", 7) is None


# --- ziehen --------------------------------------------------------------------

def _stub_pool(monkeypatch, bestand: dict):
    """``bestand`` bildet source_id auf die Fronts ab, die dort liegen.

    Zustandslos, so wie die echte Abfrage. Die weiss nicht, was ein frueherer Aufruf
    schon geliefert hat: sie laesst nur weg, was in einem **gespeicherten** Satz steckt,
    und der entsteht erst am Ende des Auftrags. Ein Stub, der seinen Bestand aufbraucht,
    macht genau den Doppler unsichtbar, um den es hier geht.
    """
    gefragt = []

    def take(source_id, tool, level, user_id, limit, topic_id=None, exclude_ids=None, kinds=None):
        gefragt.append((source_id, limit, topic_id))
        raus = set(exclude_ids or ())
        vorrat = [f for f in bestand.get(source_id, []) if f"{source_id}-{f}" not in raus]
        return [{"id": f"{source_id}-{f}", "front": f, "back": ""} for f in vorrat[:limit]]

    monkeypatch.setattr("src.database.take_from_pool", take)
    monkeypatch.setattr("src.database.get_aia_source",
                        lambda u: {"id": int(u.removeprefix("u"))})
    return gefragt


def test_nothing_to_take_without_sources_or_count(monkeypatch):
    _stub_pool(monkeypatch, {})
    assert _pool.take([], "quiz", None, 1, 5) == []
    assert _pool.take(["u1"], "quiz", None, 1, 0) == []
    assert _pool.take(["u1"], "quiz", None, None, 5) == []


def test_the_take_is_spread_evenly_over_the_sources(monkeypatch):
    _stub_pool(monkeypatch, {1: list("abcdef"), 2: list("ghijkl"), 3: list("mnopqr")})
    out = _pool.take(["u1", "u2", "u3"], "quiz", None, 1, 6)
    fronts = [i["front"] for i in out]
    assert len(fronts) == 6
    # zwei aus jeder Quelle, nicht sechs aus der ersten
    assert len([f for f in fronts if f in "abcdef"]) == 2
    assert len([f for f in fronts if f in "ghijkl"]) == 2
    assert len([f for f in fronts if f in "mnopqr"]) == 2


def test_a_thin_source_lets_the_others_make_up_for_it(monkeypatch):
    """Das ersetzt die alte Ausgleichsrechnung im Kontext.

    Die hat der kleinsten Quelle erlaubt, allen anderen ihre Groesse aufzuzwingen: vier
    Buecher plus ein Handout drueckten den Kontext von 393.000 auf 87.000 Zeichen.
    """
    _stub_pool(monkeypatch, {1: ["a"], 2: list("bcdefgh")})
    out = _pool.take(["u1", "u2"], "quiz", None, 1, 6)
    assert len(out) == 6, "die volle Bestellung, obwohl Quelle 1 nur eine Aufgabe hat"


def test_an_empty_pool_yields_nothing_rather_than_failing(monkeypatch):
    _stub_pool(monkeypatch, {1: [], 2: []})
    assert _pool.take(["u1", "u2"], "quiz", None, 1, 5) == []


def test_never_more_than_ordered(monkeypatch):
    _stub_pool(monkeypatch, {1: list("abcdefghij")})
    assert len(_pool.take(["u1"], "quiz", None, 1, 3)) == 3


def test_a_failing_pool_read_means_everything_gets_generated(monkeypatch):
    # Der Vorrat ist eine Abkuerzung, keine Voraussetzung.
    def boom(*_a, **_k):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_aia_source", boom)
    assert _pool.take(["u1"], "quiz", None, 1, 5) == []


def test_a_pool_smaller_than_the_order_does_not_repeat_itself(monkeypatch):
    """Der Normalfall bei einem wachsenden Vorrat: er gibt weniger her als bestellt.

    Die zweite Runde fragt dieselbe Quelle noch einmal. Ohne Ausschluss liefert sie
    dieselben Aufgaben, und der Satz haette jede zweimal.
    """
    _stub_pool(monkeypatch, {1: list("abcd")})
    fronts = [i["front"] for i in _pool.take(["u1"], "quiz", None, 1, 10)]
    assert fronts == list("abcd"), f"jede Aufgabe genau einmal, nicht {fronts}"


def test_the_second_round_brings_new_tasks_and_not_the_first_ones_again(monkeypatch):
    _stub_pool(monkeypatch, {1: list("abcdefgh"), 2: []})
    fronts = [i["front"] for i in _pool.take(["u1", "u2"], "quiz", None, 1, 6)]
    assert len(fronts) == len(set(fronts)), f"Doppler im selben Satz: {fronts}"
    assert len(fronts) == 6, "Quelle 1 hat genug, die leere Quelle darf das nicht kosten"


def test_the_same_task_from_two_sources_counts_once(monkeypatch):
    """Zwei Quellen koennen dieselbe Aufgabe im Vorrat haben.

    Der eindeutige Index sitzt je Quelle, ueber die Quellengrenze hinweg faengt er
    nichts ab. Zwei Folienstaende zum selben Thema reichen dafuer.
    """
    _stub_pool(monkeypatch, {1: ["a"], 2: ["a"]})
    fronts = [i["front"] for i in _pool.take(["u1", "u2"], "quiz", None, 1, 2)]
    assert fronts == ["a"], f"derselbe Satz zweimal in einer Uebung: {fronts}"


def test_an_exhausted_source_is_not_asked_again(monkeypatch):
    """Wer weniger liefert als bestellt, ist leer. Eine zweite Abfrage kostet nur."""
    gefragt = _stub_pool(monkeypatch, {1: ["a"], 2: ["b"]})
    _pool.take(["u1", "u2"], "quiz", None, 1, 6)
    assert [q[0] for q in gefragt] == [1, 2], "keine zweite Runde auf leere Vorraete"


def test_pool_rows_carry_their_reference(monkeypatch):
    _stub_pool(monkeypatch, {1: ["a"]})
    out = _pool.take(["u1"], "quiz", None, 1, 1)
    assert out[0]["pool_item_id"] == "1-a"


# --- einlagern -----------------------------------------------------------------

def _ctx(**quellen):
    return types.SimpleNamespace(source_by_name=quellen)


def _stub_store(monkeypatch, platz=100):
    gespeichert = []

    def add(source_id, tool, level, items, fingerprints, topic_id=None):
        gespeichert.append((source_id, tool, level, [i["front"] for i in items], topic_id))
        return [f"neu-{f}" for f in fingerprints]

    monkeypatch.setattr("src.database.add_pool_items", add)
    monkeypatch.setattr("src.database.pool_size", lambda *a: 0)
    monkeypatch.setattr("src.database.POOL_MAX_ITEMS", platz, raising=False)
    return gespeichert


def test_generated_items_go_into_the_pool_of_their_source(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf"},
             {"front": "b", "source_label": "B.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}, "B.pdf": {"id": 2}}), "quiz", "B1")

    assert sorted(gespeichert) == [(1, "quiz", "B1", ["a"], None),
                                  (2, "quiz", "B1", ["b"], None)]
    assert items[0]["pool_item_id"] == "neu-a"


def test_an_item_without_a_source_stays_out_of_the_pool(monkeypatch):
    # Es steht nicht fest, zu welcher Quelle sie gehoeren wuerde. Im Satz bleibt sie und
    # traegt ihren Inhalt dort weiter selbst.
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "Unbekannt.pdf"}, {"front": "b"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)

    assert gespeichert == []
    assert "pool_item_id" not in items[0]


def test_what_came_from_the_pool_is_not_stored_again(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf", "pool_item_id": 5}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)
    assert gespeichert == []


def test_a_full_pool_stops_taking_more(monkeypatch):
    gespeichert = []
    monkeypatch.setattr("src.database.add_pool_items",
                        lambda s, t, l, items, f, tid=None: gespeichert.append(len(items)) or [1] * len(items))
    monkeypatch.setattr("src.database.pool_size", lambda *a: 1000)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)
    assert gespeichert == []


def test_a_failing_store_does_not_reach_the_caller(monkeypatch):
    # Einlagern ist eine Verbesserung fuer den naechsten Aufruf, keine Voraussetzung
    # fuer diesen. Der Satz ist fertig und wird gespeichert.
    def boom(*_a, **_k):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.pool_size", boom)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)  # darf nicht werfen
    assert "pool_item_id" not in items[0]


def test_storing_nothing_is_harmless(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    _pool.store([], _ctx(), "quiz", None)
    assert gespeichert == []


# --- Grammatik trennt zusaetzlich nach Thema --------------------------------------

def test_the_grammar_pool_is_asked_per_topic(monkeypatch):
    gefragt = _stub_pool(monkeypatch, {1: list("abc")})
    _pool.take(["u1"], "grammatik", None, 1, 2, topic_id=42)
    assert all(eintrag[2] == 42 for eintrag in gefragt), \
        "ohne Thema kaeme eine Passiv-Aufgabe in einer Konjunktiv-Uebung heraus"


def test_grammar_items_are_stored_under_their_topic(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "Der Satz wird gebildet.", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "grammatik", "B1", topic_id=42)
    assert gespeichert == [(1, "grammatik", "B1", ["Der Satz wird gebildet."], 42)]


def test_a_tool_without_a_topic_stores_none(monkeypatch):
    gespeichert = _stub_store(monkeypatch)
    items = [{"front": "a", "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "quiz", None)
    assert gespeichert[0][4] is None


# --- Fingerabdruck: laengensicher fuer den Btree-Index --------------------------

def test_a_very_long_front_still_gets_a_storable_fingerprint(monkeypatch):
    # Der eindeutige Index auf aia_exercise_pool ist ein Btree, dessen Zeilen nur rund
    # 2700 Byte gross sein duerfen. Beim Lueckentext ist "front" ein ganzer Text und
    # kann das reissen. Ohne die Kappung in _fingerprint() wuerde das INSERT dann mit
    # einer Ausnahme scheitern, store() faengt sie ab und loggt nur eine Warnung, und
    # der Vorrat fuellte sich fuer dieses Werkzeug nie, obwohl nichts sichtbar kaputt
    # wirkt.
    fingerprints_gesehen = []

    def add(source_id, tool, level, items, fingerprints, topic_id=None):
        fingerprints_gesehen.extend(fingerprints)
        return [f"neu-{f}" for f in fingerprints]

    monkeypatch.setattr("src.database.add_pool_items", add)
    monkeypatch.setattr("src.database.pool_size", lambda *a: 0)
    langer_text = "Die Anlage arbeitet seit gestern wieder ohne Stoerung. " * 100
    items = [{"front": langer_text, "source_label": "A.pdf"}]
    _pool.store(items, _ctx(**{"A.pdf": {"id": 1}}), "wortschatz", None)

    assert len(fingerprints_gesehen) == 1
    # Fester Wert und NICHT _pool._FINGERPRINT_HASH_THRESHOLD: die Konstante ist genau
    # das, was dieser Test bewachen soll. Ein Vergleich gegen sie selbst wuerde gruen
    # bleiben, auch wenn jemand sie ueber die Btree-Grenze anhoebe (rund 2700 Byte in
    # der Praxis, siehe Kommentar an der Konstante) und der Fehler wieder einzoege.
    assert len(fingerprints_gesehen[0].encode("utf-8")) <= 2700
    # Kommt trotzdem an: store() traegt die vom Aufruf zurueckgegebene id ein, genau
    # wie bei jedem anderen Werkzeug auch.
    assert items[0]["pool_item_id"] == f"neu-{fingerprints_gesehen[0]}"


def test_a_short_front_keeps_its_established_fingerprint():
    # Bestehende Vorratszeilen wurden mit item_key() roh gespeichert. Aenderte sich der
    # Fingerabdruck kurzer Fronten mit, bekaeme derselbe Inhalt vor und nach dieser
    # Aenderung zwei verschiedene Werte, und der Dopplerschutz liesse fuer jede
    # bestehende Zeile genau einen Doppler durch.
    kurz = "Der Satz wird gebildet."
    assert _pool._fingerprint(kurz) == _pool.item_key(kurz)
