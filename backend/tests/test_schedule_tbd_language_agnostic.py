"""Termine ohne festes Datum, unabhaengig von der Sprache des Dokuments.

Der Zeitplan erkannte "nach Vereinbarung" ueber eine feste Phrasenliste im Code, die nur
Deutsch und Englisch kennt. Ein tuerkisches oder spanisches Dokument verlor damit genau
die Zeilen ohne Datum. Die Liste bleibt als schneller Weg bestehen, jeder Chunk ohne
Treffer geht zusaetzlich an das Modell.

Die Bedingung an den Fund des Modells: die genannte Stelle muss woertlich im Text
stehen. Sonst zeigt der Eintrag spaeter auf nichts.
"""

import json
import types

from src.features.ai_assistant.tasks.studio.schedule import _candidates as cand_mod
from src.features.ai_assistant.tasks.studio.schedule import _discover as mod


def _make_client(payload):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = payload if isinstance(payload, str) else json.dumps(payload)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _src():
    return {"id": 1, "uuid": "u-1", "filename": "plan.pdf"}


def _chunks(*texts):
    return [
        {"id": i, "content": t, "page_number": i + 1, "start_time": None}
        for i, t in enumerate(texts)
    ]


# --- die Stelle im Text wiederfinden -----------------------------------------

def test_stelle_wird_woertlich_gefunden():
    text = "Ders plani: Sunum tarihleri daha sonra duyurulacak."
    found = mod._locate(text, "Sunum tarihleri daha sonra duyurulacak")
    assert found is not None
    assert found[0] == 12
    assert text[found[0]:found[1]] == "Sunum tarihleri daha sonra duyurulacak"


def test_stelle_wird_auch_bei_anderer_schreibung_gefunden():
    text = "Fecha a convenir con el profesor"
    assert mod._locate(text, "fecha a convenir") == (0, 16)


def test_zeilenumbruch_im_chunk_bricht_die_suche_nicht():
    """Im Chunk steht ein Umbruch, wo das Modell ein Leerzeichen geschrieben hat."""
    text = "Termine\nnach   Vereinbarung mit dem Dozenten"
    found = mod._locate(text, "Termine nach Vereinbarung")
    assert found is not None
    assert text[found[0]:found[1]] == "Termine\nnach   Vereinbarung"


def test_erfundene_stelle_wird_verworfen():
    assert mod._locate("Klausur am 12.05.2026", "Termin nach Absprache") is None


def test_leere_und_ueberlange_stelle_werden_verworfen():
    assert mod._locate("irgendein Text", "") is None
    assert mod._locate("x" * 500, "x" * 200) is None


# --- die Anfrage an das Modell -----------------------------------------------

def test_ohne_modell_bleibt_es_bei_der_phrasenliste():
    assert mod._discover_in_blocks(None, "m", [(0, "tarih daha sonra duyurulacak")]) == {}


def test_zu_kurze_bloecke_werden_gar_nicht_erst_geschickt():
    client, calls = _make_client({"results": []})
    mod._discover_in_blocks(client, "m", [(0, "Folie 3"), (1, "Seite 4")])
    assert calls == []


def test_bloecke_werden_nach_zeichenzahl_gebuendelt():
    blocks = [(i, "x" * 1000) for i in range(40)]
    batches = mod._batches(blocks)
    assert all(sum(len(t) for _i, t in b) <= mod._MAX_CHARS_PER_CALL for b in batches)
    assert sum(len(b) for b in batches) == 40


def test_antwort_zu_fremden_bloecken_wird_ignoriert():
    client, _ = _make_client({"results": [
        {"id": 99, "phrase": "erfunden"},
        {"id": 0, "phrase": "tarih daha sonra duyurulacak"},
    ]})
    found = mod._discover_in_blocks(client, "m", [(0, "Sunum tarihi: tarih daha sonra duyurulacak")])
    assert found[0]["tbd"] == "tarih daha sonra duyurulacak"
    assert 99 not in found


def test_fehler_beim_modell_laesst_den_zeitplan_weiterlaufen():
    def create(model, messages, **kwargs):
        raise RuntimeError("Anbieter down")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    assert mod._discover_in_blocks(client, "m", [(0, "x" * 100)]) == {}


# --- was daraus im Zeitplan wird ---------------------------------------------

