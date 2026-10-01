"""Calendar colours: free ones first, a choice swaps instead of doubling."""
import random

from src.features.ai_assistant.scheduling import farben


def test_fuenfzehn_gruppen_bekommen_fuenfzehn_verschiedene_farben():
    gruppen = [f"ws{i}" for i in range(len(farben.PALETTE))]
    neu = farben.vergeben(gruppen, {}, random.Random(1))
    assert sorted(neu.values()) == list(range(len(farben.PALETTE)))


def test_neue_gruppe_nimmt_keine_belegte_farbe():
    vorhanden = {"a": 0, "b": 1}
    for seed in range(50):
        neu = farben.vergeben(["a", "b", "c"], vorhanden, random.Random(seed))
        assert set(neu) == {"c"} and neu["c"] not in (0, 1)


def test_alte_eintraege_ohne_gruppe_belegen_nichts():
    neu = farben.vergeben(["c"], {"geloescht": 3}, random.Random(0))
    assert set(neu) == {"c"}
    assert farben.vergeben(["c"], {"c": 3}) == {}


def test_privat_behaelt_seine_farbe_wenn_frei():
    assert farben.vergeben([farben.PRIVAT], {}) == {farben.PRIVAT: farben._PRIVAT_VORZUG}


def test_mehr_gruppen_als_farben_nimmt_die_seltenste():
    n = len(farben.PALETTE)
    gruppen = [f"ws{i}" for i in range(n + 1)]
    vorhanden = {f"ws{i}": i for i in range(n)}
    neu = farben.vergeben(gruppen, vorhanden, random.Random(0))
    assert list(neu) == [f"ws{n}"]


def test_wahl_einer_belegten_farbe_tauscht():
    vorhanden = {"a": 0, "b": 1, "c": 2}
    assert farben.waehlen(["a", "b", "c"], vorhanden, "a", 1) == {"a": 1, "b": 0}


def test_wahl_einer_freien_farbe_aendert_nur_die_gruppe():
    assert farben.waehlen(["a", "b"], {"a": 0, "b": 1}, "a", 5) == {"a": 5}
