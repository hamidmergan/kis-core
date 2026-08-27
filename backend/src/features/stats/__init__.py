"""Abfragen fuer den Statistikbereich.

Bewusst ein eigener Ort und nicht bei den Auftraegen oder beim Assistenten: die
Zahlen des Adminbereichs schneiden quer durch beide Produkte, und keiner der
beiden ist ihr Zuhause.
"""
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
