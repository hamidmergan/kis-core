"""The participant list of a module, now with the role."""

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
    """Answers by what was asked instead of by call order."""

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
    """The role is added, it replaces nothing."""
    daten, _ = lauf(monkeypatch)

    assert daten["members"][2] == {
        "name": "Mira Kaltenbach", "role": "student", "answered": 218, "chat": 47,
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


# ── Dieselbe Zahl an beiden Stellen ──────────────────────────────────────────

def test_die_modulliste_zaehlt_teilnehmer_wie_die_detailansicht():
    """List and the panel above it have to show the same number."""
    import inspect

    from src.features.stats import assistant

    quelle = inspect.getsource(assistant)

    assert "e.user_id <> m.user_id" in quelle, "der Eigentuemer darf nicht doppelt zaehlen"
    assert ") + 1 AS teilnehmer" in quelle, "und er muss ueberhaupt mitzaehlen"
