"""KI-Assistent routes - popup actions."""


from fastapi import APIRouter, Depends, Query


from src.i18n import get_locale, TRANSCRIPT_LANGUAGES, DEFAULT_TRANSCRIPT_TARGET
from src.features.ai_assistant.prompts.popup_prompts import AIA_POPUP_ACTIONS


router = APIRouter(tags=["ki-assistent: popup"])

@router.get("/ai-assistant/popup-actions")
async def get_popup_actions(
    locale: str = Depends(get_locale),
    target: str = Query(DEFAULT_TRANSCRIPT_TARGET),
):
    """The selection bar actions in the reader's language."""
    label_key = "label_en" if locale == "en" else "label_de"
    prompt_key = "prompt_en" if locale == "en" else "prompt_de"
    meta = TRANSCRIPT_LANGUAGES.get(target) or TRANSCRIPT_LANGUAGES[DEFAULT_TRANSCRIPT_TARGET]
    language = meta["name"]
    return {
        "actions": [
            {
                "key": a["key"],
                "label": a[label_key],
                "icon": a["icon"],
                "prompt": a[prompt_key].replace("{language}", language),
                "min_words": a["min_words"],
            }
            for a in AIA_POPUP_ACTIONS
        ]
    }
