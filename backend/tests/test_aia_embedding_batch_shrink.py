"""Tests fuer die selbstkorrigierende Stapelgroesse beim Embedding.

Frueher war "Chunks pro Aufruf" eine Admin-Einstellung. Sie konnte nur nach
unten, weil Standard und Obergrenze beide auf dem gemessenen Wert 1000 lagen,
und niemand kann von Hand wissen, was ein fremder Anbieter vertraegt. Statt des
Reglers findet der Client die Zahl jetzt selbst: lehnt der Endpunkt eine zu
grosse Anfrage ab, halbiert er den Stapel und versucht es erneut.

Wichtig ist die Unterscheidung zweier Absagen. "Zu gross" wird kleiner
versucht, eine Absage wegen des geteilten Rate-Limits NICHT, denn Halbieren
wuerde dort nur noch mehr Anfragen gegen das volle Kontingent erzeugen.
"""
import pytest

from src.limits import AIA_EMBEDDING_BATCH_SIZE
from src.services import aia_embeddings
from src.services.aia_embeddings import OpenAICompatEmbeddingProvider


@pytest.fixture(autouse=True)
def _frischer_lernspeicher():
    """Die gelernte Stapelgroesse lebt im Prozess. Zwischen Tests leeren."""
    aia_embeddings._learned_batch_size.clear()
    yield
    aia_embeddings._learned_batch_size.clear()


class _FakeEndpoint(OpenAICompatEmbeddingProvider):
    """Endpunkt, der Anfragen ueber ``max_inputs`` mit 502 ablehnt.

    Genau das Verhalten von myLab qwen3-embedding-4b: 1000 Eingaben gehen,
    2000 laufen in ein 502. Ein fremder Anbieter kann die Grenze anderswo haben.
    """

    def __init__(self, max_inputs: int) -> None:
        self.max_inputs = max_inputs
        self.gesendet: list[int] = []   # Eingaben je Anfrage, in Reihenfolge
        self.abgelehnt: list[int] = []  # davon die abgelehnten
        self._model = "fake-embed"
        self._key = ("http://fake/v1", "fake-embed")

    def _request(self, batch: list[str]) -> list[list[float]]:
        self.gesendet.append(len(batch))
        if len(batch) > self.max_inputs:
            self.abgelehnt.append(len(batch))
            raise RuntimeError("Error code: 502 - Bad Gateway")
        return [[0.1, 0.2, 0.3, 0.4] for _ in batch]


class _RateLimitedEndpoint(OpenAICompatEmbeddingProvider):
    """Endpunkt, der die ersten ``fehlversuche`` Anfragen mit 429 abweist."""

    def __init__(self, fehlversuche: int) -> None:
        self.offen = fehlversuche
        self.gesendet: list[int] = []
        self._model = "fake-embed"
        self._key = ("http://fake/v1", "fake-embed")

    def _request(self, batch: list[str]) -> list[list[float]]:
        self.gesendet.append(len(batch))
        if self.offen > 0:
            self.offen -= 1
            raise RuntimeError("Error code: 429 - Too Many Requests")
        return [[0.1, 0.2, 0.3, 0.4] for _ in batch]


def test_halbiert_bis_der_endpunkt_den_stapel_annimmt():
    p = _FakeEndpoint(max_inputs=300)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    # 700 auf einmal abgelehnt, 500 abgelehnt, ab 250 nimmt der Endpunkt an
    assert p.abgelehnt == [700, 500]
    assert all(n <= 300 for n in p.gesendet if n not in (700, 500))


def test_gelernte_groesse_gilt_auch_fuer_die_naechste_quelle():
    """Der Provider wird pro Upload neu gebaut. Ohne Gedaechtnis wuerde jede
    Quelle die Grenze neu ertasten und dabei Aufrufe am Rate-Limit verbrennen."""
    erste = _FakeEndpoint(max_inputs=300)
    erste.embed([f"chunk {i}" for i in range(700)])

    zweite = _FakeEndpoint(max_inputs=300)
    zweite.embed([f"chunk {i}" for i in range(700)])

    assert zweite.abgelehnt == []


def test_rate_limit_wird_wiederholt_und_nicht_halbiert(monkeypatch):
    monkeypatch.setattr(aia_embeddings.time, "sleep", lambda _s: None)
    p = _RateLimitedEndpoint(fehlversuche=1)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    assert p.gesendet == [700, 700]  # gleiche Groesse noch einmal, kein Halbieren


def test_gibt_nach_begrenzt_vielen_versuchen_auf():
    """Ein dauerhaft kaputter Endpunkt darf sich nicht bis auf 1 herunterhalbieren
    und dabei hunderte Anfragen absetzen."""
    p = _FakeEndpoint(max_inputs=0)

    with pytest.raises(RuntimeError):
        p.embed([f"chunk {i}" for i in range(700)])

    assert p.gesendet == [700, 500, 250, 125]


def test_dauerabsage_senkt_die_gelernte_groesse_nicht():
    """Gelernt wird nur eine Groesse, die der Endpunkt wirklich angenommen hat.
    Sonst wuerde eine voruebergehende Stoerung die Groesse dauerhaft druecken."""
    kaputt = _FakeEndpoint(max_inputs=0)
    with pytest.raises(RuntimeError):
        kaputt.embed([f"chunk {i}" for i in range(700)])

    wieder_da = _FakeEndpoint(max_inputs=AIA_EMBEDDING_BATCH_SIZE)
    wieder_da.embed([f"chunk {i}" for i in range(700)])

    assert wieder_da.gesendet == [700]
