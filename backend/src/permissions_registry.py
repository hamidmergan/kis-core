# backend/src/permissions_registry.py
"""Der Katalog aller Berechtigungen: die Zeilen der Rechtetabelle.

Eine Stelle, an der steht, was es an Rechten gibt. Die Oberflaeche baut daraus
ihre Tabelle, die Torwaechter pruefen dagegen, und eine eigene Rolle speichert
nur Schluessel aus diesem Katalog.

Vorher waren es vier feste Schalter in ``permissions.py``, von denen einer
(Adminbereich) fuer eigene Rollen hart auf False stand. Ein Sprachexperte, der
nur die Prompts des KI-Assistenten pflegen soll, war damit nicht abbildbar.

Die Texte stehen NICHT hier, sondern in ``frontend/messages/{de,en}.json`` unter
``admin.permissions.<schluessel>``. Ein Schluessel ohne Text faellt im
Frontend-Test auf.
"""

from src.tools_registry import ALL_TOOL_KEYS

# === Gruppen =================================================================
# Die Reihenfolge ist die Reihenfolge in der Tabelle.
GROUP_AIA = "aia"
GROUP_TOOLS = "tools"
GROUP_SETTINGS = "settings"

GROUPS: tuple[str, ...] = (GROUP_AIA, GROUP_TOOLS, GROUP_SETTINGS)

# === KI-Assistent ============================================================
PERM_AIA_USE = "aia.use"
PERM_AIA_WORKSPACE_CREATE = "aia.workspace.create"

AIA_KEYS: tuple[str, ...] = (PERM_AIA_USE, PERM_AIA_WORKSPACE_CREATE)

# === Globale Werkzeuge =======================================================
# Abgeleitet aus der Werkzeugliste, damit ein neues Werkzeug nicht an zwei
# Stellen eingetragen werden muss.
TOOL_PERM_PREFIX = "tools."
TOOL_KEYS: tuple[str, ...] = tuple(f"{TOOL_PERM_PREFIX}{k}" for k in ALL_TOOL_KEYS)


def tool_key_of(permission: str) -> str:
    """``tools.translation`` -> ``translation``."""
    return permission[len(TOOL_PERM_PREFIX):]


# === Einstellungen ===========================================================
# Ein Schluessel je Seite des Bereichs. Sprachniveau und Anbieter haben je zwei
# Reiter, bleiben aber ein Schluessel: ihre Werte liegen im selben Datensatz,
# eine Trennung waere in der Speicher-Route nicht durchzuhalten und wuerde ein
# Recht vortaeuschen, das der Torwaechter nicht halten kann.
SETTINGS_PREFIX = "settings."

PERM_SET_TOOLS_RELEASE = "settings.werkzeuge.release"
PERM_SET_TOOLS_JOBS = "settings.werkzeuge.jobs"
PERM_SET_TOOLS_STATS = "settings.werkzeuge.stats"
PERM_SET_AIA_SOURCES = "settings.assistent.sources"
PERM_SET_AIA_LEVEL = "settings.assistent.level"
PERM_SET_AIA_USAGE = "settings.assistent.usage"
PERM_SET_PROVIDERS = "settings.anbieter"
PERM_SET_USERS_PENDING = "settings.nutzer.pending"
PERM_SET_USERS_WHITELIST = "settings.nutzer.whitelist"
PERM_SET_USERS_ALL = "settings.nutzer.users"
PERM_SET_USERS_ROLES = "settings.nutzer.roles"
# Kein eigener Schluessel mehr fuer die Oberflaeche. Beschriftung und Hinweis
# stehen jetzt auf der System-Seite und haengen an PERM_SET_SYSTEM.
PERM_SET_SYSTEM = "settings.system"
PERM_SET_MASCOT = "settings.mascot"

SETTINGS_KEYS: tuple[str, ...] = (
    PERM_SET_TOOLS_RELEASE,
    PERM_SET_TOOLS_JOBS,
    PERM_SET_TOOLS_STATS,
    PERM_SET_AIA_SOURCES,
    PERM_SET_AIA_LEVEL,
    PERM_SET_AIA_USAGE,
    PERM_SET_PROVIDERS,
    PERM_SET_USERS_PENDING,
    PERM_SET_USERS_WHITELIST,
    PERM_SET_USERS_ALL,
    PERM_SET_USERS_ROLES,
    PERM_SET_SYSTEM,
    PERM_SET_MASCOT,
)

# === Der ganze Katalog =======================================================
ALL_PERMISSION_KEYS: tuple[str, ...] = AIA_KEYS + TOOL_KEYS + SETTINGS_KEYS

PERMISSION_GROUPS: dict[str, tuple[str, ...]] = {
    GROUP_AIA: AIA_KEYS,
    GROUP_TOOLS: TOOL_KEYS,
    GROUP_SETTINGS: SETTINGS_KEYS,
}


