"""Queries for the statistics area, across both products."""
from .assistant import assistant_overview
from .detail import user_detail, workspace_detail
from .eigene import may_see_workspace, own_workspaces
from .models import model_usage
from .tools import tool_overview
from .users import user_overview

__all__ = [
    "assistant_overview",
    "may_see_workspace",
    "model_usage",
    "own_workspaces",
    "tool_overview",
    "user_detail",
    "user_overview",
    "workspace_detail",
]
