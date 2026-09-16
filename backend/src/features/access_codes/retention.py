"""How long a locked test account is kept before the nightly sweep removes it."""

from src.features.admin.repository.settings import get_setting
from src.limits import ACCESS_ACCOUNT_DELETE_AFTER_DAYS

DELETE_AFTER_DAYS_SETTING = "access_account_delete_after_days"


def grace_period_days() -> int:
    """Days a locked test account stays readable for the admin, 0 switches the sweep off."""
    try:
        return int(get_setting(DELETE_AFTER_DAYS_SETTING, str(ACCESS_ACCOUNT_DELETE_AFTER_DAYS)))
    except (TypeError, ValueError):
        return ACCESS_ACCOUNT_DELETE_AFTER_DAYS
