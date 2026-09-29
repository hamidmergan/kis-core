"""Turns a short image idea into a detailed English prompt, with the language model of the chat route."""

from __future__ import annotations

from src.services import feature_router
from src.services.feature_provider_choices import binding_for
from src.services.llm_call import create_logged

_ANWEISUNG = (
    "You write prompts for an image generation model. Rewrite the user's idea as one detailed English prompt: "
    "subject, setting, composition, lighting and colors, 40 to 90 words. Do not name an art style, the user picks "
    "it separately. Never ask for text, letters or words in the picture. Answer with the prompt only."
)


def ausformulieren(text: str) -> str:
    """The detailed prompt, stripped of quotes the model likes to add."""
    llm = feature_router.make_llm_client(binding_for("chat", None))
    extra = {"extra_body": llm._extra_body} if llm._extra_body else {}
    antwort = create_logged(
        llm._client, model=llm._model, endpoint="tool", temperature=0.6, max_tokens=400,
        messages=[{"role": "system", "content": _ANWEISUNG}, {"role": "user", "content": text.strip()}], **extra,
    )
    return (antwort.choices[0].message.content or "").strip().strip('"').strip()
