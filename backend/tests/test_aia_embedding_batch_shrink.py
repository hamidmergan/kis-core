"""Checks the self-correcting batch size and the three kinds of refusal."""
import pytest

from src.limits import AIA_EMBEDDING_BATCH_SIZE
from src.services import aia_embeddings
from src.services.aia_embeddings import OpenAICompatEmbeddingProvider


@pytest.fixture(autouse=True)
def _frischer_lernspeicher():
    """The learned batch size lives in the process, clear it between tests."""
    aia_embeddings._learned_batch_size.clear()
    yield
    aia_embeddings._learned_batch_size.clear()


class _FakeEndpoint(OpenAICompatEmbeddingProvider):
    """An endpoint that rejects oversized requests with 502."""

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
    """Endpoint that rejects the first ``fehlversuche`` requests with 429."""

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


class _HaengenderEndpunkt(OpenAICompatEmbeddingProvider):
    """An endpoint that lets the first requests run into the timeout."""

    def __init__(self, fehlversuche: int, retry_on_timeout: bool = True) -> None:
        self.offen = fehlversuche
        self.gesendet: list[int] = []
        self._model = "fake-embed"
        self._key = ("http://fake/v1", "fake-embed")
        self._retry_on_timeout = retry_on_timeout

    def _request(self, batch: list[str]) -> list[list[float]]:
        self.gesendet.append(len(batch))
        if self.offen > 0:
            self.offen -= 1
            raise RuntimeError("Request timed out.")
        return [[0.1, 0.2, 0.3, 0.4] for _ in batch]


def test_halbiert_bis_der_endpunkt_den_stapel_annimmt():
    p = _FakeEndpoint(max_inputs=300)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    # 700 at once rejected, 500 rejected, from 250 on the endpoint accepts
    assert p.abgelehnt == [700, 500]
    assert all(n <= 300 for n in p.gesendet if n not in (700, 500))


def test_gelernte_groesse_gilt_auch_fuer_die_naechste_quelle():
    """Without memory every source would feel out the limit again."""
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
    """A permanently broken endpoint must not halve itself down to 1."""
    p = _FakeEndpoint(max_inputs=0)

    with pytest.raises(RuntimeError):
        p.embed([f"chunk {i}" for i in range(700)])

    assert p.gesendet == [700, 500, 250, 125]


class _LangsamerEndpunkt(OpenAICompatEmbeddingProvider):
    """A live endpoint that runs into the timeout on too many inputs."""

    def __init__(self, max_inputs: int) -> None:
        self.max_inputs = max_inputs
        self.gesendet: list[int] = []
        self._model = "fake-embed"
        self._key = ("http://fake/v1", "fake-embed")
        self._retry_on_timeout = True

    def _request(self, batch: list[str]) -> list[list[float]]:
        self.gesendet.append(len(batch))
        if len(batch) > self.max_inputs:
            raise RuntimeError("Request timed out.")
        return [[0.1, 0.2, 0.3, 0.4] for _ in batch]


def test_langsamer_endpunkt_wird_nach_dem_zweitversuch_doch_kleiner():
    """First the same size once more, then cut smaller."""
    p = _LangsamerEndpunkt(max_inputs=300)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    assert p.gesendet == [700, 700, 500, 250, 250, 200]  # gleich, gleich, dann kleiner


def test_erfolg_eines_kleinen_stapels_senkt_die_gelernte_groesse_nicht():
    """Learning only happens on a full batch, otherwise a handful of rows poisons the upload."""
    klein = _FakeEndpoint(max_inputs=3)
    klein.embed([f"zeile {i}" for i in range(6)])
    assert klein.gesendet == [6, 3, 3]  # 6 abgelehnt, dann zweimal 3

    upload = _FakeEndpoint(max_inputs=AIA_EMBEDDING_BATCH_SIZE)
    upload.embed([f"chunk {i}" for i in range(700)])

    assert upload.gesendet == [700]  # voller Stapel, nicht auf 3 gedrosselt


def test_kleiner_stapel_wird_nicht_unveraendert_wiederholt():
    """Halving only counts when the next request really gets smaller."""
    p = _FakeEndpoint(max_inputs=0)

    with pytest.raises(RuntimeError):
        p.embed([f"zeile {i}" for i in range(6)])

    assert p.gesendet == [6, 3, 1]  # jede Wiederholung ist echt kleiner


def test_zeitueberschreitung_wird_nicht_halbiert():
    """A timeout says nothing about the batch size."""
    p = _HaengenderEndpunkt(fehlversuche=1)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    assert p.gesendet == [700, 700]  # gleiche Groesse noch einmal, kein Halbieren


def test_tote_gegenstelle_bleibt_im_hintergrund_begrenzt():
    """The number of attempts has to stay capped."""
    p = _HaengenderEndpunkt(fehlversuche=99)

    with pytest.raises(RuntimeError):
        p.embed([f"chunk {i}" for i in range(700)])

    assert p.gesendet == [700, 700, 500, 250, 125]


def test_fail_fast_wartet_kein_zweites_mal():
    """For the source chips the timeout is paid exactly once."""
    p = _HaengenderEndpunkt(fehlversuche=99, retry_on_timeout=False)

    with pytest.raises(RuntimeError):
        p.embed([f"chunk {i}" for i in range(700)])

    assert p.gesendet == [700]


def test_dauerabsage_senkt_die_gelernte_groesse_nicht():
    """Only a size the endpoint really accepted is learned."""
    kaputt = _FakeEndpoint(max_inputs=0)
    with pytest.raises(RuntimeError):
        kaputt.embed([f"chunk {i}" for i in range(700)])

    wieder_da = _FakeEndpoint(max_inputs=AIA_EMBEDDING_BATCH_SIZE)
    wieder_da.embed([f"chunk {i}" for i in range(700)])

    assert wieder_da.gesendet == [700]
