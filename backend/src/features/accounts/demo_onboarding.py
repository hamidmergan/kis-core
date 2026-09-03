"""The demo module lands in every account once, no matter how that account came to be."""
from loguru import logger

from src import database


def demo_module_zuweisen(user_id: int) -> list[str]:
    """Joins the open demo courses on the first time in, returns their uuids."""
    try:
        if database.demo_seeding_done(user_id):
            return []
        kurse = database.get_demo_workspaces(user_id)
        # Without a demo module the mark stays empty, so a later one still reaches this account.
        if not kurse:
            return []
        if not database.claim_demo_seeding(user_id):
            return []
        beigetreten = [
            kurs["uuid"]
            for kurs in kurse
            if not kurs["joined"] and not kurs["owned"]
            and database.enroll_student(kurs["id"], user_id, None, via_demo=True)
        ]
        logger.info("Demo: Konto {} beim ersten Mal in {} Module eingeschrieben", user_id, len(beigetreten))
        return beigetreten
    except Exception as fehler:
        # A login must never fail over this.
        logger.error("Demo-Zuweisung fuer Konto {} fehlgeschlagen: {}", user_id, fehler)
        return []
