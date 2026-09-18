"""The text layer as one running text, nothing cut, nothing repeated, nothing recognised."""

import pytest

from src.features.summary import textlayer as tl


class _Seite:
    def __init__(self, text):
        self._text = text

    def get_textpage(self):
        return self

    def get_text_range(self):
        return self._text


class _Dokument:
    def __init__(self, seiten):
        self._seiten = [_Seite(t) for t in seiten]

    def __len__(self):
        return len(self._seiten)

    def __getitem__(self, i):
        return self._seiten[i]


def test_eine_textdatei_kommt_am_stueck_zurueck(tmp_path):
    text = " ".join(f"Satz Nummer {n}." for n in range(600))
    f = tmp_path / "a.txt"
    f.write_text(text, encoding="utf-8")

    ergebnis = tl.read_text_layer(str(f), "txt")

    assert ergebnis == text
    assert "\n\n" not in ergebnis


def test_markdown_und_untertitel_gehen_ueber_die_ausleser(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("# Titel\n\nAbsatz eins.", encoding="utf-8")
    assert "Absatz eins." in tl.read_text_layer(str(f), "md")


def test_pdf_seiten_werden_durch_eine_leerzeile_getrennt(monkeypatch):
    monkeypatch.setattr(tl, "_open_pdf", lambda pfad: _Dokument(["Seite eins.", "Seite zwei."]))
    assert tl.read_text_layer("x.pdf", "pdf") == "Seite eins.\n\nSeite zwei."


def test_leere_pdf_seiten_fallen_weg(monkeypatch):
    monkeypatch.setattr(tl, "_open_pdf", lambda pfad: _Dokument(["Text.", "   ", ""]))
    assert tl.read_text_layer("x.pdf", "pdf") == "Text."


def test_eine_pdf_ohne_text_wird_gemeldet(monkeypatch):
    monkeypatch.setattr(tl, "_open_pdf", lambda pfad: _Dokument(["", "  "]))
    with pytest.raises(tl.NoReadableText):
        tl.read_text_layer("x.pdf", "pdf")


def test_eine_fremde_endung_wird_abgelehnt():
    with pytest.raises(ValueError):
        tl.read_text_layer("x.xyz", "xyz")
