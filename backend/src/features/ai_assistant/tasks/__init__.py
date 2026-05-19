"""Import all KI-Assistent task workspaces so Celery registers tasks,
and re-export task functions for backwards-compat imports."""

from src.features.ai_assistant.tasks.ingestion import (  # noqa: F401
    run_index_source,
    run_generate_summaries,
    run_generate_doc_summary,
    run_translate_transcript_en,
)
from src.features.ai_assistant.tasks.glossary import run_generate_glossary  # noqa: F401
from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set  # noqa: F401
from src.features.ai_assistant.tasks.maintenance import (  # noqa: F401
    run_reindex_all_sources,
    run_reindex_workspace,
    run_backfill_doc_summaries,
    run_backfill_page_summaries,
)
from src.features.ai_assistant.tasks.studio.mindmap import run_generate_mindmap  # noqa: F401
from src.features.ai_assistant.tasks.studio.data_table import run_generate_data_table  # noqa: F401
from src.features.ai_assistant.tasks.studio.schedule import run_generate_schedule  # noqa: F401
