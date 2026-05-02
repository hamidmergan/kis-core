"""i18n message fragments for admin routes."""

MESSAGES: dict[str, dict[str, str]] = {
    # Tool visibility
    "admin.tools.unknownKey": {
        "de": "Unbekanntes Tool",
        "en": "Unknown tool",
    },
    # Settings
    "admin.settings.unknownPingService": {
        "de": "Unbekannter Service: {service}",
        "en": "Unknown service: {service}",
    },
    "admin.settings.lastProviderRequired": {
        "de": "Mindestens ein {group}-Anbieter muss aktiv bleiben. Aktiviere zuerst einen anderen.",
        "en": "At least one {group} provider must remain active. Enable another one first.",
    },
    "admin.settings.labelEmpty": {
        "de": "{label} darf nicht leer sein",
        "en": "{label} must not be empty",
    },
    "admin.settings.labelTooLong": {
        "de": "{label} ist zu lang (max 40 Zeichen)",
        "en": "{label} is too long (max 40 characters)",
    },
    "admin.settings.unknownModelKeys": {
        "de": "Unbekannte Model-Keys: {unknown}",
        "en": "Unknown model keys: {unknown}",
    },
    "admin.settings.modelNameEmpty": {
        "de": "Modellname für {key} darf nicht leer sein",
        "en": "Model name for {key} must not be empty",
    },
    # Quota
    "admin.quota.unknownType": {
        "de": "Unbekannter Quota-Typ: {quota_type}",
        "en": "Unknown quota type: {quota_type}",
    },
    # Maintenance
    "admin.maintenance.reindexAlreadyRunning": {
        "de": "Reindex läuft bereits",
        "en": "Reindex already running",
    },
    # Prompts
    "admin.prompt.notFound": {
        "de": "Prompt nicht gefunden",
        "en": "Prompt not found",
    },
    "admin.prompt.readOnly": {
        "de": "Dieser Prompt ist schreibgeschützt",
        "en": "This prompt is read-only",
    },
    "admin.prompt.notAllowed": {
        "de": "Nicht erlaubt",
        "en": "Not allowed",
    },
    # Users
    "admin.user.notFound": {
        "de": "User nicht gefunden",
        "en": "User not found",
    },
    "admin.user.noEmail": {
        "de": "User hat keine Email-Adresse",
        "en": "User has no email address",
    },
    # Whitelist
    "admin.whitelist.invalidEmail": {
        "de": "Ungültige Email-Adresse",
        "en": "Invalid email address",
    },
    "admin.whitelist.adminProtected": {
        "de": "Die Admin-Email kann nicht aus der Whitelist entfernt werden.",
        "en": "The admin email cannot be removed from the whitelist.",
    },
}
