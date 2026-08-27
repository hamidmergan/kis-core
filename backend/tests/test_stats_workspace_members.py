"""Die Teilnehmerliste eines Moduls, jetzt mit Rolle.

Ohne die Rolle stand in der Liste eine Zahlenkolonne, in der der Tutor wie
jeder andere aussah. Wer eine Lehrperson auf ihre eigenen Module loslaesst,
muss ihr auch sagen koennen, wen sie da vor sich hat.
"""

from src.features.stats import detail

MODUL = "u-1"
EIGNER = 7

KOPF = {
    "id": 1, "uuid": MODUL, "title": "Werkstoffkunde 2",
    "is_active": True, "created_at": None,
    "owner_id": EIGNER, "owner": "Anke Reimers",
}

LEUTE = [
    {"name": "Anke Reimers", "rolle": "owner", "uebungen": 0, "chat": 18},
    {"name": "Jonas Petersen", "rolle": "tutor", "uebungen": 34, "chat": 61},
    {"name": "Mira Kaltenbach", "rolle": "student", "uebungen": 218, "chat": 47},
]


class _Cursor:
    """Antwortet nach dem, was gefragt wurde, statt nach Aufrufreihenfolge."""

    def __init__(self, leute, calls):
        self._leute, self._calls, self._sql = leute, calls, ""

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
        if "aia_enrollments" in self._sql:
            return [dict(p) for p in self._leute]
        return []


class _Conn:
    def __init__(self, leute, calls):
        self._leute, self._calls = leute, calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _Cursor(self._leute, self._calls)


def lauf(monkeypatch, leute=LEUTE):
    calls: list[tuple] = []
    monkeypatch.setattr(detail, "get_connection", lambda: _Conn(leute, calls))
    return detail.workspace_detail(MODUL), calls


def test_jede_person_traegt_ihre_rolle(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert [p["role"] for p in daten["members"]] == ["owner", "tutor", "student"]


def test_die_zahlen_je_person_bleiben_daneben_stehen(monkeypatch):
    """Die Rolle kommt dazu, sie ersetzt nichts."""
    daten, _ = lauf(monkeypatch)

    assert daten["members"][2] == {
        "name": "Mira Kaltenbach", "role": "student", "answered": 218, "chat": 47,
    }


def test_der_eigentuemer_zaehlt_bei_den_teilnehmern_mit(monkeypatch):
    daten, _ = lauf(monkeypatch)

    assert daten["totals"]["members"] == 3


def test_die_abfrage_holt_den_eigentuemer_dazu(monkeypatch):
    """Er steht in keiner Einschreibung und fehlte deshalb ganz."""
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "aia_enrollments" in s][0]

    assert "UNION ALL" in sql
    assert "'owner'" in sql


def test_der_eigentuemer_steht_nicht_zweimal_da(monkeypatch):
    """Wer sein Modul einmal selbst betreten hat, hat auch eine Einschreibung."""
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "aia_enrollments" in s][0]

    assert "e.user_id <> %s" in sql


def test_mehrere_einschreibungen_blieben_eine_person(monkeypatch):
    """Heute verhindert ein UNIQUE auf (workspace_id, user_id) den Fall schon.

    Die Zusammenfassung steht trotzdem da, weil ``get_workspace_participants``
    dieselbe Frage genauso beantwortet. Zwei Listen derselben Leute, die sich
    bei geloeckertem Schluessel unterschiedlich verhalten, waeren die schlechtere
    Wahl als eine Zeile, die heute nichts tut.
    """
    _, calls = lauf(monkeypatch)
    sql = [s for s, _ in calls if "aia_enrollments" in s][0]

    assert "GROUP BY e.user_id" in sql
    assert "BOOL_OR(e.role = 'tutor')" in sql, "dann gewinnt die staerkere Rolle"


# ── Dieselbe Zahl an beiden Stellen ──────────────────────────────────────────

def test_die_modulliste_zaehlt_teilnehmer_wie_die_detailansicht():
    """Die Liste im Reiter KI-Assistent und das Fenster darueber zeigen dieselbe
    Spalte. Stuende in der Zeile 2 und im geoeffneten Modul 3, suchte man den
    Fehler bei sich statt in der Abfrage.
    """
    import inspect

    from src.features.stats import assistant

    quelle = inspect.getsource(assistant)

    assert "e.user_id <> m.user_id" in quelle, "der Eigentuemer darf nicht doppelt zaehlen"
    assert ") + 1 AS teilnehmer" in quelle, "und er muss ueberhaupt mitzaehlen"
