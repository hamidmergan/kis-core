"""Prüft das gleichzeitige Schreiben: höchstens drei, nach Überlastung einzeln, nie doppelt."""

import asyncio

import httpx
import openai
import pytest

from src.features.summary import concurrency as cc


class _Zaehler:
    """Merkt sich, wie viele Aufgaben höchstens gleichzeitig liefen."""

    def __init__(self):
        self.jetzt = 0
        self.hoechstens = 0
        self.danach: list[int] = []

    def aufgabe(self, wert, fehler=()):
        """Eine Aufgabe, die bei jedem Aufruf den nächsten Fehler aus der Liste wirft."""
        fehler = list(fehler)

        async def lauf():
            self.jetzt += 1
            self.hoechstens = max(self.hoechstens, self.jetzt)
            self.danach.append(self.jetzt)
            try:
                await asyncio.sleep(0.01)
                if fehler:
                    raise fehler.pop(0)
                return wert
            finally:
                self.jetzt -= 1
        return lauf


def _zeitueberschreitung():
    return openai.APITimeoutError(request=httpx.Request("POST", "http://modell"))


async def test_hoechstens_drei_laufen_gleichzeitig():
    z = _Zaehler()
    ergebnis = await cc.run_limited([z.aufgabe(i) for i in range(7)], 3)
    assert ergebnis == list(range(7))
    assert z.hoechstens == 3


async def test_nach_einer_zeitueberschreitung_geht_es_einzeln_weiter():
    z = _Zaehler()
    aufgaben = [z.aufgabe(0, [_zeitueberschreitung()])] + [z.aufgabe(i) for i in range(1, 7)]
    ergebnis = await cc.run_limited(aufgaben, 3)
    assert ergebnis == list(range(7))
    # Once the provider struggled, every later start finds itself alone.
    erst_ab = z.danach.index(3) + 1
    assert all(n == 1 for n in z.danach[erst_ab + 2:])


async def test_ein_anbieter_der_ueberlastet_meldet_zaehlt_wie_eine_zeitueberschreitung():
    z = _Zaehler()
    ueberlastet = openai.InternalServerError(
        "Service Unavailable", response=httpx.Response(503, request=httpx.Request("POST", "http://m")),
        body=None)
    assert await cc.run_limited([z.aufgabe("a", [ueberlastet])], 3) == ["a"]


async def test_ein_echter_fehler_bricht_ab():
    z = _Zaehler()
    with pytest.raises(ValueError):
        await cc.run_limited([z.aufgabe("a", [ValueError("kaputt")])], 3)


async def test_ein_zweites_scheitern_derselben_aufgabe_bricht_ab():
    z = _Zaehler()
    with pytest.raises(openai.APITimeoutError):
        await cc.run_limited([z.aufgabe("a", [_zeitueberschreitung(), _zeitueberschreitung()])], 3)


async def test_nach_dem_haltesignal_startet_nichts_mehr():
    z = _Zaehler()
    gestartet = []

    def darf():
        return len(gestartet) < 2

    async def merken(i):
        gestartet.append(i)
        return await z.aufgabe(i)()

    aufgaben = [lambda i=i: merken(i) for i in range(5)]
    ergebnis = await cc.run_limited(aufgaben, 1, may_start=darf)
    assert ergebnis == [0, 1, cc.SKIPPED, cc.SKIPPED, cc.SKIPPED]
