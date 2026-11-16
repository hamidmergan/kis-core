"""The calendar day as the people using the platform see it."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

# The one time zone every local time and day of the platform is shown in.
LOCAL_TZ = ZoneInfo("Europe/Berlin")


def today() -> date:
    """Today in Germany, the containers run on UTC and would be a day behind after midnight."""
    return datetime.now(LOCAL_TZ).date()
