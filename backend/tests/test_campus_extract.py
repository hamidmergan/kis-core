"""Aus einer Seite wird Markdown mit Überschriften, Menü und Fußzeile fallen weg."""
from src.features.campus.services import extract

SEITE = """<html><head><title>Wohnen – Hochschule</title></head><body>
<nav><ul><li><a href="/a">Studium</a></li><li><a href="/b">Forschung</a></li></ul></nav>
<main><article>
<h1>Wohnen und Verpflegung</h1>
<p>Wohnheime sind die preiswerteste Wohnform außerhalb des Elternhauses. Sie werden zum größten Teil vom Studentenwerk betrieben, aber es gibt auch private Anbieter in der Stadt.</p>
<h2>Mensa</h2>
<p>Die Mensa bietet täglich drei bis vier frische Gerichte, darunter mindestens ein vegetarisches Gericht, und eine Auswahl an Desserts für alle Studierenden.</p>
</article></main>
<footer><p>Impressum Datenschutz Kontakt</p></footer>
</body></html>"""


def test_markdown_mit_ueberschriften_und_titel():
    e = extract.extract_markdown(SEITE, "https://x.test/wohnen/")
    assert e is not None
    assert e.title.startswith("Wohnen")
    assert "## Mensa" in e.markdown or "# Mensa" in e.markdown
    assert "Wohnheime sind die preiswerteste" in e.markdown
    assert "Impressum" not in e.markdown


def test_leere_seite_ergibt_none():
    assert extract.extract_markdown("<html><body><p>kurz</p></body></html>", "https://x.test/") is None


def test_hash_ist_stabil():
    assert extract.content_hash("abc") == extract.content_hash("abc")
    assert extract.content_hash("abc") != extract.content_hash("abd")


def test_cookie_banner_wird_nicht_als_haupttext_genommen():
    banner = "<section aria-label='cookie-consent'><div>" + "Cookie Hinweis Datenschutz Einwilligung " * 40 + "</div></section>"
    inhalt = "<div><p>" + "Semesterdauer 01.09.2026 bis 28.02.2027 Rueckmeldung im Juni. " * 3 + "</p></div>"
    out = extract.extract_markdown(f"<html><body>{banner}{inhalt}</body></html>", "https://x.test/k/")
    assert out is not None and "Semesterdauer" in out.markdown and "Cookie Hinweis" not in out.markdown
