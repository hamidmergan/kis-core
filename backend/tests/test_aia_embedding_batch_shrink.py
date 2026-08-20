"""Tests fuer die selbstkorrigierende Stapelgroesse beim Embedding.

Frueher war "Chunks pro Aufruf" eine Admin-Einstellung. Sie konnte nur nach
unten, weil Standard und Obergrenze beide auf dem gemessenen Wert 1000 lagen,
und niemand kann von Hand wissen, was ein fremder Anbieter vertraegt. Statt des
Reglers findet der Client die Zahl jetzt selbst: lehnt der Endpunkt eine zu
grosse Anfrage ab, halbiert er den Stapel und versucht es erneut.

Wichtig ist die Unterscheidung zweier Absagen. "Zu gross" wird kleiner
versucht, eine Absage wegen Ueberlastung NICHT, denn Halbieren wuerde dort
nur noch mehr Anfragen erzeugen.
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


class _HaengenderEndpunkt(OpenAICompatEmbeddingProvider):
    """Endpunkt, der die ersten ``fehlversuche`` Anfragen in die Zeitschranke laufen
    laesst. Genau der Fall, der die Quellenchips minutenlang aufgehalten hat."""

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


class _LangsamerEndpunkt(OpenAICompatEmbeddingProvider):
    """Endpunkt, der lebt, aber ueber ``max_inputs`` in die Zeitschranke laeuft.

    Der Unterschied zu einer toten Gegenstelle: hier hilft ein kleinerer Stapel
    sehr wohl. Ein Upload muss diesen Weg noch finden.
    """

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
    """Ein Upload darf an einer nur langsamen Gegenstelle nicht scheitern.

    Erst gleiche Groesse noch einmal (vielleicht war es ein Aussetzer), und erst
    wenn auch das in die Schranke laeuft, kleiner schneiden. Ohne diesen zweiten
    Schritt wuerde jeder Anbieter, der 1000 Eingaben nicht in der Zeit schafft,
    den ganzen Upload abbrechen.
    """
    p = _LangsamerEndpunkt(max_inputs=300)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    assert p.gesendet == [700, 700, 500, 250, 250, 200]  # gleich, gleich, dann kleiner


def test_erfolg_eines_kleinen_stapels_senkt_die_gelernte_groesse_nicht():
    """Sonst vergiftet eine Handvoll Chip-Zeilen den naechsten Upload.

    Nimmt der Endpunkt 3 von 6 Zeilen an, heisst das NICHT, dass seine Grenze bei
    3 liegt. Gelernt wird nur an einem Stapel, der die Grenze wirklich ausgereizt
    hat, also einem vollen. Sonst liefe der naechste Upload mit 1000 Chunks in
    Dreier-Haeppchen los.
    """
    klein = _FakeEndpoint(max_inputs=3)
    klein.embed([f"zeile {i}" for i in range(6)])
    assert klein.gesendet == [6, 3, 3]  # 6 abgelehnt, dann zweimal 3

    upload = _FakeEndpoint(max_inputs=AIA_EMBEDDING_BATCH_SIZE)
    upload.embed([f"chunk {i}" for i in range(700)])

    assert upload.gesendet == [700]  # voller Stapel, nicht auf 3 gedrosselt


def test_kleiner_stapel_wird_nicht_unveraendert_wiederholt():
    """Halbieren darf nur zaehlen, wenn die naechste Anfrage wirklich kleiner wird.

    Die gelernte Groesse (1000) lag weit ueber dem Stapel, den die Quellenchips
    schicken (eine Handvoll Zeilen). Die Absage halbierte 1000 auf 500, der Stapel
    blieb bei 6 und dieselbe Anfrage ging viermal raus. Bei einer haengenden
    Gegenstelle sind das viermal die volle Wartezeit fuer nichts.
    """
    p = _FakeEndpoint(max_inputs=0)

    with pytest.raises(RuntimeError):
        p.embed([f"zeile {i}" for i in range(6)])

    assert p.gesendet == [6, 3, 1]  # jede Wiederholung ist echt kleiner


def test_zeitueberschreitung_wird_nicht_halbiert():
    """Eine Zeitschranke sagt nichts ueber die Stapelgroesse, sondern dass die
    Gegenstelle nicht antwortet. Kleiner schneiden hilft dort nie und kostet jedes
    Mal die volle Wartezeit noch einmal."""
    p = _HaengenderEndpunkt(fehlversuche=1)

    vektoren = p.embed([f"chunk {i}" for i in range(700)])

    assert len(vektoren) == 700
    assert p.gesendet == [700, 700]  # gleiche Groesse noch einmal, kein Halbieren


def test_tote_gegenstelle_bleibt_im_hintergrund_begrenzt():
    """Der Upload darf es zweimal gleich gross und danach kleiner versuchen, aber
    die Zahl der Versuche muss gedeckelt bleiben. Sonst haelt eine tote Gegenstelle
    einen Worker beliebig lange fest."""
    p = _HaengenderEndpunkt(fehlversuche=99)

    with pytest.raises(RuntimeError):
        p.embed([f"chunk {i}" for i in range(700)])

    assert p.gesendet == [700, 700, 500, 250, 125]


def test_fail_fast_wartet_kein_zweites_mal():
    """Die Quellenchips sind eine Zugabe, keine Antwort. Auf diesem Weg wird die
    Zeitschranke genau einmal bezahlt und die Antwort geht ohne Chips raus."""
    p = _HaengenderEndpunkt(fehlversuche=99, retry_on_timeout=False)

    with pytest.raises(RuntimeError):
        p.embed([f"chunk {i}" for i in range(700)])

    assert p.gesendet == [700]


def test_dauerabsage_senkt_die_gelernte_groesse_nicht():
    """Gelernt wird nur eine Groesse, die der Endpunkt wirklich angenommen hat.
    Sonst wuerde eine voruebergehende Stoerung die Groesse dauerhaft druecken."""
    kaputt = _FakeEndpoint(max_inputs=0)
    with pytest.raises(RuntimeError):
        kaputt.embed([f"chunk {i}" for i in range(700)])

    wieder_da = _FakeEndpoint(max_inputs=AIA_EMBEDDING_BATCH_SIZE)
    wieder_da.embed([f"chunk {i}" for i in range(700)])

    assert wieder_da.gesendet == [700]
