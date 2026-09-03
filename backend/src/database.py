"""Backwards-compat facade. Real code lives in src.core.* and src.features.*/repository."""

from src.core.db.pool import get_connection  # noqa: F401
from src.core.db.schema import init_db  # noqa: F401
from src.core.db._common import _notify_job_update, _de_date_to_utc  # noqa: F401
from src.limits import MAX_RESULT_FILES  # noqa: F401

from src.features.admin.repository.users import *  # noqa: F401,F403
from src.features.admin.repository.roles import *  # noqa: F401,F403
from src.features.admin.repository.settings import *  # noqa: F401,F403
from src.features.jobs.repository import *  # noqa: F401,F403
from src.features.quotas.repository import *  # noqa: F401,F403
from src.features.glossaries.repository import *  # noqa: F401,F403
from src.features.ai_assistant.repository.workspaces import *  # noqa: F401,F403
from src.features.ai_assistant.repository.access_links import *  # noqa: F401,F403
from src.features.ai_assistant.repository.enrollments import *  # noqa: F401,F403
from src.features.ai_assistant.repository.sources import *  # noqa: F401,F403
from src.features.ai_assistant.repository.source_rename import *  # noqa: F401,F403
from src.features.ai_assistant.repository.titles import *  # noqa: F401,F403
from src.features.ai_assistant.repository.chapters import *  # noqa: F401,F403
from src.features.ai_assistant.repository.chunks import *  # noqa: F401,F403
from src.features.ai_assistant.repository.chat import *  # noqa: F401,F403
from src.features.ai_assistant.repository.notes import *  # noqa: F401,F403
from src.features.ai_assistant.repository.mindmaps import *  # noqa: F401,F403
from src.features.ai_assistant.repository.data_tables import *  # noqa: F401,F403
from src.features.ai_assistant.repository.schedule import *  # noqa: F401,F403
from src.features.ai_assistant.repository.demo_tour_seed import *  # noqa: F401,F403
from src.features.ai_assistant.repository.glossary import *  # noqa: F401,F403
from src.features.ai_assistant.repository.exercises import *  # noqa: F401,F403
from src.features.ai_assistant.repository.context_cursors import *  # noqa: F401,F403
from src.features.ai_assistant.repository.exercise_pool import *  # noqa: F401,F403
from src.features.ai_assistant.repository.grammar_topics import *  # noqa: F401,F403
from src.features.ai_assistant.repository.stats import *  # noqa: F401,F403
from src.features.ai_assistant.repository.language_level import *  # noqa: F401,F403
from src.features.ai_providers.repository.providers import *  # noqa: F401,F403
from src.features.ai_providers.repository.feature_routes import *  # noqa: F401,F403
from src.features.ai_providers.repository.model_limits import *  # noqa: F401,F403
