"""The info file that sits in the ZIP next to video and slides."""

from datetime import datetime

from src.services.screencast.infodatei import baue_info, dauer_text, sprach_wort


def _job() -> dict:
    return {
        "original_filename": "Vorlesung 3.pptx",
        "completed_at": datetime(2026, 8, 23, 21, 40),
        "created_at": datetime(2026, 8, 23, 21, 10),
    }


def _meta() -> dict:
    return {
        "target_lang": "EN-US",
        "subtitles": True,
        "audio_count": 12,
        "stats": {
            "skripte": {"anbieter": "myLab", "modell": "qwen3-32b", "dauer_s": 72.4},
            "uebersetzung": {
                "anbieter": "myLab", "modell": "qwen3-32b",
                "quelle": "DE", "ziel": "EN-US", "folien": 12, "dauer_s": 134.0,
            },
            "bilder": {"dpi": 100, "folien": 12, "dauer_s": 18.0},
            "vertonung": {
                "anbieter": "myLab", "modell": "stimme-v1",
                "stimme": "nova", "stimme_name": "Anna",
                "tempo": 1.0, "folien": 12, "zeichen": 8432, "dauer_s": 542.0,
            },
            "clips": {"folien": 12, "folienpause": 0.5, "dauer_s": 100.0},
            "untertitel": {"folien_mit_ton": 12, "dauer_s": 4.0},
            "zusammenfuegen": {"clips": 13, "dauer_s": 12.0},
        },
    }


def test_info_fuer_nutzer_zeigt_die_einstellungen():
    text = baue_info(_job(), _meta(), mit_technik=False)

    assert "Vorlesung 3" in text
    assert "23.08.2026" in text
    assert "Folien: 12" in text
    assert "Zeichen im Sprechtext: 8.432" in text
    assert "Deutsch nach Englisch" in text
    assert "Stimme: Anna" in text
    assert "Tempo: 1,0" in text
    assert "Pause zwischen Folien: 0,5 Sekunden" in text
    assert "Untertitel: ja" in text


def test_info_fuer_nutzer_verschweigt_anbieter_und_modell():
    text = baue_info(_job(), _meta(), mit_technik=False)

    assert "myLab" not in text
    assert "stimme-v1" not in text
    assert "qwen3-32b" not in text


def test_info_fuer_admin_zeigt_anbieter_und_modell():
    text = baue_info(_job(), _meta(), mit_technik=True)

    assert "Vertonung: myLab, Modell stimme-v1" in text
    assert "Übersetzung: myLab, Modell qwen3-32b" in text
    assert "Sprechtexte: myLab, Modell qwen3-32b" in text
    assert "Auflösung: 100 dpi" in text


def test_info_nennt_keine_dauern_mehr():
    """The per-step times are no longer in the file."""
    assert "Dauer" not in baue_info(_job(), _meta(), mit_technik=True)


def test_info_ohne_zahlen_bleibt_lesbar():
    """Old jobs have no stats, the file must still not be empty."""
    text = baue_info(_job(), {"audio_count": 5, "subtitles": False}, mit_technik=True)

    assert "Vorlesung 3" in text
    assert "Folien: 5" in text
    assert "Untertitel: nein" in text
    assert "Stimme:" not in text  # keine erfundene Angabe


def test_info_ohne_uebersetzung_nennt_nur_die_sprache():
    meta = _meta()
    del meta["stats"]["uebersetzung"]
    text = baue_info(_job(), meta, mit_technik=False)

    assert "nach" not in text.split("Sprache:")[1].split("\n")[0]
    assert "Sprache: Englisch" in text


def test_dauer_text_rundet_menschlich():
    assert dauer_text(0) == "0 s"
    assert dauer_text(18.4) == "18 s"
    assert dauer_text(62) == "1 min 2 s"
    assert dauer_text(600) == "10 min 0 s"
    assert dauer_text(3672) == "1 h 1 min"


def test_sprach_wort_fuer_den_dateinamen():
    assert sprach_wort("EN-US") == "englisch"
    assert sprach_wort("FR") == "franzoesisch"
    assert sprach_wort("") == "uebersetzt"
    assert sprach_wort("XX-YY") == "uebersetzt"
