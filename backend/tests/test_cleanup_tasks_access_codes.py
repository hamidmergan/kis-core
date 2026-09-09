"""The hourly job that locks accounts whose event access ran out."""

from unittest.mock import patch


def test_the_task_locks_expired_accounts_and_returns_how_many():
    from src.tasks.cleanup_tasks import run_lock_expired_access_accounts

    with patch(
        "src.tasks.cleanup_tasks.repo.lock_expired_accounts", return_value=3
    ) as sperren:
        ergebnis = run_lock_expired_access_accounts()

    assert ergebnis == 3
    sperren.assert_called_once_with()


def test_the_task_swallows_errors_so_the_beat_schedule_keeps_running():
    from src.tasks.cleanup_tasks import run_lock_expired_access_accounts

    with patch(
        "src.tasks.cleanup_tasks.repo.lock_expired_accounts", side_effect=RuntimeError("db down")
    ):
        ergebnis = run_lock_expired_access_accounts()

    assert ergebnis == 0
