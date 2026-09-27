"""The grace period before an expired test account is deleted, as an admin field."""

import pytest
from fastapi import HTTPException

from src.limits import ACCESS_ACCOUNT_DELETE_AFTER_DAYS
from src.permissions_registry import PERM_SET_USERS_ALL, SETTING_FIELD_PERMISSIONS
from src.routes.admin import settings as admin_settings
from src.features.access_codes.retention import DELETE_AFTER_DAYS_SETTING

_ADMIN = {"role": "admin"}


class _Body:
    """Minimal stand-in for UpdateSettingsRequest: everything None except one field."""

    def __init__(self, **kwargs):
        object.__setattr__(self, "_set", kwargs)

    def __getattr__(self, name):
        return object.__getattribute__(self, "_set").get(name)

    def model_dump(self):
        return dict(object.__getattribute__(self, "_set"))


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(
        admin_settings.db, "get_setting", lambda key, default="": data.get(key, default)
    )
    monkeypatch.setattr(
        admin_settings.db, "set_setting", lambda key, value: data.__setitem__(key, value)
    )
    return data


async def _speichern(tage):
    return admin_settings.update_settings(
        _Body(access_account_delete_after_days=tage), _ADMIN, "de"
    )


async def test_an_untouched_install_reads_thirty_days(store):
    antwort = admin_settings.get_settings(_ADMIN)

    assert antwort["access_account_delete_after_days"] == ACCESS_ACCOUNT_DELETE_AFTER_DAYS
    assert ACCESS_ACCOUNT_DELETE_AFTER_DAYS == 30


async def test_the_saved_value_comes_back_as_a_number(store):
    store[DELETE_AFTER_DAYS_SETTING] = "90"

    antwort = admin_settings.get_settings(_ADMIN)

    assert antwort["access_account_delete_after_days"] == 90


async def test_saving_a_longer_grace_period_works(store):
    await _speichern(90)

    assert store[DELETE_AFTER_DAYS_SETTING] == "90"


async def test_zero_switches_the_sweep_off(store):
    """Zero is the emergency exit and must pass the check."""
    await _speichern(0)

    assert store[DELETE_AFTER_DAYS_SETTING] == "0"


async def test_a_negative_grace_period_is_refused(store):
    with pytest.raises(HTTPException) as fehler:
        await _speichern(-1)

    assert fehler.value.status_code == 400
    assert DELETE_AFTER_DAYS_SETTING not in store


async def test_an_absurdly_long_grace_period_is_refused(store):
    """A typo like 3650000 would keep every account forever without anyone noticing."""
    with pytest.raises(HTTPException) as fehler:
        await _speichern(3651)

    assert fehler.value.status_code == 400
    assert DELETE_AFTER_DAYS_SETTING not in store


def test_the_field_belongs_to_the_user_administration():
    """Without a mapping the field silently falls to full admins only."""
    assert SETTING_FIELD_PERMISSIONS["access_account_delete_after_days"] == PERM_SET_USERS_ALL


def test_a_role_without_user_administration_may_not_change_it():
    class _NurWerkzeuge:
        keys = ("settings.werkzeuge.limits",)

    with pytest.raises(HTTPException) as fehler:
        admin_settings._assert_fields_allowed(
            _Body(access_account_delete_after_days=90), _NurWerkzeuge(), "de"
        )

    assert fehler.value.status_code == 403
