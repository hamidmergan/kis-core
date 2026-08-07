"""Zielsprache der Auswahlleisten-Übersetzung: Speicherung je Person.

Warum die Einstellung an der Person hängt und nicht am Modul: wer ein
deutsches Skript liest, braucht die Übersetzung in seiner eigenen Sprache.
Eine Vorgabe des Moduls würde allen dieselbe aufzwingen.

Alles offline. Die Datenbankverbindung wird durch eine Attrappe ersetzt, die
eine vorgegebene Zeile liefert und die abgesetzte Anweisung mitschreibt.
"""

import pytest

from src.features.ai_assistant.repository import chat as repo_chat


class _FakeCursor:
    def __init__(self, row, calls):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row, calls):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._row, self._calls)

    def commit(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    """Hängt die Verbindung aus und gibt die Liste der Anweisungen zurück."""
    def _apply(row):
        calls: list[tuple] = []
        monkeypatch.setattr(repo_chat, "get_connection", lambda: _FakeConn(row, calls))
        return calls
    return _apply


def test_person_ohne_gespeicherte_einstellung_bekommt_englisch(fake_db):
    fake_db(None)
    settings = repo_chat.get_aia_user_settings(1, 2)
    assert settings["popup_translate_lang"] == "en"


def test_gespeicherter_wert_wird_gelesen(fake_db):
    fake_db({
        "chat_lang": "de",
        "studio_enabled": True,
        "popup_translate_lang": "tr",
    })
    settings = repo_chat.get_aia_user_settings(1, 2)
    assert settings["popup_translate_lang"] == "tr"


def test_schreiben_nimmt_die_sprache_mit(fake_db):
    calls = fake_db(None)
    repo_chat.upsert_aia_user_settings(1, 2, "de", True, "ar")
    sql, params = calls[0]
    assert "popup_translate_lang" in sql
    assert "ar" in params


def test_schreiben_ohne_angabe_bleibt_bei_englisch(fake_db):
    calls = fake_db(None)
    repo_chat.upsert_aia_user_settings(1, 2, "de", True)
    _sql, params = calls[0]
    assert "en" in params


# ── Route: Einstellung schreiben ─────────────────────────────────────────────

import pytest
from fastapi import HTTPException

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes import messages as messages_route


@pytest.fixture
def fake_settings_route(monkeypatch):
    """Modul und Einschreibung vortäuschen, Schreibaufrufe mitschreiben."""
    written: list[tuple] = []
    monkeypatch.setattr(messages_route.db, "get_aia_workspace", lambda uuid: {"id": 7, "user_id": 3})
    monkeypatch.setattr(messages_route.db, "is_student_enrolled", lambda wid, uid: True)
    monkeypatch.setattr(
        messages_route.db, "upsert_aia_user_settings",
        lambda *args: written.append(args),
    )
    return written


def _body(lang):
    return schemas.UserSettingsBody(
        chat_lang="de", studio_enabled=True,
        popup_translate_lang=lang,
    )


def test_body_faellt_ohne_angabe_auf_englisch():
    body = schemas.UserSettingsBody(
        chat_lang="de", studio_enabled=True,
    )
    assert body.popup_translate_lang == "en"


@pytest.mark.asyncio
async def test_route_speichert_gueltige_sprache(fake_settings_route):
    await messages_route.update_user_settings(
        "abc", _body("es"), current_user={"user_id": 3}, locale="de",
    )
    # Positionen: workspace, user, chat_lang, studio, popup_lang, sprachtrainer
    assert fake_settings_route[0][4] == "es"


@pytest.mark.asyncio
async def test_route_lehnt_unbekannte_sprache_ab(fake_settings_route):
    with pytest.raises(HTTPException) as err:
        await messages_route.update_user_settings(
            "abc", _body("klingonisch"), current_user={"user_id": 3}, locale="de",
        )
    assert err.value.status_code == 400
    assert fake_settings_route == []
