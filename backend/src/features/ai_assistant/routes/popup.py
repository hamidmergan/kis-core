"""KI-Assistent routes - popup actions."""


from fastapi import APIRouter, Depends


from src.i18n import get_locale
from src.tool_prompts import (
    AIA_POPUP_ACTIONS,
)


router = APIRouter(tags=["ki-assistent: popup"])

@router.get("/ai-assistant/popup-actions")
async def get_popup_actions(locale: str = Depends(get_locale)):
    """Return the PDF-viewer popup actions in the user's UI locale.

    Both label and prompt match the locale; the prompts instruct the LLM to
    answer in the source-text language, so they're behaviourally equivalent
    across locales and only differ in tone.
    """
    label_key = "label_en" if locale == "en" else "label_de"
    prompt_key = "prompt_en" if locale == "en" else "prompt_de"
    return {
        "actions": [
            {
                "key": a["key"],
                "label": a[label_key],
                "icon": a["icon"],
                "prompt": a[prompt_key],
                "min_words": a["min_words"],
            }
            for a in AIA_POPUP_ACTIONS
        ]
    }