def is_settings_key(permission: str) -> bool:
    return permission.startswith(SETTINGS_PREFIX)


def valid_keys(keys) -> tuple[str, ...]:
    """Unbekanntes rauswerfen, Reihenfolge des Katalogs herstellen, Doppelte weg.

    Eine geloeschte Berechtigung darf eine Rolle nicht kaputtmachen, deshalb
    filtern statt werfen. Die feste Reihenfolge macht gespeicherte Listen
    vergleichbar.
    """
    wanted = set(keys)
    return tuple(k for k in ALL_PERMISSION_KEYS if k in wanted)


# === Systemrollen ============================================================
# Fest im Code, nicht in der Datenbank. Die Tabelle zeigt sie ausgegraut, damit
# man vergleichen kann, was eine eigene Rolle daneben darf.
#
# Die drei Zeilen bilden exakt ab, was ``permissions_for_system_role`` vorher
# als vier Schalter ausgedrueckt hat. Wer hier etwas aendert, aendert das
# Verhalten aller bestehenden Konten.
SYSTEM_ROLES: tuple[str, ...] = ("admin", "staff", "user")

SYSTEM_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "admin": ALL_PERMISSION_KEYS,
    "staff": AIA_KEYS + TOOL_KEYS,
    "user": (PERM_AIA_USE,),
}

# === Besitzer der Einstellungs-Felder ========================================
# ``PATCH /api/admin/settings`` bedient mit einem Datensatz mehrere Seiten. Ohne
# diese Zuordnung koennte jemand mit dem Recht fuer eine Seite jedes Feld jeder
# anderen Seite mitschicken. Beim Speichern wird jedes gesetzte Feld einzeln
# gegen diese Tabelle geprueft.
#
# Ein Feld, das hier fehlt, ist absichtlich nicht speicherbar: die Pruefung
# behandelt Unbekanntes wie "nur Administrator".
SETTING_FIELD_PERMISSIONS: dict[str, str] = {
    "whitelist_enabled": PERM_SET_USERS_WHITELIST,
    "workspace_label_singular_de": PERM_SET_SYSTEM,
    "workspace_label_plural_de": PERM_SET_SYSTEM,
    "workspace_label_singular_en": PERM_SET_SYSTEM,
    "workspace_label_plural_en": PERM_SET_SYSTEM,
    "home_notice_enabled": PERM_SET_SYSTEM,
    "home_notice_text": PERM_SET_SYSTEM,
    "language_training_enabled": PERM_SET_AIA_LEVEL,
    "ocr_enabled": PERM_SET_AIA_SOURCES,
    "aia_workspace_max_sources": PERM_SET_AIA_SOURCES,
    "aia_context_max_chars": PERM_SET_AIA_SOURCES,
    "aia_specific_max_chars": PERM_SET_AIA_SOURCES,
    "aia_tool_context_max_chars": PERM_SET_AIA_SOURCES,
    "aia_summary_batch_max_chars": PERM_SET_AIA_SOURCES,
    "aia_source_max_pages": PERM_SET_AIA_SOURCES,
    "aia_flashcard_voice_provider_id": PERM_SET_PROVIDERS,
    "aia_flashcard_voice_id": PERM_SET_PROVIDERS,
    "tts_max_chars_per_request": PERM_SET_PROVIDERS,
    "language_diagnosis_prompt": PERM_SET_AIA_LEVEL,
    "language_diagnosis_question_plan_de": PERM_SET_AIA_LEVEL,
    "language_diagnosis_answer_max_chars": PERM_SET_AIA_LEVEL,
    "language_diagnosis_adaptive_behavior": PERM_SET_AIA_LEVEL,
    "language_diagnosis_grading_rules": PERM_SET_AIA_LEVEL,
    "language_diagnosis_level_examples": PERM_SET_AIA_LEVEL,
    "language_diagnosis_level_descriptions": PERM_SET_AIA_LEVEL,
}


# === Migration alter Rollen ==================================================
def keys_from_legacy(aia_access: str | None, allowed_tools) -> tuple[str, ...]:
    """Die beiden alten Spalten in Schluessel uebersetzen.

    ``aia_access`` war dreiwertig, aber Lesen ueber einen geteilten Link war
    schon vorher fuer alle da. Nur ``edit`` hat wirklich etwas zusaetzlich
    erlaubt, naemlich eigene Workspaces.
    """
    keys = [PERM_AIA_USE]
    if aia_access == "edit":
        keys.append(PERM_AIA_WORKSPACE_CREATE)
    for tool in allowed_tools or []:
        key = f"{TOOL_PERM_PREFIX}{tool}"
        if key in TOOL_KEYS:
            keys.append(key)
    return valid_keys(keys)
