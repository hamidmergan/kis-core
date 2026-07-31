"""Transkript-Uebersetzung: welche Untertiteldatei gilt als Original, was fliegt raus.

Diese beiden Entscheidungen liefen frueher ueber eine einzelne Abfrage je
Sprache, also bis zu neun Netzwerkrunden pro Aufruf. Jetzt ist es eine
Auflistung. Das Ergebnis muss dasselbe sein, deshalb steht hier beides: was
herauskommt und wie oft dafuer der Speicher befragt wird.
"""

import pytest

from src.i18n import TRANSCRIPT_LANGUAGES
from src.services.subtitle_converter import segments_to_vtt
from src.features.ai_assistant.tasks import ingestion

SEGMENTE = [
    {"start": 0.0, "end": 2.5, "text": "Hallo Welt"},
    {"start": 2.5, "end": 4.0, "text": "Zweiter Satz"},
]


@pytest.fixture
def quelle(lokal):
    """Eine Medienquelle im Speicher. Liefert (ordner, file_path, vtt_anlegen)."""
    ordner = lokal / "users/42/aia/workspaces/w1/sources"
    ordner.mkdir(parents=True)
    file_path = str(ordner / "abc.mp4")
    (ordner / "abc.mp4").write_bytes(b"video")

    def vtt_anlegen(lang: str, segmente=SEGMENTE) -> None:
        (ordner / f"abc_transcript.{lang}.vtt").write_text(
            segments_to_vtt(segmente), encoding="utf-8"
        )

    return ordner, file_path, vtt_anlegen


class _FakeUebersetzer:
    """Uebersetzt, indem er jedem Satz die Zielsprache anhaengt."""

    def __init__(self):
        self.aufrufe: list[dict] = []

    def translate_batch(self, texts, source_lang, target_lang):
        self.aufrufe.append({"source_lang": source_lang, "target_lang": target_lang})
        return [f"{t} [{target_lang}]" for t in texts]


@pytest.fixture
def uebersetzer(monkeypatch):
    """Haengt einen Fake-Uebersetzer ein und liefert ihn zurueck."""
    from src import dependencies
    client = _FakeUebersetzer()
    monkeypatch.setattr(
        dependencies, "get_translate_client_for_provider",
        lambda provider_id, feature=None: (client, None),
    )
    return client


def _db_stubs(monkeypatch, source: dict, workspace: dict | None = None) -> None:
    monkeypatch.setattr(ingestion.db, "get_aia_source", lambda uuid: source)
    monkeypatch.setattr(
        ingestion.db, "get_aia_workspace_by_id", lambda ws_id: workspace or {},
    )


# ─── Welche Datei gilt als Original ────────────────────────────────────────

def test_die_erkannte_sprache_gewinnt(quelle):
    """``en`` steht in der Sprachliste hinter ``de``. Wer die erkannte Sprache
    ueberginge und einfach die Liste durchliefe, kaeme hier auf ``de`` und
    wuerde eine Uebersetzung faelschlich zum Original erklaeren."""
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    vtt_anlegen("en")

    key, lang = ingestion._resolve_source_vtt(file_path, {"language": "en"})

    assert lang == "en"
    assert key == str(ordner / "abc_transcript.en.vtt")


def test_ohne_erkannte_sprache_zaehlt_die_erste_vorhandene(quelle):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("fr")

    key, lang = ingestion._resolve_source_vtt(file_path, {"language": "unknown"})

    assert lang == "fr"
    assert key == str(ordner / "abc_transcript.fr.vtt")


def test_erkannte_sprache_ohne_datei_faellt_auf_die_vorhandene_zurueck(quelle):
    """Die Spalte kann eine Sprache nennen, deren Datei es nicht gibt."""
    _, file_path, vtt_anlegen = quelle
    vtt_anlegen("en")

    _, lang = ingestion._resolve_source_vtt(file_path, {"language": "de"})

    assert lang == "en"


def test_ohne_jede_untertiteldatei_kommt_nichts_zurueck(quelle):
    _, file_path, _ = quelle

    assert ingestion._resolve_source_vtt(file_path, {"language": "de"}) == (None, None)


def test_das_original_wird_mit_einer_einzigen_abfrage_gefunden(quelle, monkeypatch):
    """Der Punkt der Umstellung. Eine Auflistung statt einer Abfrage je Sprache."""
    _, file_path, vtt_anlegen = quelle
    vtt_anlegen("ru")  # letzte der acht Sprachen, frueher der teuerste Fall
    aufrufe: list[str] = []
    echt = ingestion.list_keys
    monkeypatch.setattr(
        ingestion, "list_keys", lambda p: (aufrufe.append(p), echt(p))[1],
    )

    _, lang = ingestion._resolve_source_vtt(file_path, {"language": "unknown"})

    assert lang == "ru"
    assert len(aufrufe) == 1


# ─── Aufraeumen alter Uebersetzungen ───────────────────────────────────────

def test_zielsprache_gleich_quellsprache_wirft_alte_uebersetzungen_weg(
    quelle, monkeypatch,
):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    vtt_anlegen("en")
    vtt_anlegen("fr")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang="de")

    assert sorted(p.name for p in ordner.iterdir()) == ["abc.mp4", "abc_transcript.de.vtt"]


def test_uebersetzung_wird_geschrieben_und_das_original_bleibt(
    quelle, monkeypatch, uebersetzer,
):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang="en")

    assert sorted(p.name for p in ordner.iterdir()) == [
        "abc.mp4", "abc_transcript.de.vtt", "abc_transcript.en.vtt",
    ]
    inhalt = (ordner / "abc_transcript.en.vtt").read_text(encoding="utf-8")
    assert "Hallo Welt [English]" in inhalt
    assert uebersetzer.aufrufe == [{"source_lang": "German", "target_lang": "English"}]


def test_eine_neue_zielsprache_verdraengt_die_alte(quelle, monkeypatch, uebersetzer):
    """Genau eine Uebersetzung je Quelle, sonst sammeln sich Altlasten an."""
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    vtt_anlegen("en")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang="fr")

    assert sorted(p.name for p in ordner.iterdir()) == [
        "abc.mp4", "abc_transcript.de.vtt", "abc_transcript.fr.vtt",
    ]


def test_die_zielsprache_kommt_aus_dem_workspace_wenn_keine_genannt_ist(
    quelle, monkeypatch, uebersetzer,
):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    _db_stubs(
        monkeypatch,
        {"file_path": file_path, "workspace_id": 7, "language": "de"},
        workspace={"transcript_target_lang": "it"},
    )

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang=None)

    assert (ordner / "abc_transcript.it.vtt").exists()


def test_aufraeumen_fasst_fremde_quellen_nicht_an(quelle, monkeypatch):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    vtt_anlegen("fr")
    (ordner / "xyz_transcript.fr.vtt").write_text("fremd", encoding="utf-8")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang="de")

    assert (ordner / "xyz_transcript.fr.vtt").read_text(encoding="utf-8") == "fremd"


def test_eine_unbekannte_zielsprache_aendert_nichts(quelle, monkeypatch):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang="klingon")

    assert sorted(p.name for p in ordner.iterdir()) == ["abc.mp4", "abc_transcript.de.vtt"]


def test_alle_bekannten_sprachen_sind_zweistellig_klein():
    """Beide Wege verlassen sich darauf, dass der Code im Schluessel steht."""
    assert all(c.isalpha() and c.islower() and 2 <= len(c) <= 5 for c in TRANSCRIPT_LANGUAGES)