def test_tuerkischer_termin_ohne_datum_wird_zum_kandidaten(monkeypatch):
    chunks = _chunks("Sunum tarihleri daha sonra duyurulacak.\nSinav: 12.05.2026")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"results": [
        {"id": 0, "phrase": "Sunum tarihleri daha sonra duyurulacak"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    tbd = [c for c in out if c["is_tbd"]]
    assert len(tbd) == 1
    assert tbd[0]["date_raw"] == "Sunum tarihleri daha sonra duyurulacak"
    assert tbd[0]["date_iso"] is None
    assert tbd[0]["page_number"] == 1
    # das Datum im selben Chunk bleibt ein eigener Kandidat
    assert any(c["date_iso"] == "2026-05-12" for c in out)


def test_erfundene_stelle_erzeugt_keinen_eintrag(monkeypatch):
    chunks = _chunks("Die Vorlesung findet woechentlich statt und wird aufgezeichnet.")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"results": [{"id": 0, "phrase": "Termin nach Absprache"}]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert [c for c in out if c["is_tbd"]] == []


def test_die_phrasenliste_schlaegt_das_modell(monkeypatch):
    """Findet die Liste die Stelle, gilt ihr Treffer, auch wenn das Modell etwas anderes
    meldet. Der Chunk geht trotzdem in die Anfrage, denn dort wird auch nach
    ausgeschriebenen Daten gesucht, und die braucht jeder Chunk."""
    chunks = _chunks("Sprechstunde nach Vereinbarung, Anmeldung im Sekretariat")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, calls = _make_client({"results": [
        {"id": 0, "phrase": "Anmeldung im Sekretariat"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert len(calls) == 1
    assert [c["date_raw"] for c in out if c["is_tbd"]] == ["nach Vereinbarung"]


def test_ohne_modell_arbeitet_die_kandidatensuche_wie_vorher(monkeypatch):
    chunks = _chunks("Sprechstunde nach Absprache", "tarih daha sonra duyurulacak")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert [c["date_raw"] for c in out if c["is_tbd"]] == ["nach Absprache"]


# --- Datum in der Nachbarspalte ----------------------------------------------
#
# Aus einem echten Kursplan (Quelle 2 im Testbestand). Die erste Zeile traegt ihr Datum
# in der naechsten Spalte, das "tba" meint dort den noch offenen INHALT. Die zweite
# Zeile hat in der Datumsspalte gar kein Datum, sie ist der echte offene Termin.

ZEILE_MIT_DATUM = (
    "| Online-Präsenz: tba, mgl. Schreibwerkstatt, Poster         "
    "| 27.06.2026, 10:00-14.30 Uhr                              |                       |"
)
ZEILE_OHNE_DATUM = (
    "| Präsentationen (online)                                    "
    "| während der Prüfungswochen (wird individuell vereinbart) |                       |"
)


def test_tba_neben_dem_datum_ist_kein_offener_termin(monkeypatch):
    """Zwei Schutzwaende: das Kuerzel steht nicht mehr in der Phrasenliste, und selbst
    wenn das Modell die Zeile meldet, faellt sie ueber das Datum in der Nachbarspalte."""
    chunks = _chunks(ZEILE_MIT_DATUM)
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"results": [{"id": 0, "phrase": "Online-Präsenz: tba"}]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert [c for c in out if c["is_tbd"]] == []
    assert any(c["date_iso"] == "2026-06-27" for c in out)


def test_abgeschnittene_tba_zeile_ergibt_keinen_eintrag_mehr(monkeypatch):
    """Der Chunker schneidet die Tabellenzeile mitten durch, das Datum liegt im
    Nachbar-Chunk. Genau daraus entstand der falsche Eintrag "Online-Präsenz:
    Schreibwerkstatt" ohne Datum. Ohne das Kuerzel in der Liste passiert nichts mehr."""
    chunks = _chunks("| Anfertigen der Hausarbeit |\n| Online-Präsenz: tba, mgl. Schreibwerkstatt,")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert [c for c in out if c["is_tbd"]] == []


def test_zeile_ohne_datum_bleibt_ein_offener_termin(monkeypatch):
    """Die Phrasenliste kennt "wird individuell vereinbart" nicht, im echten Lauf kam
    diese Zeile vom Modell. Genau die soll uebrig bleiben."""
    chunks = _chunks(ZEILE_OHNE_DATUM)
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"results": [
        {"id": 0, "phrase": "während der Prüfungswochen (wird individuell vereinbart)"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert len([c for c in out if c["is_tbd"]]) == 1


def test_beide_zeilen_zusammen_ergeben_genau_einen_offenen_termin(monkeypatch):
    """Das verworfene "tba" darf den Chunk nicht blockieren: die zweite Zeile muss noch
    beim Modell ankommen."""
    chunks = _chunks(ZEILE_MIT_DATUM + "\n" + ZEILE_OHNE_DATUM)
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"results": [
        {"id": 0, "phrase": "während der Prüfungswochen (wird individuell vereinbart)"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    tbd = [c for c in out if c["is_tbd"]]
    assert len(tbd) == 1
    assert "individuell vereinbart" in tbd[0]["raw_quote"]


def test_fliesstext_mit_datum_verliert_seinen_offenen_termin_nicht(monkeypatch):
    """Ein Transkript-Chunk hat keine Zeilenumbrueche. Ein Datum irgendwo im selben Chunk
    darf den offenen Termin nicht abraeumen, es fehlt die Spaltengrenze."""
    chunks = _chunks(
        "Am 27.06.2026 machen wir die Schreibwerkstatt und die Präsentationen "
        "werden dann später individuell vereinbart, das machen wir per Mail."
    )
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)
    client, _ = _make_client({"results": [
        {"id": 0, "phrase": "Präsentationen werden dann später individuell vereinbart"},
    ]})

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert len([c for c in out if c["is_tbd"]]) == 1


def test_hoechstens_ein_termin_ohne_datum_je_chunk(monkeypatch):
    chunks = _chunks("Sprechstunde nach Absprache, Kolloquium nach Vereinbarung")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert len([c for c in out if c["is_tbd"]]) == 1
