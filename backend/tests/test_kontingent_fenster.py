"""The quota window runs from first use, separately per tool."""

import os
from datetime import datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from src import quotas  # noqa: E402
from src.limits import QUOTA_DEFAULTS  # noqa: E402

NUTZER = -4711  # gehoert niemandem, die Tabelle hat keinen Fremdschluessel darauf
FENSTER_STUNDEN = QUOTA_DEFAULTS["tts"]["window_hours"]


@pytest.fixture(scope="module")
def verbindung():
    """A database connection or a clean skip."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("kein DATABASE_URL gesetzt (Test braucht echtes Postgres)")
    from src.core.db.pool import get_connection
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception as fehler:  # pragma: no cover - nur ausserhalb des Stacks
        pytest.skip(f"Datenbank nicht erreichbar: {fehler}")
    return get_connection


def _aufraeumen(verbindung):
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_quotas WHERE user_id = %s", (NUTZER,))
            cur.execute("DELETE FROM user_quota_overrides WHERE user_id = %s", (NUTZER,))
        conn.commit()


@pytest.fixture
def sauber(verbindung):
    """A user with no quota history, before as after."""
    _aufraeumen(verbindung)
    yield verbindung
    _aufraeumen(verbindung)


def _zeile(verbindung, typ: str) -> tuple[int, datetime | None]:
    """Counter and window end of this tool, the end in UTC."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT used, reset_at FROM user_quotas WHERE user_id = %s AND quota_type = %s",
                (NUTZER, typ),
            )
            zeile = cur.fetchone()
    if zeile is None:
        return 0, None
    ende = zeile[1]
    if ende is not None and ende.tzinfo is None:
        ende = ende.replace(tzinfo=timezone.utc)
    return zeile[0], ende


def _fenster_ablaufen_lassen(verbindung, typ: str) -> None:
    """Pushes this tool's window end into the past."""
    with verbindung() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE user_quotas SET reset_at = %s, window_started_at = %s
                   WHERE user_id = %s AND quota_type = %s""",
                (
                    datetime.now(timezone.utc) - timedelta(minutes=1),
                    datetime.now(timezone.utc) - timedelta(hours=FENSTER_STUNDEN, minutes=1),
                    NUTZER,
                    typ,
                ),
            )
        conn.commit()


def _grenze_setzen(verbindung, typ: str, wert: int) -> None:
    from src.database import quota_set_override
    quota_set_override(NUTZER, typ, wert)


def _verbrauchen(typ: str = "tts") -> dict:
    return quotas.check_and_consume_quota(NUTZER, typ, is_admin=False)


# --- the window starts at first use --------------------------------------------

def test_der_erste_aufruf_startet_das_fenster(sauber):
    vorher = datetime.now(timezone.utc)
    _verbrauchen("tts")

    verbraucht, ende = _zeile(sauber, "tts")
    assert verbraucht == 1
    assert ende is not None, "nach der ersten Nutzung muss ein Fensterende stehen"
    erwartet = vorher + timedelta(hours=FENSTER_STUNDEN)
    assert abs((ende - erwartet).total_seconds()) < 60


def test_weitere_aufrufe_verschieben_das_fensterende_nicht(sauber):
    _verbrauchen("tts")
    _, erstes_ende = _zeile(sauber, "tts")
    _verbrauchen("tts")
    verbraucht, zweites_ende = _zeile(sauber, "tts")

    assert verbraucht == 2
    assert erstes_ende is not None and zweites_ende is not None
    assert erstes_ende == zweites_ende, "das Fenster darf nicht mitwandern"


def test_nach_ablauf_faengt_der_zaehler_wieder_bei_eins_an(sauber):
    _verbrauchen("tts")
    _verbrauchen("tts")
    _fenster_ablaufen_lassen(sauber, "tts")

    _verbrauchen("tts")

    verbraucht, ende = _zeile(sauber, "tts")
    assert verbraucht == 1, "das abgelaufene Fenster zaehlt nicht mehr mit"
    assert ende is not None and ende > datetime.now(timezone.utc), "ein neues Fenster laeuft"


def test_ein_zaehler_ohne_fenster_zaehlt_nicht_mit(sauber):
    """Legacy: rows from the old version have a count but no window."""
    with sauber() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_quotas (user_id, quota_type, used, reset_at)
                   VALUES (%s, 'tts', 99, NULL)""",
                (NUTZER,),
            )
        conn.commit()

    ergebnis = _verbrauchen("tts")

    assert ergebnis["allowed"] is True
    assert _zeile(sauber, "tts")[0] == 1, "ohne Fenster hat der alte Stand keine Bedeutung"


