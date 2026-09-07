"""Transkript-Wege: ausliefern, melden, Sprachen auflisten."""

import pytest
from fastapi import HTTPException

from src.services.subtitle_converter import segments_to_vtt
from src.features.ai_assistant.routes.sources import _streaming

SEGMENTE = [{"start": 0.0, "end": 2.0, "text": "Hallo Welt"}]

WORKSPACE = {"id": 7, "uuid": "w1", "user_id": 42, "transcript_target_lang": "xx"}


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
    """The key has to match the requested language, not just any."""
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
    vtt_anlegen("en")

    antwort = await _langs()

    assert antwort["available"] == ["de", "en"]
    assert antwort["source_lang"] == "de"


async def test_ohne_untertitel_bleibt_die_liste_leer(quelle):
    antwort = await _langs()

    assert antwort["available"] == []


async def test_die_erkannte_sprache_steht_vorn(quelle):
    """The player builds its tabs from this, the order is visible."""
    _, vtt_anlegen, source = quelle
    source["language"] = "fr"
    vtt_anlegen("de")
    vtt_anlegen("fr")

    antwort = await _langs()

    assert antwort["available"] == ["fr", "de"]


async def test_das_transkript_der_nachbarquelle_zaehlt_nicht_mit(quelle):
    """All extra files sit in the same folder, the name keeps them apart."""
    ordner, vtt_anlegen, _ = quelle
    vtt_anlegen("de")
    (ordner / "xyz_transcript.fr.vtt").write_text("fremd", encoding="utf-8")

    antwort = await _langs()

    assert antwort["available"] == ["de"]


# ─── Uebersetzung starten ──────────────────────────────────────────────────

@pytest.fixture
def auftraege(quelle, monkeypatch):
    """Faengt den Celery-Auftrag ab und liefert die Liste der Aufrufe."""
    from src.services import feature_router
    from src.tasks import aia_tasks

    gesendet: list[tuple] = []

    class Auftrag:
        @staticmethod
        def delay(*args):
            gesendet.append(args)

    monkeypatch.setattr(_streaming, "_require_workspace_manage", lambda *a, **k: WORKSPACE)
    monkeypatch.setattr(
        feature_router, "resolve", lambda name: type("B", (), {"provider": {"id": 3}})()
    )
    monkeypatch.setattr(aia_tasks, "run_translate_transcript", Auftrag)
    return gesendet


async def _translate(target_lang: str):
    from src.features.ai_assistant import schemas
    return await _streaming.regenerate_transcript(
        workspace_uuid="w1", source_uuid="s1",
        body=schemas.TranslateTranscriptBody(target_lang=target_lang),
        current_user={"user_id": 42}, locale="de",
    )


async def test_die_gewaehlte_sprache_landet_im_auftrag(quelle, auftraege):
    """Die Sprache kommt aus dem Rumpf, nicht mehr aus dem Modul."""
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    antwort = await _translate("en")

    assert antwort["target_lang"] == "en"
    assert auftraege == [("s1", 3, "en")]


async def test_die_originalsprache_wird_abgewiesen(quelle, auftraege):
    """In die eigene Sprache zu uebersetzen ergibt keinen Sinn."""
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    with pytest.raises(HTTPException) as fehler:
        await _translate("de")

    assert fehler.value.status_code == 400
    assert auftraege == []


async def test_eine_unbekannte_sprache_wird_abgewiesen(quelle, auftraege):
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    with pytest.raises(HTTPException) as fehler:
        await _translate("xx")

    assert fehler.value.status_code == 400
    assert auftraege == []


# ─── Zielsprache steht an der Quelle ───────────────────────────────────────

async def test_die_zielsprache_kommt_aus_den_dateien(quelle):
    """Die vorhandene Uebersetzung zaehlt, das Modul-Feld sagt 'xx' und wird ignoriert."""
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")
    vtt_anlegen("en")

    antwort = await _langs()

    assert antwort["target_lang"] == "en"


async def test_ohne_uebersetzung_gibt_es_keine_zielsprache(quelle):
    _, vtt_anlegen, _ = quelle
    vtt_anlegen("de")

    antwort = await _langs()

    assert antwort["target_lang"] is None
