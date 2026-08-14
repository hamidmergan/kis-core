"""Adminbereich: den Fragen-Plan der Einstufung einmal von der KI schreiben lassen.

Der Endpunkt speichert NICHT. Er gibt die Fragen zurueck, die Karte im Adminbereich
traegt sie in die Liste ein und speichert sie ueber den gewohnten Weg. So laeuft
alles durch dieselbe Pruefung, und die Verwaltung sieht das Ergebnis, bevor es fuer
einen Kurs gilt.
"""

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_llm_client
from src.i18n import get_locale, t
from src.services.aia_diagnosis_authoring import (
    GENERATION_SLOTS,
    build_generation_messages,
    build_repair_message,
    parse_generated_plan,
)
from src.services.aia_diagnosis_chat import (
    LEVEL_EXAMPLES_SETTING,
    DiagnosisChatError,
    build_examples_block,
    parse_level_examples,
)
from src.services.aia_json_llm import ask_json
from src.services.aia_level_ladder import (
    LEVEL_DESCRIPTIONS_SETTING,
    build_levels_block,
    parse_level_descriptions,
)

from src.dependencies_rbac import require_permission
from src.permissions_registry import PERM_SET_AIA_LEVEL

router = APIRouter()

# Der Fragenplan gehoert zur Seite Sprachniveau.
_require = require_permission(PERM_SET_AIA_LEVEL)


async def _ask(llm, messages: list[dict], locale: str) -> str:
    """Ein Durchlauf. Eigene Funktion, damit ein Test sie ersetzen kann."""
    return await ask_json(llm, messages, locale=locale, what="Diagnosis plan generation")


@router.post("/settings/diagnosis-plan/generate")
async def generate_diagnosis_plan(
    _admin=Depends(_require),
    llm=Depends(get_llm_client),
    locale: str = Depends(get_locale),
):
    """Einen kompletten Fragen-Plan erzeugen, EIN Aufruf fuer die ganze Hochschule.

    Der Auftrag traegt die Stufen-Leiter aus dem Reiter KI-Verhalten, damit die
    Fragen zu derselben Skala passen, nach der spaeter eingestuft wird. Kommt eine
    unbrauchbare Antwort, wird genau einmal nachgefasst; danach gibt es eine klare
    Absage statt einer halben Liste.
    """
    levels = build_levels_block(
        parse_level_descriptions(db.get_setting(LEVEL_DESCRIPTIONS_SETTING, ""))
    )
    examples = build_examples_block(
        parse_level_examples(db.get_setting(LEVEL_EXAMPLES_SETTING, ""))
    )
    messages = build_generation_messages(levels, examples, GENERATION_SLOTS)

    raw = await _ask(llm, messages, locale)
    try:
        return {"questions": parse_generated_plan(raw, GENERATION_SLOTS)}
    except DiagnosisChatError as exc:
        logger.warning("Fragen-Plan unbrauchbar erzeugt: {} | roh: {!r}", exc, raw[:500])
        reason = str(exc)

    repaired = await _ask(
        llm,
        [*messages,
         {"role": "assistant", "content": raw},
         {"role": "system", "content": build_repair_message(reason)}],
        locale,
    )
    try:
        return {"questions": parse_generated_plan(repaired, GENERATION_SLOTS)}
    except DiagnosisChatError as exc:
        logger.warning("Fragen-Plan auch nach Nachfassen unbrauchbar: {} | roh: {!r}",
                       exc, repaired[:500])
        raise HTTPException(
            status_code=502,
            detail=t("admin.settings.diagnosisPlanGenerationFailed", locale),
        )