# --- every tool on its own -----------------------------------------------------

def test_jedes_werkzeug_hat_sein_eigenes_fenster(sauber):
    _grenze_setzen(sauber, "tts", 1)
    _grenze_setzen(sauber, "summary", 1)
    _verbrauchen("tts")
    _verbrauchen("summary")

    _fenster_ablaufen_lassen(sauber, "tts")

    assert _verbrauchen("tts")["allowed"] is True, "das eigene Fenster ist abgelaufen"
    assert _verbrauchen("summary")["allowed"] is False, "das fremde Fenster laeuft weiter"


# --- the limit still applies ---------------------------------------------------

def test_die_grenze_sperrt_und_nennt_das_fensterende(sauber):
    _grenze_setzen(sauber, "tts", 2)
    _verbrauchen("tts")
    _verbrauchen("tts")

    ergebnis = _verbrauchen("tts")

    assert ergebnis["allowed"] is False
    assert ergebnis["used"] == 2
    assert ergebnis["limit"] == 2
    assert ergebnis["reset_at"], "die Absage muss sagen, wann es weitergeht"


def test_nach_ablauf_ist_das_gesperrte_werkzeug_wieder_frei(sauber):
    _grenze_setzen(sauber, "tts", 1)
    _verbrauchen("tts")
    assert _verbrauchen("tts")["allowed"] is False

    _fenster_ablaufen_lassen(sauber, "tts")

    assert _verbrauchen("tts")["allowed"] is True


# --- Bestandsschutz ------------------------------------------------------------

def test_admins_verbrauchen_nichts(sauber):
    ergebnis = quotas.check_and_consume_quota(NUTZER, "tts", is_admin=True)

    assert ergebnis["allowed"] is True
    assert _zeile(sauber, "tts") == (0, None), "fuer Admins wird nichts geschrieben"


def test_unbegrenzt_schreibt_keine_zeile(sauber):
    _grenze_setzen(sauber, "tts", -1)

    ergebnis = _verbrauchen("tts")

    assert ergebnis["allowed"] is True
    assert ergebnis["limit"] == -1
    assert _zeile(sauber, "tts") == (0, None)


# --- the admin view ------------------------------------------------------------

def test_die_admin_ansicht_nennt_das_fensterende_je_werkzeug(sauber):
    from src.database import quota_get_all_for_user
    _verbrauchen("tts")

    zeilen = quota_get_all_for_user(NUTZER)

    assert isinstance(zeilen, list), "es gibt kein gemeinsames Fensterende mehr daneben"
    tts = next(z for z in zeilen if z["quota_type"] == "tts")
    assert tts["used"] == 1
    assert tts["reset_at"] is not None, "die Ansicht muss das Fensterende zeigen"


def test_admin_zuruecksetzen_beendet_das_fenster(sauber):
    from src.database import quota_reset
    _verbrauchen("tts")

    quota_reset(NUTZER, "tts")

    assert _zeile(sauber, "tts") == (0, None), "Zaehler und Fenster sind weg"


# --- the refusal names a readable time ------------------------------------------

def test_das_gemeldete_fensterende_ist_lesbar(sauber):
    ergebnis = _verbrauchen("tts")

    gemeldet = datetime.fromisoformat(ergebnis["reset_at"].replace("Z", "+00:00"))

    assert gemeldet.tzinfo is not None
    assert abs((gemeldet - _zeile(sauber, "tts")[1]).total_seconds()) < 1


def test_die_absage_sagt_ab_wann_es_weitergeht(sauber):
    from fastapi import HTTPException
    from src.quotas import enforce_quota
    _grenze_setzen(sauber, "tts", 1)
    enforce_quota(NUTZER, "tts", is_admin=False)

    with pytest.raises(HTTPException) as absage:
        enforce_quota(NUTZER, "tts", is_admin=False)

    assert absage.value.status_code == 429
    assert "Erneut verfügbar ab" in absage.value.detail["message"]
