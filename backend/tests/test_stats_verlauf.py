"""History: chat, tools, exercises and joins mixed, newest first, online times separate."""
from datetime import date, datetime

from src.features.stats import detail

NUTZER = 12

REIHE = [
    {
        "art": "chat", "modul": "Werkstoffkunde 2",
        "text": "Wie funktioniert ein Verbundwerkstoff und was macht ihn stabiler als reines "
                "Metall bei hohen Temperaturen und starker mechanischer Belastung ueber Jahre?",
        "werkzeug": None, "status": None, "wann": datetime(2026, 8, 29, 14, 32),
    },
    {
        "art": "werkzeug", "modul": None, "text": "vortrag.mp4",
        "werkzeug": "screencast", "status": "success", "wann": datetime(2026, 8, 29, 10, 0),
    },
    {
        "art": "uebung", "modul": "Werkstoffkunde 2", "text": None,
        "werkzeug": "quiz", "status": None, "wann": datetime(2026, 8, 28, 9, 0),
    },
    {
        "art": "beitritt", "modul": "Werkstoffkunde 2", "text": None,
        "werkzeug": None, "status": "student", "wann": datetime(2026, 8, 1, 8, 0),
    },
]

# 29th: two sessions with a gap between. 28th: a single hour.
PRAESENZ = [
    {"day": date(2026, 8, 29), "hour": 14},
    {"day": date(2026, 8, 29), "hour": 13},
    {"day": date(2026, 8, 29), "hour": 9},
    {"day": date(2026, 8, 28), "hour": 20},
]


class _Cursor:
    def __init__(self, reihe, praesenz, calls):
        self._reihe, self._praesenz = reihe, praesenz
        self._calls, self._sql = calls, ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        self._calls.append((self._sql, params))

    def fetchone(self):
        return None

    def fetchall(self):
        if "user_presence" in self._sql:
            return [dict(p) for p in self._praesenz]
        return [dict(r) for r in self._reihe]


class _Conn:
    def __init__(self, reihe, praesenz, calls):
        self._reihe, self._praesenz, self._calls = reihe, praesenz, calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _Cursor(self._reihe, self._praesenz, self._calls)


def lauf(monkeypatch, vor=None, reihe=REIHE, praesenz=PRAESENZ):
    calls: list[tuple] = []
    monkeypatch.setattr(detail, "get_connection", lambda: _Conn(reihe, praesenz, calls))
    return detail.user_verlauf(NUTZER, vor), calls


def test_die_vier_arten_kommen_zusammen(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert [e["kind"] for e in daten["events"]] == ["chat", "werkzeug", "uebung", "beitritt"]


def test_chat_text_wird_gekuerzt(monkeypatch):
    daten, _ = lauf(monkeypatch)

    chat = daten["events"][0]
    assert chat["text"].endswith("…")
    assert len(chat["text"]) <= detail.VORSCHAU_LAENGE + 1


def test_kurzer_text_bleibt_unveraendert(monkeypatch):
    reihe = [dict(REIHE[0], text="Kurze Frage.")]
    daten, _ = lauf(monkeypatch, reihe=reihe)

    assert daten["events"][0]["text"] == "Kurze Frage."


def test_ohne_vor_gibt_es_keine_zeitgrenze(monkeypatch):
    _, calls = lauf(monkeypatch)

    sql = [s for s, _ in calls if "UNION ALL" in s][0]
    assert "wann <" not in sql


def test_mit_vor_wird_die_zeit_mitgegeben(monkeypatch):
    _, calls = lauf(monkeypatch, vor="2026-08-28T09:00:00Z")

    sql, params = [(s, p) for s, p in calls if "UNION ALL" in s][0]
    assert "wann <" in sql
    assert params["vor"] == "2026-08-28T09:00:00Z"


def test_jede_abfrage_ist_auf_die_person_beschraenkt(monkeypatch):
    """Four UNION branches, each with the user id in the WHERE."""
    _, calls = lauf(monkeypatch)

    sql = [s for s, _ in calls if "UNION ALL" in s][0]
    assert sql.count("%(uid)s") == 4


def test_has_more_wenn_die_seite_voll_ist(monkeypatch):
    voll = [dict(REIHE[0]) for _ in range(detail.VERLAUF_SEITE)]
    daten, _ = lauf(monkeypatch, reihe=voll)

    assert daten["has_more"] is True


def test_has_more_wenn_die_seite_nicht_voll_ist(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert daten["has_more"] is False


def test_zusammenhaengende_stunden_werden_eine_sitzung(monkeypatch):
    daten, _ = lauf(monkeypatch)

    erste = daten["sessions"][0]
    assert erste == {"day": "2026-08-29", "from": 13, "to": 14}


def test_luecke_reisst_die_sitzung_auseinander(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert {"day": "2026-08-29", "from": 9, "to": 9} in daten["sessions"]


def test_sitzungen_sind_nach_zeit_sortiert(monkeypatch):
    daten, _ = lauf(monkeypatch)

    tage = [s["day"] for s in daten["sessions"]]
    assert tage == sorted(tage, reverse=True)


def test_sitzungsabfrage_ist_auf_die_person_beschraenkt(monkeypatch):
    _, calls = lauf(monkeypatch)

    sql, params = [(s, p) for s, p in calls if "user_presence" in s][0]
    assert params == (NUTZER,)
