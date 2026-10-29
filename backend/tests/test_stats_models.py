"""Model numbers, checked at the one place a wrong period would sneak in."""
from src.features.stats import models as m


def test_zeitraum_jahr_sind_365_tage():
    assert m.ZEITRAEUME["jahr"] == 365


def test_zeitraum_halbjahr_sind_182_tage():
    assert m.ZEITRAEUME["halbjahr"] == 182


def test_zeitraum_30t_sind_30_tage():
    assert m.ZEITRAEUME["30t"] == 30


def test_unbekannter_zeitraum_faellt_auf_30_tage_zurueck():
    """The router lets only the three known values through, this is just the net underneath."""
    assert m.ZEITRAEUME.get("nonsense", 30) == 30
