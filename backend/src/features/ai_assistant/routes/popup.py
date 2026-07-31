"""KI-Assistent routes - popup actions."""


from fastapi import APIRouter, Depends, Query


from src.i18n import get_locale, TRANSCRIPT_LANGUAGES, DEFAULT_TRANSCRIPT_TARGET
from src.tool_prompts import (
    AIA_POPUP_ACTIONS,
)


router = APIRouter(tags=["ki-assistent: popup"])

@router.get("/ai-assistant/popup-actions")
async def get_popup_actions(
    locale: str = Depends(get_locale),
    target: str = Query(DEFAULT_TRANSCRIPT_TARGET),
):
    """Return the PDF-viewer popup actions in the user's UI locale.

    Both label and prompt match the locale; the prompts instruct the LLM to
    answer in the source-text language, so they're behaviourally equivalent
    across locales and only differ in tone.

    `target` is the reader's own translation target (a code from
    TRANSCRIPT_LANGUAGES), passed by the browser from the per-user setting.
    An unknown code falls back to English instead of erroring: the selection
    bar must never end up without actions because of a stale query string.
    Nothing here is privileged - the value only shapes the reader's own
    translation - so no auth or DB lookup is needed on this route.
    """
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
