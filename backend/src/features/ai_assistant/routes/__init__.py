"""Aggregates all KI-Assistent sub-routers into one umbrella router."""

from fastapi import APIRouter

from src.features.ai_assistant.routes import (
    popup,
    modules,
    sources,
    chat,
    messages,
    notes,
    glossary,
)
from src.features.ai_assistant.routes.studio import (
    mindmap,
    flashcards,
    data_table,
    schedule,
)
from src.features.ai_assistant.routes.language_training import (
    exercises,
    stats,
)

router = APIRouter()

for m in [
    popup, modules, sources, chat, messages, notes, glossary,
    mindmap, flashcards, data_table, schedule, exercises, stats,
]:
    router.include_router(m.router)
