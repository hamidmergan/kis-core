"""The participant list of a module, now with the role."""

from datetime import datetime

from src.features.stats import detail

MODUL = "u-1"
EIGNER = 7
JONAS = 12
MIRA = 25

KOPF = {
    "id": 1, "uuid": MODUL, "title": "Werkstoffkunde 2",
    "is_active": True, "created_at": None,
    "owner_id": EIGNER, "owner": "Anke Reimers",
}

LEUTE = [
    {"user_id": EIGNER, "name": "Anke Reimers", "rolle": "owner", "uebungen": 0, "chat": 18},
    {"user_id": JONAS, "name": "Jonas Petersen", "rolle": "tutor", "uebungen": 34, "chat": 61},
    {"user_id": MIRA, "name": "Mira Kaltenbach", "rolle": "student", "uebungen": 218, "chat": 47},
]

# Zwei Werkzeuge fuer Mira, eins fuer Jonas, keins fuer die Eignerin.
WERKZEUGE = [
    {"user_id": MIRA, "tool": "flashcards", "n": 12},
    {"user_id": MIRA, "tool": "karteikarten", "n": 4},
    {"user_id": JONAS, "tool": "quiz", "n": 3},
]

# Mira: die Uebung ist neuer als ihr letzter Chat. Jonas: nur Chat. Die Eignerin: nichts.
AKTIVITAET = [
    {"user_id": MIRA, "zuletzt": datetime(2026, 8, 20, 9, 0)},
    {"user_id": JONAS, "zuletzt": datetime(2026, 8, 10, 14, 30)},
]


class _Cursor:
    """Answers by what was asked instead of by call order."""

    def __init__(self, leute, werkzeuge, aktivitaet, calls):
        self._leute, self._werkzeuge, self._aktivitaet = leute, werkzeuge, aktivitaet
        self._calls, self._sql = calls, ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._sql = " ".join(sql.split())
        self._calls.append((self._sql, params))

    def fetchone(self):
        if "FROM aia_workspaces m" in self._sql:
            return dict(KOPF)
        return {"n": 0, "zuletzt": None}

    def fetchall(self):
        if "GROUP BY p.user_id, s.tool" in self._sql:
            return [dict(w) for w in self._werkzeuge]
        if "GROUP BY user_id" in self._sql:
            return [dict(a) for a in self._aktivitaet]
        if "aia_enrollments" in self._sql:
            return [dict(p) for p in self._leute]
        return []


class _Conn:
    def __init__(self, leute, werkzeuge, aktivitaet, calls):
        self._leute, self._werkzeuge, self._aktivitaet, self._calls = leute, werkzeuge, aktivitaet, calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _Cursor(self._leute, self._werkzeuge, self._aktivitaet, self._calls)


def lauf(monkeypatch, leute=LEUTE, werkzeuge=WERKZEUGE, aktivitaet=AKTIVITAET):
    calls: list[tuple] = []
    monkeypatch.setattr(detail, "get_connection", lambda: _Conn(leute, werkzeuge, aktivitaet, calls))
    return detail.workspace_detail(MODUL), calls


def test_jede_person_traegt_ihre_rolle(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert [p["role"] for p in daten["members"]] == ["owner", "tutor", "student"]


def test_die_zahlen_je_person_bleiben_daneben_stehen(monkeypatch):
    """Die Rolle kam schon dazu, jetzt kommen Aktivitaet und Werkzeuge dazu."""
    daten, _ = lauf(monkeypatch)

    assert daten["members"][2] == {
        "name": "Mira Kaltenbach", "role": "student", "answered": 218, "chat": 47,
        "last": "2026-08-20T09:00:00Z",
        "tools": [
            {"tool": "lernkarten", "answered": 12},
            {"tool": "karteikarten", "answered": 4},
        ],
    }


def test_der_eigentuemer_zaehlt_bei_den_teilnehmern_mit(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert daten["totals"]["members"] == 3


def test_die_abfrage_holt_den_eigentuemer_dazu(monkeypatch):
    """They appear in no enrollment and were therefore missing entirely."""
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "aia_enrollments" in s][0]

    assert "UNION ALL" in sql
    assert "'owner'" in sql


def test_der_eigentuemer_steht_nicht_zweimal_da(monkeypatch):
    """Whoever entered their own module once also has an enrollment."""
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "aia_enrollments" in s][0]

    assert "e.user_id <> %s" in sql


def test_mehrere_einschreibungen_blieben_eine_person(monkeypatch):
    """The grouping stays so both lists answer the same question alike."""
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "aia_enrollments" in s][0]

    assert "GROUP BY e.user_id" in sql
    assert "BOOL_OR(e.role = 'tutor')" in sql, "dann gewinnt die staerkere Rolle"


# ── Zuletzt aktiv und genutzte Werkzeuge, beides nur in diesem Modul ────────

def test_zuletzt_aktiv_ist_das_neuere_von_chat_und_uebung(monkeypatch):
    daten, _ = lauf(monkeypatch)

    mira = daten["members"][2]
    assert mira["last"] == "2026-08-20T09:00:00Z"


def test_person_ohne_aktivitaet_hat_last_none(monkeypatch):
    daten, _ = lauf(monkeypatch)

    eignerin = daten["members"][0]
    assert eignerin["last"] is None


def test_werkzeuge_je_person_zeigen_die_kachel_statt_des_rohen_namens(monkeypatch):
    """flashcards in der DB, lernkarten auf der Kachel, das Frontend uebersetzt den Rest."""
    daten, _ = lauf(monkeypatch)

    jonas = daten["members"][1]
    assert jonas["tools"] == [{"tool": "quiz", "answered": 3}]


def test_person_ohne_werkzeugnutzung_hat_leere_liste(monkeypatch):
    daten, _ = lauf(monkeypatch)

    eignerin = daten["members"][0]
    assert eignerin["tools"] == []


def test_werkzeugabfrage_ist_auf_das_modul_beschraenkt(monkeypatch):
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "GROUP BY p.user_id, s.tool" in s][0]

    assert "s.workspace_id = %s" in sql


def test_aktivitaetsabfrage_verbindet_chat_und_uebungen(monkeypatch):
    """Presence bleibt aussen vor, das waere plattformweit statt modulbezogen."""
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "GROUP BY user_id" in s][0]

    assert "aia_messages" in sql
    assert "aia_exercise_progress" in sql
    assert "user_presence" not in sql


# ── Dieselbe Zahl an beiden Stellen ──────────────────────────────────────────

def test_die_modulliste_zaehlt_teilnehmer_wie_die_detailansicht():
    """List and the panel above it have to show the same number."""
    import inspect

    from src.features.stats import assistant

    quelle = inspect.getsource(assistant)

    assert "e.user_id <> m.user_id" in quelle, "der Eigentuemer darf nicht doppelt zaehlen"
    assert ") + 1 AS teilnehmer" in quelle, "und er muss ueberhaupt mitzaehlen"
