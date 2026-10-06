"""Switching off and removing the accounts that access codes created."""
from loguru import logger

from src.dependencies import get_session_store
from src.features.access_codes import repository as repo


def lock_accounts(user_ids: list[int]) -> int:
    """Blocks the login and ends every open session of these code accounts."""
    gesperrt = repo.set_users_active(user_ids, False)
    if gesperrt:
        get_session_store().destroy_for_users(gesperrt)
    return len(gesperrt)


def delete_accounts(user_ids: list[int]) -> int:
    """Removes these code accounts with everything they own, sessions included."""
    from src.features.admin.repository.user_delete import delete_user_completely
    from src.storage import delete_user_folder

    geloescht: list[int] = []
    for user_id in user_ids:
        try:
            delete_user_completely(user_id)
        except Exception as fehler:
            logger.warning("code account {} not deleted: {}", user_id, fehler)
            continue
        geloescht.append(user_id)
        # Storage comes after the database so an abort stays repeatable.
        try:
            delete_user_folder(user_id)
        except Exception as fehler:
            logger.warning("code account {}: files not deleted: {}", user_id, fehler)
    if geloescht:
        get_session_store().destroy_for_users(geloescht)
    return len(geloescht)
