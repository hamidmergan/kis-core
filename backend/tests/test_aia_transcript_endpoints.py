"""Transkript-Endpunkte: Untertitel ausliefern, Vorhandensein melden, Sprachen auflisten.

Alle drei bauen ihren Schluessel aus dem Pfad der Quelle. Geht dabei etwas
schief, liefert der Player stumm keine Spur, ohne Fehler im Log. Geprueft wird
gegen den echten lokalen Speicher.
"""

import pytest
from fastapi import HTTPException

from src.services.subtitle_converter import segments_to_vtt
from src.features.ai_assistant.routes.sources import _streaming

SEGMENTE = [{"start": 0.0, "end": 2.0, "text": "Hallo Welt"}]

WORKSPACE = {"id": 7, "uuid": "w1", "user_id": 42, "transcript_target_lang": "en"}


@pytest.fixture
def quelle(lokal, monkeypatch):
    """Eine Medienquelle samt Zugriffspruefung. Liefert (ordner, vtt_anlegen, source)."""
    ordner = lokal / "users/42/aia/workspaces/w1/sources"
    ordner.mkdir(parents=True)
    (ordner / "abc.mp4").write_bytes(b"video")
    source = {
        "uuid": "s1", "workspace_id": 7, "filename": "vorlesung.mp4",
        "file_path": str(ordner / "abc.mp4"), "language": "de",
    }

    monkeypatch.setattr(_streaming.db, "get_aia_workspace", lambda uuid: WORKSPACE)
    monkeypatch.setattr(_streaming.db, "is_student_enrolled", lambda ws_id, user_id: False)
    monkeypatch.setattr(_streaming, "_load_workspace_source", lambda *a, **k: source)

    def vtt_anlegen(lang: str) -> None:
        (ordner / f"abc_transcript.{lang}.vtt").write_text(
            segments_to_vtt(SEGMENTE), encoding="utf-8"
        )

    return ordner, vtt_anlegen, source


async def _vtt(lang: str):
    return await _streaming.get_transcript_vtt(
        workspace_uuid="w1", source_uuid="s1", lang=lang,
        current_user={"user_id": 42}, locale="de",
    )


async def _exists(lang: str):
    return await _streaming.get_transcript_exists(
        workspace_uuid="w1", source_uuid="s1", lang=lang,
        current_user={"user_id": 42}, locale="de",
    )


async def _langs():
    return await _streaming.get_transcript_langs(
        workspace_uuid="w1", source_uuid="s1",
        current_user={"user_id": 42}, locale="de",
    )


# ─── Untertitel ausliefern ─────────────────────────────────────────────────

async def test_vorhandene_untertitel_kommen_zurueck(quelle):
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    antwort = await _vtt("de")

    assert b"Hallo Welt" in antwort.body
    assert antwort.media_type.startswith("text/vtt")


async def test_fehlende_sprache_gibt_404(quelle):
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    with pytest.raises(HTTPException) as fehler:
        await _vtt("fr")

    assert fehler.value.status_code == 404


async def test_die_sprachen_werden_nicht_verwechselt(quelle):
    """Der Schluessel muss die angefragte Sprache treffen, nicht irgendeine."""
    ordner, _, _ = quelle
    (ordner / "abc_transcript.de.vtt").write_text(
        segments_to_vtt([{"start": 0.0, "end": 1.0, "text": "deutsch"}]), encoding="utf-8",
    )
    (ordner / "abc_transcript.en.vtt").write_text(
        segments_to_vtt([{"start": 0.0, "end": 1.0, "text": "english"}]), encoding="utf-8",
    )

    assert b"english" in (await _vtt("en")).body
    assert b"deutsch" in (await _vtt("de")).body


async def test_ein_unsinniger_sprachcode_wird_abgewiesen(quelle):
    with pytest.raises(HTTPException) as fehler:
        await _vtt("../../etc/passwd")

    assert fehler.value.status_code == 400


# ─── Vorhandensein melden ──────────────────────────────────────────────────

async def test_vorhandensein_meldet_wahr_und_falsch(quelle):
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    assert await _exists("de") == {"exists": True}
    assert await _exists("fr") == {"exists": False}


# ─── Sprachen auflisten ────────────────────────────────────────────────────

async def test_nur_wirklich_vorhandene_sprachen_werden_gemeldet(quelle):
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")
    vtt_anlegen("fr")

    antwort = await _langs()

    assert antwort["available"] == ["de", "fr"]
    assert antwort["source_lang"] == "de"
    assert antwort["target_lang"] == "en"


async def test_ohne_untertitel_bleibt_die_liste_leer(quelle):
    antwort = await _langs()

    assert antwort["available"] == []


async def test_die_erkannte_sprache_steht_vorn(quelle):
    """Der Player baut daraus seine Reiter, die Reihenfolge ist sichtbar."""
    _, vtt_anlegen, source = quelle
    source["language"] = "fr"
    vtt_anlegen("de")
    vtt_anlegen("fr")

    antwort = await _langs()

    assert antwort["available"] == ["fr", "de"]


async def test_das_transkript_der_nachbarquelle_zaehlt_nicht_mit(quelle):
    """Alle Zusatzdateien liegen im selben Ordner, die Trennung macht der Name."""
    ordner, vtt_anlegen, _ = quelle
    vtt_anlegen("de")
    (ordner / "xyz_transcript.fr.vtt").write_text("fremd", encoding="utf-8")

    antwort = await _langs()

    assert antwort["available"] == ["de"]
