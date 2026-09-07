"""Queries for the statistics area, across both products."""
from .assistant import assistant_overview
from .detail import user_detail, user_verlauf, workspace_detail
from .models import model_usage
from .tools import tool_overview
from .users import user_overview, users_by_day, users_by_hour, users_new_in_month

__all__ = [
    "assistant_overview",
    "model_usage",
    "tool_overview",
    "user_detail",
    "user_overview",
    "user_verlauf",
    "users_by_day",
    "users_by_hour",
    "users_new_in_month",
    "workspace_detail",
]
