"""Der Modul-Schalter aus der .env."""
import pytest

from src.modules import ALL_MODULES, ModuleConfigError, parse_modules


def test_leerer_wert_gibt_alle_module():
    assert parse_modules("") == frozenset(ALL_MODULES)


def test_nur_leerzeichen_gibt_alle_module():
    assert parse_modules("   ") == frozenset(ALL_MODULES)


def test_einzelnes_modul():
    assert parse_modules("aia") == frozenset({"aia"})


def test_beide_module_mit_leerzeichen_und_grossschreibung():
    assert parse_modules(" AIA , tools ") == frozenset({"aia", "tools"})


def test_doppelter_eintrag_zaehlt_einmal():
    assert parse_modules("tools,tools") == frozenset({"tools"})


def test_unbekanntes_modul_wird_abgelehnt():
    with pytest.raises(ModuleConfigError) as e:
        parse_modules("aia,screencast")
    assert "screencast" in str(e.value)


def test_nur_unbekannte_module_werden_abgelehnt():
    with pytest.raises(ModuleConfigError):
        parse_modules("quatsch")
