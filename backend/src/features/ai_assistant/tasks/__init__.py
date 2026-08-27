"""Loads all task modules so Celery knows them."""

from src.features.ai_assistant.tasks.ingestion import (  # noqa: F401
    run_index_source,
    run_translate_transcript,
)
from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set  # noqa: F401
from src.features.ai_assistant.tasks.maintenance import run_reindex_all_sources  # noqa: F401
from src.features.ai_assistant.tasks.studio.mindmap import run_generate_mindmap  # noqa: F401
from src.features.ai_assistant.tasks.studio.data_table import run_generate_data_table  # noqa: F401
from src.features.ai_assistant.tasks.studio.schedule import run_generate_schedule  # noqa: F401
