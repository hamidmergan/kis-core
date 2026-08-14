# backend/src/permissions.py
"""Permission model for RBAC.

Eine Person hat eine Menge von Rechte-Schluesseln aus
``src.permissions_registry``. Systemrollen (admin/staff/user) bringen ihre Menge
als Konstante mit, eigene Rollen holen sie aus der Tabelle ``custom_roles``.

Die vier Felder, die es hier frueher gab, sind zu abgeleiteten Eigenschaften
geworden. So laufen ``auth.py``, die Werkzeugleiste und die Startseite
unveraendert weiter, waehrend die Torwaechter auf Schluessel umsteigen.
"""
from dataclasses import dataclass, field

from src.dependencies import get_settings
from src.permissions_registry import (
    PERM_AIA_USE,
    PERM_AIA_WORKSPACE_CREATE,
    PERM_SET_USERS_ALL,
    SYSTEM_ROLE_PERMISSIONS,
    SYSTEM_ROLES,
    TOOL_KEYS,
    is_settings_key,
    tool_key_of,
    valid_keys,
)

__all__ = [
    "SYSTEM_ROLES",
    "Permissions",
    "permissions_for_system_role",
    "resolve_user_permissions",
    "custom_role_permissions",
]


@dataclass(frozen=True)
class Permissions:
    """Was jemand darf, als Menge von Schluesseln.

    ``allow_ldap_user_create`` steht daneben statt im Katalog, weil es kein
    Recht ist, das man vergeben kann: es haengt zusaetzlich an einem
    Serverschalter, der beim Start gelesen wird.
    """

    keys: frozenset[str] = field(default_factory=frozenset)
    allow_ldap_user_create: bool = False

    def has(self, *keys: str) -> bool:
        """Wahr, sobald einer der genannten Schluessel da ist."""
        return any(k in self.keys for k in keys)

    # --- abgeleitete Sicht fuer alles, was noch die alten Namen nutzt --------
    @property
    def allow_admin_panel(self) -> bool:
        """Darf ueberhaupt eine Seite des Bereichs sehen.

        Frueher hiess das "ist Administrator". Jetzt reicht ein einziges
        Einstellungsrecht, denn genau darum ging der Umbau.
        """
        return any(is_settings_key(k) for k in self.keys)

    @property
    def allow_aia(self) -> bool:
        return PERM_AIA_USE in self.keys

    @property
    def allow_workspace_create(self) -> bool:
        return PERM_AIA_WORKSPACE_CREATE in self.keys

    @property
    def tools(self) -> tuple[str, ...]:
        """Werkzeug-Schluessel ohne Praefix, in der Reihenfolge des Katalogs."""
        return tuple(tool_key_of(k) for k in TOOL_KEYS if k in self.keys)

    @property
    def settings_pages(self) -> tuple[str, ...]:
        return tuple(k for k in sorted(self.keys) if is_settings_key(k))


def permissions_for_system_role(role: str) -> Permissions:
    preset = SYSTEM_ROLE_PERMISSIONS.get(role)
    if preset is None:
        raise ValueError(f"Unknown system role: {role!r}")
    return Permissions(keys=frozenset(preset))


def custom_role_permissions(keys) -> Permissions:
    """Permissions for a DB-backed custom role.

    Unbekannte Schluessel fallen weg, damit eine geloeschte Berechtigung eine
    Rolle nicht mit einem Fehler statt mit weniger Rechten beantwortet.
    """
    return Permissions(keys=frozenset(valid_keys(keys)))


def resolve_user_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    """Compute effective permissions, layering the LDAP feature flag on top.

    Note: `get_settings()` is `lru_cache`d, so `ldap_user_creation_enabled`
    is read once per process and frozen. Toggling the env var requires a
    backend restart — matches the deploy-time-only flag strategy in the spec.
    """
    base = _resolve_base_permissions(role, custom_role_id, is_env_admin)
    if PERM_SET_USERS_ALL in base.keys and get_settings().ldap_user_creation_enabled:
        return Permissions(keys=base.keys, allow_ldap_user_create=True)
    return base


def _resolve_base_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    """Compute base permissions before the LDAP env-flag layer.

    env-admin always wins (bootstrap super-admin). Otherwise: system role
    constants, or DB-backed custom role.
    """
    if is_env_admin:
        return permissions_for_system_role("admin")
    if role in SYSTEM_ROLES:
        return permissions_for_system_role(role)
    if role == "custom" and custom_role_id is not None:
        # Lazy import to avoid pulling psycopg2 at module import time.
        from src import database
        cr = database.get_custom_role(custom_role_id)
        if cr is None:
            # Custom role was deleted concurrently; degrade gracefully to 'user'.
            return permissions_for_system_role("user")
        return custom_role_permissions(cr["permissions"])
    # Unknown / corrupt role -> safest fallback
    return permissions_for_system_role("user")
