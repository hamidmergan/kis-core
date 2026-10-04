"""Facade so Celery finds the campus tasks under the usual module path."""
from src.features.campus.tasks import *  # noqa: F401,F403
