"""Gesprochene Termine aus Transkripten kommen im Zeitplan an.

Ein Vortrag sagt "der 3. Juli", der Kursplan schreibt "03.07.2026". Der gesprochene
Termin traegt also keine Jahreszahl, und die faellt im Code immer auf das laufende Jahr.

Sobald der Tag in diesem Jahr vorbei war, hielt die Klassifikation ihn fuer eine
Erinnerung an frueher und verwarf ihn. Am 13.08.2026 gemessen: alle vier gesprochenen
Termine der drei Vorlesungsvideos waren mit is_historical=true weg, im Zeitplan hingen
danach fast nur PDF-Quellen.

Der Ausweg ist ein Beleg statt einer Vermutung: steht derselbe Tag irgendwo MIT Jahr,
dann ist der gesprochene Termin dieselbe Veranstaltung und kein Rueckblick.
"""

import json
import types
from datetime import date

from src.features.ai_assistant.tasks.studio.schedule import _classify as mod

HEUTE = date(2026, 8, 13)


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


def _gesprochen(raw="3. Juli", md=(7, 3)):
    return {"date_raw": raw, "date_iso": None, "partial_date": md,
            "is_tbd": False, "context": f"Der {raw}, da ist die finale Deadline."}


def _geschrieben(iso="2026-07-03"):
    return {"date_raw": "03.07.2026", "date_iso": iso, "partial_date": None,
            "is_tbd": False, "context": "| Abgabe Hausarbeit | 03.07.2026 |"}


def _antwort(n):
    return {"results": [{"id": i, "keep": True, "title": "Abgabe Hausarbeit",
                         "type": "deadline"} for i in range(n)]}


# --- welche Tage sind mit Jahr belegt ----------------------------------------

def test_tage_aus_den_kandidaten_zaehlen():
    assert mod._dated_month_days([_geschrieben()], []) == {(7, 3)}


def test_tage_aus_schon_stehenden_eintraegen_zaehlen():
    eintraege = [{"due_date": date(2026, 4, 22), "title": "Sprechstunde"}]
    assert mod._dated_month_days([], eintraege) == {(4, 22)}


def test_eintraege_ohne_datum_zaehlen_nicht():
    assert mod._dated_month_days([], [{"due_date": None, "title": "Präsentation"}]) == set()


def test_gesprochene_termine_belegen_keinen_tag():
    """Sonst wuerde sich ein Transkript selbst zum Beleg erklaeren."""
    assert mod._dated_month_days([_gesprochen()], []) == set()


# --- was die Klassifikation zu sehen bekommt ---------------------------------

def _kandidaten_im_aufruf(calls):
    text = calls[0][1]["content"]
    return json.loads(text[text.index("Candidates:") + len("Candidates:"):])


def test_der_beleg_steht_am_gesprochenen_termin():
    client, calls = _make_client(_antwort(2))
    batch = [_gesprochen(), _geschrieben()]

    mod._classify_candidates(client, "m", batch, HEUTE, mod._dated_month_days(batch, []))

    gesprochen, geschrieben = _kandidaten_im_aufruf(calls)
    assert gesprochen["year_missing"] is True
    assert gesprochen["documented_with_year_elsewhere"] is True
    # der geschriebene Termin traegt sein Jahr selbst, er braucht die Marke nicht
    assert "documented_with_year_elsewhere" not in geschrieben


def test_ohne_beleg_keine_marke():
    client, calls = _make_client(_antwort(1))
    batch = [_gesprochen("15. April", (4, 15))]

    mod._classify_candidates(client, "m", batch, HEUTE, mod._dated_month_days(batch, []))

    assert "documented_with_year_elsewhere" not in _kandidaten_im_aufruf(calls)[0]


def test_ein_anderer_tag_belegt_nichts():
    client, calls = _make_client(_antwort(2))
    batch = [_gesprochen("15. April", (4, 15)), _geschrieben("2026-07-03")]

    mod._classify_candidates(client, "m", batch, HEUTE, mod._dated_month_days(batch, []))

    assert "documented_with_year_elsewhere" not in _kandidaten_im_aufruf(calls)[0]


def test_der_beleg_darf_aus_einem_frueheren_lauf_kommen():
    """Die PDF wurde gestern verarbeitet, das Video kommt heute dazu."""
    client, calls = _make_client(_antwort(1))
    batch = [_gesprochen()]
    eintraege = [{"due_date": date(2026, 7, 3), "title": "Abgabe Hausarbeit"}]

    mod._classify_candidates(client, "m", batch, HEUTE, mod._dated_month_days(batch, eintraege))

    assert _kandidaten_im_aufruf(calls)[0]["documented_with_year_elsewhere"] is True


def test_die_anfrage_sagt_die_wahrheit_ueber_das_jahr():
    """Sie versprach "next upcoming occurrence", der Code nimmt das laufende Jahr."""
    client, calls = _make_client(_antwort(1))

    mod._classify_candidates(client, "m", [_gesprochen()], HEUTE, set())

    frage = calls[0][1]["content"]
    assert "CURRENT calendar year" in frage
    assert "NEXT upcoming" not in frage


def test_ohne_belegliste_laeuft_alles_wie_vorher():
    client, calls = _make_client(_antwort(1))

    ergebnis = mod._classify_candidates(client, "m", [_gesprochen()], HEUTE)

    assert ergebnis[0]["keep"] is True
    assert "documented_with_year_elsewhere" not in _kandidaten_im_aufruf(calls)[0]
