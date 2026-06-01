from src.features.ai_assistant.routes._helpers import fill_uncited_lines
from src.features.ai_assistant.routes._citation_match import Unit


class _FakeLoader:
    def __init__(self, units): self._u = units
    def units(self, source, *, is_media): return self._u


def test_fills_only_uncited_groundable_lines():
    text = (
        "## Überblick\n"
        "- Das Paper hat sechs bis sieben Seiten.\n"
        "- Schon zitiert. [2, S. 5 | foo]\n"
    )
    units = [Unit(page=5, start_time=None, end_time=None,
                  raw_text="das Paper hat sechs bis sieben Seiten plus Literaturverzeichnis")]
    sources = {2: {"source": {"id": 2, "filename": "x.pdf"}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    lines = out.splitlines()
    assert lines[0] == "## Überblick"            # heading untouched
    assert "[2, S. 5 |" in lines[1]              # first bullet now cited
    assert "[2, S. 5 | foo]" in lines[2]         # pre-existing citation untouched
    assert out.count("[2, S. 5 |") == 2          # one added + one pre-existing
