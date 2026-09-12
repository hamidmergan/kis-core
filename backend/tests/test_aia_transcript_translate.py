"""Which subtitle file counts as the original, and how often storage is queried."""

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
    """A media source in storage, returns (folder, file_path, make_vtt)."""
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
    """Translates by appending the target language to every sentence."""

    def __init__(self):
        self.aufrufe: list[dict] = []

    def translate_batch(self, texts, source_lang, target_lang):
        self.aufrufe.append({"source_lang": source_lang, "target_lang": target_lang})
        return [f"{t} [{target_lang}]" for t in texts]


@pytest.fixture
def uebersetzer(monkeypatch):
    """Installs a fake translator and returns it."""
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


# ─── Which file counts as the original ─────────────────────────────────────

def test_die_erkannte_sprache_gewinnt(quelle):
    """The detected language decides, not the order of the list."""
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    vtt_anlegen("en")

    key, lang = ingestion._resolve_source_vtt(file_path, {"language": "en"})

    assert lang == "en"
    assert key == str(ordner / "abc_transcript.en.vtt")


def test_ohne_erkannte_sprache_zaehlt_die_erste_vorhandene(quelle):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("en")

    key, lang = ingestion._resolve_source_vtt(file_path, {"language": "unknown"})

    assert lang == "en"
    assert key == str(ordner / "abc_transcript.en.vtt")


def test_eine_dritte_sprache_wird_trotzdem_gefunden(quelle):
    """Whisper detects any language, only the offered translation targets are capped."""
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("fr")

    key, lang = ingestion._resolve_source_vtt(file_path, {"language": "unknown"})

    assert lang == "fr"
    assert key == str(ordner / "abc_transcript.fr.vtt")


def test_erkannte_sprache_ohne_datei_faellt_auf_die_vorhandene_zurueck(quelle):
    """The column can name a language whose file does not exist."""
    _, file_path, vtt_anlegen = quelle
    vtt_anlegen("en")

    _, lang = ingestion._resolve_source_vtt(file_path, {"language": "de"})

    assert lang == "en"


def test_ohne_jede_untertiteldatei_kommt_nichts_zurueck(quelle):
    _, file_path, _ = quelle

    assert ingestion._resolve_source_vtt(file_path, {"language": "de"}) == (None, None)


def test_das_original_wird_mit_einer_einzigen_abfrage_gefunden(quelle, monkeypatch):
    """The point of the change, one listing instead of a query per language."""
    _, file_path, vtt_anlegen = quelle
    vtt_anlegen("ru")  # any language the model detects, not just an offered target
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
    """Exactly one translation per source, otherwise leftovers pile up.

    The source itself can be recorded in any language Whisper detects, even
    one outside the two offered translation targets, so this uses "fr" as
    the original to still exercise a switch between the two real targets.
    """
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("fr")
    vtt_anlegen("en")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "fr"})

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang="de")

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
        workspace={"transcript_target_lang": "en"},
    )

    ingestion._run_translate_transcript_inner("s1", provider_id=None, target_lang=None)

    assert (ordner / "abc_transcript.en.vtt").exists()


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
    """Both paths rely on the code being part of the key."""
    assert all(c.isalpha() and c.islower() and 2 <= len(c) <= 5 for c in TRANSCRIPT_LANGUAGES)


# ─── A failure leaves a note, a success removes it ──────────────────────────

class _KaputterUebersetzer:
    """Fails like a provider that answers with an error."""

    def __init__(self, meldung: str):
        self.meldung = meldung

    def translate_batch(self, texts, source_lang, target_lang):
        raise RuntimeError(self.meldung)


def _uebersetzer_einbauen(monkeypatch, client) -> None:
    from src import dependencies
    monkeypatch.setattr(
        dependencies, "get_translate_client_for_provider",
        lambda provider_id, feature=None: (client, None),
    )


def test_ein_fehler_hinterlaesst_eine_marke_mit_der_meldung(quelle, monkeypatch):
    """The panel polls for this note instead of waiting for a file that never comes."""
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})
    _uebersetzer_einbauen(monkeypatch, _KaputterUebersetzer("Internal Server Error"))

    with pytest.raises(RuntimeError):
        ingestion.run_translate_transcript("s1", None, "en")

    marke = ordner / "abc_transcript.en.error"
    assert marke.read_text(encoding="utf-8") == "Internal Server Error"
    assert not (ordner / "abc_transcript.en.vtt").exists()


def test_ein_rate_limit_hinterlaesst_keine_marke(quelle, monkeypatch):
    """A 429 is retried, so the panel has to keep waiting."""
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})
    _uebersetzer_einbauen(monkeypatch, _KaputterUebersetzer("Error code: 429 rate limit"))

    with pytest.raises(RuntimeError):
        ingestion.run_translate_transcript("s1", None, "en")

    assert not (ordner / "abc_transcript.en.error").exists()


def test_ein_erfolg_raeumt_die_alte_marke_weg(quelle, monkeypatch, uebersetzer):
    ordner, file_path, vtt_anlegen = quelle
    vtt_anlegen("de")
    (ordner / "abc_transcript.en.error").write_text("alt", encoding="utf-8")
    _db_stubs(monkeypatch, {"file_path": file_path, "workspace_id": 7, "language": "de"})

    ingestion.run_translate_transcript("s1", None, "en")

    assert not (ordner / "abc_transcript.en.error").exists()
    assert (ordner / "abc_transcript.en.vtt").exists()
