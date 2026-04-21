"""Import all KI-Assistent task modules so Celery registers tasks,
and re-export task functions for backwards-compat imports."""

from src.features.ki_assistent.tasks.ingestion import (  # noqa: F401
    run_index_source,
    run_generate_summaries,
    run_translate_transcript_en,
)
from src.features.ki_assistent.tasks.glossary import run_generate_glossary  # noqa: F401
from src.features.ki_assistent.tasks.sprachtraining import run_generate_exercise_set  # noqa: F401
from src.features.ki_assistent.tasks.maintenance import run_reindex_all_sources  # noqa: F401
from src.features.ki_assistent.tasks.studio.mindmap import run_generate_mindmap  # noqa: F401
from src.features.ki_assistent.tasks.studio.datentabelle import run_generate_datentabelle  # noqa: F401
from src.features.ki_assistent.tasks.studio.zeitplan import run_generate_zeitplan  # noqa: F401
