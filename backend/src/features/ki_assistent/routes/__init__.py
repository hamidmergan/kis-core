"""Aggregates all KI-Assistent sub-routers into one umbrella router."""

from fastapi import APIRouter

from src.features.ki_assistent.routes import (
    popup,
    modules,
    sources,
    chat,
    messages,
    notes,
    glossary,
)
from src.features.ki_assistent.routes.studio import (
    mindmap,
    lernkarten,
    datentabelle,
)
from src.features.ki_assistent.routes.sprachtraining import (
    exercises,
    stats,
)

router = APIRouter(tags=["ki-assistent"])

for m in [
    popup, modules, sources, chat, messages, notes, glossary,
    mindmap, lernkarten, datentabelle, exercises, stats,
]:
    router.include_router(m.router)
