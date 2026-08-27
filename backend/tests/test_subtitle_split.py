"""Lange Erkenner-Segmente in kurze Einblendungen zerlegen."""

import pytest

from src.services.subtitle_converter import split_long_segments

# A real segment from storage, 553 characters over 29.3 seconds.
_LANG = (
    "Verantwortliche. Bei wissenschaftlichen Tagungen gibt es verschiedene "
    "Verantwortliche. Je nach Groesse der Konferenz gibt es mehrere Leiter, "
    "sogenannte Chairs. Das sind Fachleute aus dem jeweiligen Gebiet, meist "
    "Professoren, Dozenten, aber auch Praktiker aus Unternehmen koennen das "
    "sein. Dann gibt es immer ein Organisationskomitee. Das sind meistens "
    "Mitarbeiterinnen und Mitarbeiter der ausrichtenden Hochschule. Die sind "
    "zustaendig fuer Organisation und Ablauf, das heisst Raeumlichkeiten, "
    "Ausstattung, Rahmenprogramm, Verpflegung und so weiter und so fort."
)


def _seg(start: float, ende: float, text: str) -> dict:
    return {"start": start, "end": ende, "text": text}


def test_kurzes_segment_bleibt_unveraendert():
    """What is already short the recogniser passes through."""
    segmente = split_long_segments([_seg(1.0, 3.0, "Guten Morgen zusammen.")])
    assert segmente == [_seg(1.0, 3.0, "Guten Morgen zusammen.")]


def test_langes_segment_wird_geteilt():
    segmente = split_long_segments([_seg(0.0, 29.3, _LANG)])
    assert len(segmente) > 1


def test_keine_zeile_ist_laenger_als_die_grenze():
    for seg in split_long_segments([_seg(0.0, 29.3, _LANG)]):
        for zeile in seg["text"].split("\n"):
            assert len(zeile) <= 42, zeile


def test_hoechstens_zwei_zeilen_je_einblendung():
    for seg in split_long_segments([_seg(0.0, 29.3, _LANG)]):
        assert len(seg["text"].split("\n")) <= 2


def test_kein_wort_wird_zerschnitten():
    """All words come back out in the same order."""
    segmente = split_long_segments([_seg(0.0, 29.3, _LANG)])
    heraus = " ".join(s["text"].replace("\n", " ") for s in segmente).split()
    assert heraus == _LANG.split()


def test_zeiten_bleiben_im_rahmen_und_ohne_luecke():
    segmente = split_long_segments([_seg(10.0, 39.3, _LANG)])
    assert segmente[0]["start"] == 10.0
    assert segmente[-1]["end"] == 39.3
    for vorher, danach in zip(segmente, segmente[1:]):
        assert vorher["end"] == danach["start"]
        assert vorher["start"] < vorher["end"]


def test_getrennt_wird_am_satzende():
    """Two short sentences that together are too long split at the period."""
    text = (
        "Die Konferenz beginnt am Montag um neun Uhr im grossen Hoersaal. "
        "Danach geht es weiter mit den Vortraegen der Fachgruppen."
    )
    segmente = split_long_segments([_seg(0.0, 8.0, text)])
    assert segmente[0]["text"].replace("\n", " ").endswith("Hoersaal.")


def test_ein_uebermaessig_langes_wort_bleibt_ganz():
    """No endless looping when a single word blows the limit."""
    wort = "Donau" + "dampfschifffahrtsgesellschaft" * 4
    segmente = split_long_segments([_seg(0.0, 4.0, wort)])
    assert " ".join(s["text"].replace("\n", " ") for s in segmente).split() == [wort]


def test_leere_liste_bleibt_leer():
    assert split_long_segments([]) == []
