"""The source summary is written in the language read from the text, not guessed by the model."""

from src.services import aia_summarizer as sm

# A table of contents in German, crowded with English technical terms, misled the model.
INHALT = (
    "GVT Graphical Visualisation Technologies. 1 Einleitung, Überblick und Lernziele, "
    "Literatur und Links, Voraussetzungen und Bearbeitungsanleitung. 2 Rendering Pipeline, "
    "Vertex Shader und Fragment Shader werden in diesem Kapitel ausführlich erklärt. "
    "3 WebGL Grundlagen, Buffer, Texturen und Beleuchtung mit Übungen und Wissensüberprüfung. "
    "Die Zusammenfassung am Ende jedes Kapitels fasst die wichtigsten Begriffe noch einmal zusammen."
)


class _Client:
    def __init__(self):
        self.systems = []
        self.chat = self
        self.completions = self

    def create(self, **kw):
        self.systems.append(kw["messages"][0]["content"])
        msg = type("M", (), {"content": "Kurzfassung des Kapitels."})
        return type("R", (), {"choices": [type("C", (), {"message": msg})]})


def test_every_call_names_the_language_of_the_text():
    client = _Client()
    # A small cap forces several batches and a merge.
    sm.build_source_summary([{"content": INHALT}] * 3, client, "m", len(INHALT), retries=0)
    assert len(client.systems) == 4
    assert all("Write in German. This is fixed." in s for s in client.systems)


def test_an_unclear_text_leaves_the_judgement_to_the_model():
    client = _Client()
    sm.build_source_summary([{"content": "S. 12"}], client, "m", 1000, retries=0)
    assert "DOMINANT language" in client.systems[0]
