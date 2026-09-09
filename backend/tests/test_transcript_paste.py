"""Three pasted formats become the same segments, the rest is a clear refusal."""
import pytest

from src.limits import YOUTUBE_TRANSCRIPT_MAX_CHARS
from src.services.transcript_paste import parse_transcript
from src.services.web_page_fetch import LinkError

ZWEIZEILIG = "0:00\nHallo und willkommen\n0:04\nHeute geht es um Photosynthese\n0:09\nLos geht es\n"
EINZEILIG = "0:00 Hallo und willkommen\n0:04 Heute geht es um Photosynthese\n0:09 Los geht es\n"
SRT = (
    "1\n00:00:00,000 --> 00:00:04,000\nHallo und willkommen\n\n"
    "2\n00:00:04,000 --> 00:00:09,000\nHeute geht es um Photosynthese\n\n"
    "3\n00:00:09,000 --> 00:00:14,000\nLos geht es\n"
)
VTT = (
    "WEBVTT\n\n00:00.000 --> 00:04.000\nHallo und willkommen\n\n"
    "00:04.000 --> 00:09.000\nHeute geht es um Photosynthese\n\n"
    "00:09.000 --> 00:14.000\nLos geht es\n"
)
ERWARTET = ["Hallo und willkommen", "Heute geht es um Photosynthese", "Los geht es"]


@pytest.mark.parametrize("text", [ZWEIZEILIG, EINZEILIG, SRT, VTT])
def test_drei_formate_geben_dieselben_segmente(text):
    segments = parse_transcript(text)
    assert [s["text"] for s in segments] == ERWARTET
    assert [s["start"] for s in segments] == [0.0, 4.0, 9.0]
    assert [s["end"] for s in segments] == [4.0, 9.0, 14.0]


def test_windows_zeilenenden_und_gemischte_formen():
    text = "0:00\r\nHallo\r\n0:04 Welt\r\n0:09\r\nZeile eins\r\nZeile zwei\r\n"
    segments = parse_transcript(text)
    assert [s["text"] for s in segments] == ["Hallo", "Welt", "Zeile eins Zeile zwei"]


def test_stunden_werden_gelesen():
    segments = parse_transcript("1:02:03\nSpät im Video\n1:02:10\nNoch später\n")
    assert segments[0]["start"] == 3723.0
    assert segments[0]["end"] == 3730.0


def test_text_vor_der_ersten_zeitmarke_wird_verworfen():
    segments = parse_transcript("Transkript\nKapitel 1\n0:00\nHallo\n")
    assert [s["text"] for s in segments] == ["Hallo"]


def test_leere_zeitmarken_fallen_weg():
    segments = parse_transcript("0:00\n0:04\nHallo\n0:09\n")
    assert [(s["start"], s["text"]) for s in segments] == [(4.0, "Hallo")]


def test_ohne_zeitmarken_kommt_der_hinweis():
    with pytest.raises(LinkError) as exc:
        parse_transcript("Hallo und willkommen\nHeute geht es um Photosynthese\n")
    assert exc.value.key == "ai.youtube.noTimestamps"
    assert exc.value.status == 400


@pytest.mark.parametrize("text", ["", "   \n\n", "0:00\n0:04\n"])
def test_ohne_text_kommt_der_hinweis(text):
    with pytest.raises(LinkError) as exc:
        parse_transcript(text)
    assert exc.value.key == "ai.youtube.emptyTranscript"


def test_zu_lang_wird_abgewiesen():
    with pytest.raises(LinkError) as exc:
        parse_transcript("0:00 x\n" * (YOUTUBE_TRANSCRIPT_MAX_CHARS // 6 + 1))
    assert exc.value.key == "ai.youtube.tooLong"


def test_pfeil_im_text_macht_kein_srt_daraus():
    segments = parse_transcript("0:00\nErst das --> dann das\n0:04\nWeiter\n")
    assert [s["text"] for s in segments] == ["Erst das --> dann das", "Weiter"]
    assert [s["start"] for s in segments] == [0.0, 4.0]


def test_viele_leerzeilen_bleiben_schnell():
    import time

    start = time.monotonic()
    with pytest.raises(LinkError) as exc:
        parse_transcript("\n" * 200_000 + "x")
    assert exc.value.key == "ai.youtube.noTimestamps"
    assert time.monotonic() - start < 2.0


# The real copy from youtube.com glues the hidden spoken label between stamp and text.
ECHTE_KOPIE = (
    "0:066 SekundenViele Lehrmaterialien an Hochschulen liegen bereits in hoher Qualität vor.\n"
    "0:1111 SekundenHäufig jedoch nur auf Deutsch und nicht in Formaten, die internationale Studierende gut unterstützen.\n"
    "0:3939 Sekundenvorhandener Materialien und macht sie auch als bilinguale Lernformate nutzbar.\n"
    "1:061 Minute, 6 Sekundenoder Übersetzungen genutzt werden. Das Glossarsystem sichert fachsprachliche Konsistenz.\n"
    "2:232 Minuten, 23 SekundenWelcome everyone to this introduction to stereography and immersive media.\n"
)


def test_echte_youtube_kopie_mit_angeklebter_beschriftung():
    segments = parse_transcript(ECHTE_KOPIE)
    assert [s["start"] for s in segments] == [6.0, 11.0, 39.0, 66.0, 143.0]
    assert segments[0]["text"].startswith("Viele Lehrmaterialien")
    assert segments[1]["text"].startswith("Häufig jedoch")
    assert segments[2]["text"].startswith("vorhandener Materialien")
    assert segments[3]["text"].startswith("oder Übersetzungen")
    assert segments[4]["text"].startswith("Welcome everyone")
    assert segments[3]["end"] == 143.0


def test_echte_kopie_auf_englisch_und_mit_stunden():
    text = (
        "0:066 secondsMany teaching materials already exist.\n"
        "1:061 minute, 6 secondsor translations.\n"
        "1:02:031 hour, 2 minutes, 3 secondsLate in the video.\n"
    )
    segments = parse_transcript(text)
    assert [s["start"] for s in segments] == [6.0, 66.0, 3723.0]
    assert [s["text"] for s in segments] == [
        "Many teaching materials already exist.", "or translations.", "Late in the video.",
    ]


def test_unbekannte_sprache_behaelt_die_beschriftung_im_text():
    # The stamp still counts, only the label stays in the text (Finnish is not in the list).
    segments = parse_transcript("0:066 sekuntiaTeksti tässä.\n0:1111 sekuntiaToinen rivi.\n")
    assert [s["start"] for s in segments] == [6.0, 11.0]
    assert segments[0]["text"] == "6 sekuntiaTeksti tässä."


def test_kopfzeilen_der_youtube_seite_werden_verworfen():
    segments = parse_transcript("Transkript\nIm Transkript suchen\n0:066 SekundenHallo.\n")
    assert [s["text"] for s in segments] == ["Hallo."]
