"""The calendar day as the people using the platform see it."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

_BERLIN = ZoneInfo("Europe/Berlin")


def today() -> date:
    """Today in Germany, the containers run on UTC and would be a day behind after midnight."""
    return datetime.now(_BERLIN).date()
