"""A span whose end lies before its start is not a span."""

from datetime import date

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes.schedule_personal import _validate_range


def test_ende_nach_anfang_ist_in_ordnung():
    _validate_range(date(2027, 2, 15), date(2027, 2, 26), "de")


def test_ende_gleich_anfang_ist_in_ordnung():
    """A span over exactly one day is allowed, it is simply one day."""
    _validate_range(date(2027, 2, 15), date(2027, 2, 15), "de")


def test_ohne_ende_ist_in_ordnung():
    _validate_range(date(2027, 2, 15), None, "de")


def test_ende_vor_anfang_wird_abgelehnt():
    with pytest.raises(HTTPException) as fehler:
        _validate_range(date(2027, 2, 26), date(2027, 2, 15), "de")
    assert fehler.value.status_code == 400


def test_ende_einen_tag_vor_dem_anfang_wird_abgelehnt():
    """The tightest case counts too, not only the obvious one."""
    with pytest.raises(HTTPException):
        _validate_range(date(2027, 2, 16), date(2027, 2, 15), "de")
