"""Every demo module lands in every account once, no matter how that account came to be."""
from loguru import logger

from src import database


def demo_module_zuweisen(user_id: int) -> list[str]:
    """Joins each demo course this account has not been offered yet, returns their uuids."""
    try:
        beigetreten = []
        for kurs in database.get_demo_workspaces(user_id):
            if kurs["seeded"] or kurs["owned"]:
                continue
            # The mark goes first, so two parallel logins never enroll twice.
            if not database.claim_demo_seeding(kurs["id"], user_id):
                continue
            if kurs["joined"]:
                continue
            if database.enroll_student(kurs["id"], user_id, None, via_demo=True):
                beigetreten.append(kurs["uuid"])
        if beigetreten:
            logger.info("Demo: Konto {} in {} Module eingeschrieben", user_id, len(beigetreten))
        return beigetreten
    except Exception as fehler:
        # A login must never fail over this.
        logger.error("Demo-Zuweisung fuer Konto {} fehlgeschlagen: {}", user_id, fehler)
        return []
