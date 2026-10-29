"""Der Campus-Assistent ist als Werkzeug mit eigenem Verwaltungsrecht registriert."""
from src import limits
from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    KEY_MODULE,
    MATRIX_LAYOUT,
    PERM_SET_CAMPUS,
    SETTINGS_KEYS,
    SYSTEM_ROLE_PERMISSIONS,
    TOOL_KEYS,
)
from src.routes.admin._registries import TOOLS_CONFIG
from src.tools_registry import ALL_TOOL_KEYS


def test_campus_ist_ein_werkzeug():
    assert "campus" in ALL_TOOL_KEYS
    assert "tools.campus" in TOOL_KEYS
    assert any(t["key"] == "campus" for t in TOOLS_CONFIG)


def test_only_staff_may_use_the_info_assistant():
    assert "tools.campus" not in SYSTEM_ROLE_PERMISSIONS["user"]
    assert "tools.campus" in SYSTEM_ROLE_PERMISSIONS["staff"]


def test_verwaltungsrecht_haengt_im_katalog():
    assert PERM_SET_CAMPUS == "settings.campus"
    assert PERM_SET_CAMPUS in SETTINGS_KEYS
    assert PERM_SET_CAMPUS in ALL_PERMISSION_KEYS
    assert any(PERM_SET_CAMPUS in keys for _, _, keys in MATRIX_LAYOUT)
    assert KEY_MODULE[PERM_SET_CAMPUS] == "tools"


def test_grenzen_sind_gesetzt():
    assert limits.CAMPUS_QUESTION_MAX_CHARS == 2000
    assert limits.CAMPUS_MAX_QUESTIONS_PER_CHAT == 50
    assert limits.CAMPUS_MAX_CHATS_PER_USER == 100
    assert limits.CAMPUS_CHAT_RETENTION_DAYS == 90
    assert limits.CAMPUS_CONTEXT_MAX_CHARS == 40_000
