"""Backwards-compat facade. Real code lives in src.core.* and src.features.*/repository."""

from src.core.db.pool import get_connection  # noqa: F401
from src.core.db.schema import init_db  # noqa: F401
from src.core.db._common import _notify_job_update, _de_date_to_utc  # noqa: F401
from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS  # noqa: F401

from src.features.admin.repository.users import *  # noqa: F401,F403
from src.features.admin.repository.settings import *  # noqa: F401,F403
from src.features.jobs.repository import *  # noqa: F401,F403
from src.features.quotas.repository import *  # noqa: F401,F403
from src.features.ki_assistent.repository.modules import *  # noqa: F401,F403
from src.features.ki_assistent.repository.access_links import *  # noqa: F401,F403
from src.features.ki_assistent.repository.enrollments import *  # noqa: F401,F403
from src.features.ki_assistent.repository.sources import *  # noqa: F401,F403
from src.features.ki_assistent.repository.chunks import *  # noqa: F401,F403
from src.features.ki_assistent.repository.chat import *  # noqa: F401,F403
from src.features.ki_assistent.repository.notes import *  # noqa: F401,F403
from src.features.ki_assistent.repository.summaries import *  # noqa: F401,F403
from src.features.ki_assistent.repository.mindmaps import *  # noqa: F401,F403
from src.features.ki_assistent.repository.datentabellen import *  # noqa: F401,F403
from src.features.ki_assistent.repository.glossary import *  # noqa: F401,F403
from src.features.ki_assistent.repository.exercises import *  # noqa: F401,F403
from src.features.ki_assistent.repository.stats import *  # noqa: F401,F403
