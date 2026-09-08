"""From a fetched page to the small HTML file LibreOffice renders."""
from datetime import datetime, timezone

import pytest

from src.services import web_page_extract as wpe
from src.services.web_page_fetch import LinkError

# Long enough to clear the word floor, boring enough to stay out of the way.
_ABSATZ = ("Die Photosynthese ist ein biochemischer Prozess, bei dem Pflanzen Lichtenergie "
           "in chemische Energie umwandeln und dabei aus Kohlendioxid und Wasser Zucker "
           "und Sauerstoff herstellen. ")


def _seite(titel="Photosynthese im Überblick", absaetze=6, extra=""):
    # Byte-distinct paragraphs: trafilatura collapses consecutive identical-text elements.
    text = "".join(f"<p>Absatz {i + 1}: {_ABSATZ}</p>" for i in range(absaetze))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{titel}</title></head>
<body>
<nav><ul><li><a href="/">Start</a></li><li><a href="/kontakt">Kontakt</a></li><li><a href="/impressum">Impressum</a></li></ul></nav>
<div id="cookie-banner">Wir verwenden Cookies. <button>Cookies akzeptieren</button></div>
<main><article><h1>{titel}</h1>{text}{extra}</article></main>
<footer><p>Copyright Hochschule. Datenschutz. Impressum.</p></footer>
</body></html>""".encode("utf-8")


def test_haupttext_bleibt_menue_und_banner_fliegen():
    doc = wpe.extract_html_page(_seite(), "https://example.org/bio/photosynthese")
    assert doc.title == "Photosynthese im Überblick"
    assert doc.word_count >= 100
    assert "Photosynthese ist ein biochemischer Prozess" in doc.body_html
    assert "Cookies akzeptieren" not in doc.body_html
    assert "Impressum" not in doc.body_html
    assert "<p>" in doc.body_html


def test_zu_wenig_text_gibt_den_wortzahl_fehler():
    with pytest.raises(LinkError) as exc:
        wpe.extract_html_page(_seite(absaetze=1), "https://example.org/kurz")
    assert exc.value.key == "ai.link.noText"
    assert exc.value.status == 422


def test_leere_seite_gibt_den_wortzahl_fehler():
    with pytest.raises(LinkError):
        wpe.extract_html_page(b"<html><body></body></html>", "https://example.org/leer")


def test_titel_faellt_auf_host_und_pfad_zurueck():
    ohne_titel = _seite(titel="").replace(b"<title></title>", b"")
    doc = wpe.extract_html_page(ohne_titel, "https://example.org/bio/photosynthese")
    assert doc.title == "example.org/bio/photosynthese"


def test_bilder_und_links_stehen_nicht_in_der_datei():
    extra = ('<p>Mehr dazu <a href="https://boese.example/x">hier</a>.</p>'
             '<img src="https://boese.example/pixel.png" alt="p">'
             '<script>alert(1)</script>')
    doc = wpe.extract_html_page(_seite(extra=extra), "https://example.org/a")
    datei = wpe.build_document_html(doc.title, "https://example.org/a", doc.body_html, datetime.now(timezone.utc), "de")
    assert "href=" not in datei
    assert "src=" not in datei
    assert "<script" not in datei
    assert "<img" not in datei


def test_strip_outside_entfernt_jede_referenz_nach_aussen():
    frag = ('<p style="background:url(x)">a</p><img src="x.png"/><link rel="stylesheet" href="s.css">'
            '<iframe src="y"></iframe><a href="z">b</a>')
    out = wpe.strip_outside(frag)
    assert out == "<p>a</p><a>b</a>"


def test_dokument_hat_titel_und_kopfzeile():
    datei = wpe.build_document_html(
        "Mein Titel", "https://example.org/a", "<p>x</p>",
        datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc), "de",
    )
    assert "<h1>Mein Titel</h1>" in datei
    assert "<p>Quelle: https://example.org/a, abgerufen am 08.09.2026</p>" in datei
    assert 'charset="utf-8"' in datei


def test_dokument_kopfzeile_auf_englisch():
    datei = wpe.build_document_html("T", "https://example.org/a", "", datetime(2026, 9, 8, tzinfo=timezone.utc), "en")
    assert "Source: https://example.org/a, fetched on 2026-09-08" in datei


def test_dokument_maskiert_titel():
    datei = wpe.build_document_html("<b>x</b>", "https://example.org/a?b=1&c=2", "", datetime.now(timezone.utc), "de")
    assert "<h1>&lt;b&gt;x&lt;/b&gt;</h1>" in datei
    assert "b=1&amp;c=2" in datei


def test_textseite_wird_zu_absaetzen():
    text = ("Erster Absatz. " * 40 + "\n\n" + "Zweiter Absatz. " * 40).encode("utf-8")
    doc = wpe.extract_text_page(text, "https://example.org/notizen.txt")
    assert doc.body_html.count("<p>") == 2
    assert doc.title == "example.org/notizen.txt"


def test_textseite_maskiert_html():
    text = ("<b>fett</b> " * 120).encode("utf-8")
    doc = wpe.extract_text_page(text, "https://example.org/t")
    assert "<b>" not in doc.body_html
    assert "&lt;b&gt;" in doc.body_html


@pytest.mark.parametrize("roh,erwartet", [
    ('Was: ist <das>? / Teil 1', "Was ist das Teil 1"),
    ("   viele    Leerzeichen   ", "viele Leerzeichen"),
    ("", "seite"),
    ("Punkt am Ende...", "Punkt am Ende"),
    ("x" * 300, "x" * 120),
])
def test_sicherer_dateiname(roh, erwartet):
    assert wpe.safe_filename(roh) == erwartet


def test_pdf_titel_aus_dem_link():
    assert wpe.pdf_title_from_url("https://example.org/lehre/Skript%20WS.pdf") == "Skript WS"
    assert wpe.pdf_title_from_url("https://example.org/") == "example.org"
