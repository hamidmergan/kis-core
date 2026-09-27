"""Plätze beim Anbieter: nie mehr gleichzeitige Anfragen, als er verkraftet, der Rest wartet bei uns."""

import pytest

from src.services import provider_slots


class _Redis:
    """Ein sortiertes Set wie in Redis, mit einer einstellbaren Uhr."""

    def __init__(self):
        self.sets: dict[str, dict[str, float]] = {}

    def zremrangebyscore(self, key, lo, hi):
        s = self.sets.setdefault(key, {})
        for k in [k for k, v in s.items() if v <= hi]:
            del s[k]

    def zcard(self, key):
        return len(self.sets.get(key, {}))

    def zadd(self, key, mapping):
        self.sets.setdefault(key, {}).update(mapping)

    def zrem(self, key, member):
        self.sets.get(key, {}).pop(member, None)


@pytest.fixture
def uhr(monkeypatch):
    stand = {"t": 1000.0}
    monkeypatch.setattr(provider_slots.time, "time", lambda: stand["t"])

    def schlafen(sek):
        stand["t"] += sek

    monkeypatch.setattr(provider_slots.time, "sleep", schlafen)
    return stand


def test_bis_zur_grenze_gibt_es_sofort_einen_platz(uhr):
    r = _Redis()
    for _ in range(4):
        assert provider_slots.claim("mylab", limit=4, wait_seconds=0, r=r)
    assert r.zcard("kis:provider-slots:mylab") == 4


def test_ueber_der_grenze_wartet_die_anfrage_und_gibt_dann_als_voll_auf(uhr):
    """Lasttest 26.09.: ab 12 gleichzeitigen Vertonungen scheiterte bei myLab jede einzelne."""
    r = _Redis()
    for _ in range(4):
        provider_slots.claim("mylab", limit=4, wait_seconds=0, r=r)
    start = uhr["t"]
    with pytest.raises(provider_slots.ProviderFull) as fehler:
        provider_slots.claim("mylab", limit=4, wait_seconds=30, r=r)
    assert uhr["t"] - start >= 30
    # Die Meldung muss als "Anbieter voll" erkannt werden, sonst zählt sie als Fehlversuch.
    from src.services.upstream_errors import is_upstream_busy
    assert is_upstream_busy(fehler.value)


def test_ein_freigegebener_platz_geht_an_den_naechsten(uhr):
    r = _Redis()
    tickets = [provider_slots.claim("mylab", limit=2, wait_seconds=0, r=r) for _ in range(2)]
    provider_slots.release("mylab", tickets[0], r=r)
    assert provider_slots.claim("mylab", limit=2, wait_seconds=0, r=r)


def test_ein_verwaister_platz_heilt_von_selbst(uhr):
    """Stirbt ein Arbeiter mitten in der Anfrage, darf sein Platz nicht ewig belegt bleiben."""
    r = _Redis()
    for _ in range(2):
        provider_slots.claim("mylab", limit=2, wait_seconds=0, r=r)
    uhr["t"] += provider_slots.STALE_SECONDS + 1
    assert provider_slots.claim("mylab", limit=2, wait_seconds=0, r=r)


def test_anbieter_zaehlen_getrennt(uhr):
    r = _Redis()
    provider_slots.claim("a", limit=1, wait_seconds=0, r=r)
    assert provider_slots.claim("b", limit=1, wait_seconds=0, r=r)


def test_ohne_redis_laeuft_die_anfrage_durch(uhr):
    class _Kaputt:
        def zremrangebyscore(self, *a):
            raise ConnectionError("weg")

    assert provider_slots.claim("mylab", limit=1, wait_seconds=0, r=_Kaputt())


def test_der_platz_wird_auch_bei_einem_fehler_zurueckgegeben(uhr):
    r = _Redis()
    with pytest.raises(RuntimeError):
        with provider_slots.slot("mylab", limit=1, wait_seconds=0, r=r):
            raise RuntimeError("Anbieter antwortet 500")
    assert r.zcard("kis:provider-slots:mylab") == 0
