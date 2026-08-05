"""Aggregates all KI-Assistent sub-routers into one umbrella router."""

from fastapi import APIRouter, Depends

from src.dependencies_rbac import require_aia_access
from src.features.ai_assistant.routes import (
    popup,
    workspaces,
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
    grammar_topics,
    stats,
    diagnosis,
)

router = APIRouter(dependencies=[Depends(require_aia_access)])

for m in [
    popup, workspaces, sources, chat, messages, notes, glossary,
    mindmap, flashcards, data_table, schedule, exercises, grammar_topics,
    stats, diagnosis,
]:
    router.include_router(m.router)
