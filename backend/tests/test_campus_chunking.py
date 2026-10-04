"""Chunks tragen ihre Überschriftenkette, kurze Abschnitte werden zusammengelegt."""
from src.features.campus.services.chunking import split_markdown

MD = """# Beratung

Allgemeiner Einstieg in zwei Sätzen. Noch ein Satz dazu.

## Sprechzeiten

Dienstag 14 bis 16 Uhr.

## Kontakt

Telefon 0451 300 5447.

# Newsletter

""" + ("Lange Zeile mit vielen Wörtern zum Auffüllen des Abschnitts. " * 60)


def test_ueberschriftenkette_steht_im_chunk():
    chunks = split_markdown(MD, piece_chars=600, overlap=100)
    assert chunks[0]["position"] == 0
    assert chunks[0]["heading"] == "Beratung"
    assert chunks[0]["content"].startswith("Beratung\n")
    # The three short sections share one chunk, the later headings stay inside the text.
    assert "Sprechzeiten" in chunks[0]["content"] and "Kontakt" in chunks[0]["content"]


def test_langer_abschnitt_wird_geteilt_und_behaelt_die_kette():
    chunks = split_markdown(MD, piece_chars=600, overlap=100)
    newsletter = [c for c in chunks if c["heading"] == "Newsletter"]
    assert len(newsletter) >= 4
    assert all(c["content"].startswith("Newsletter\n") for c in newsletter)
    assert [c["position"] for c in chunks] == list(range(len(chunks)))


def test_text_ohne_ueberschrift():
    chunks = split_markdown("Nur ein Absatz ohne Überschrift.")
    assert chunks == [{"position": 0, "heading": None, "content": "Nur ein Absatz ohne Überschrift."}]
