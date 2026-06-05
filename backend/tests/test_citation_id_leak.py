"""The model sometimes leaks the internal chunk/source id mechanism into prose as a
closing meta-sentence ("Alle genannten Informationen stammen aus den Dokumenten mit
den IDs #1 und #2."). A '#<digit>' in the FINAL answer is ALWAYS leakage — real
citations are resolved to '[N, S. X | kw]' chips, which never contain '#'. So we
drop a trailing clause carrying a stray '#<digit>'. Structural, language-agnostic.
"""
from src.features.ai_assistant.routes._helpers import _strip_chunk_id_leak


def test_strips_trailing_id_meta_sentence():
    text = ("Die Recherche erfolgt systematisch [1, S. 12 | Recherche]. "
            "Alle genannten Informationen stammen aus den Dokumenten mit den IDs #1 und #2.")
    assert _strip_chunk_id_leak(text) == "Die Recherche erfolgt systematisch [1, S. 12 | Recherche]."


def test_strips_leak_on_its_own_trailing_line():
    text = "Inhalt der Seite.\n\nQuelle ist Dokument #7."
    assert _strip_chunk_id_leak(text) == "Inhalt der Seite."


def test_keeps_text_without_leak():
    text = "Die Methode nutzt einen Test [1, S. 2 | Test]. Sie ist robust."
    assert _strip_chunk_id_leak(text) == text


def test_does_not_touch_resolved_chips():
    # Resolved chips contain no '#', so a normal answer is untouched.
    text = "Fakt eins [1, S. 5 | Fakt]. Fakt zwei [2, 03:12 | Clip]."
    assert _strip_chunk_id_leak(text) == text


def test_leak_with_hash_space_digit():
    text = "Zusammenfassung der Seite. Quellen: # 1 und # 2."
    assert _strip_chunk_id_leak(text) == "Zusammenfassung der Seite."


def test_empty_and_plain():
    assert _strip_chunk_id_leak("") == ""
    assert _strip_chunk_id_leak("Nur ein Satz ohne alles") == "Nur ein Satz ohne alles"
