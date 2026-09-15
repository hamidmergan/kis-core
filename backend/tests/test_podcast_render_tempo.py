"""The chosen tempo has to reach the speech provider, not a fixed value on the way."""

from src.tasks.podcast_tasks import _render


class _FakeTts:
    """Remembers with which tempo every piece was spoken."""

    def __init__(self):
        self.tempi = []

    def synthesize_chunk(self, text, voice_id="", speed=1.0, language="de"):
        self.tempi.append(speed)
        return b"ton"


def test_das_gewaehlte_tempo_geht_an_den_anbieter():
    client = _FakeTts()
    _render._sprich(client, "Ein Satz.", "anna", "de", 0.7)
    assert client.tempi == [0.7]


def test_jedes_stueck_eines_langen_beitrags_bekommt_dasselbe_tempo():
    client = _FakeTts()
    _render._sprich(client, "Ein Satz. " * 200, "anna", "de", 1.2)
    assert len(client.tempi) > 1
    assert set(client.tempi) == {1.2}
