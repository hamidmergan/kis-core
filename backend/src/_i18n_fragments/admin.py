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
    "admin.settings.homeNoticeTooLong": {
        "de": "Hinweistext ist zu lang (max {max} Zeichen)",
        "en": "Notice text is too long (max {max} characters)",
    },
    "admin.settings.diagnosisPromptTooLong": {
        "de": "Diagnose-Prompt ist zu lang (max {max} Zeichen)",
        "en": "Diagnosis prompt is too long (max {max} characters)",
    },
    "admin.settings.diagnosisPlanInvalid": {
        "de": "Fragen-Plan ist ungültig. Jede Zeile braucht eine Stufe und einen Fragetyp.",
        "en": "Question plan is invalid. Each row needs a level and a question type.",
    },
    "admin.settings.answerMaxCharsOutOfRange": {
        "de": "Antwortlänge muss zwischen {min} und {max} Zeichen liegen",
        "en": "Answer length must be between {min} and {max} characters",
    },
    "admin.settings.diagnosisExamplesInvalid": {
        "de": "Beispiele sind ungültig. Erlaubt sind nur die Stufen A1, A2, B1, B2 mit Text.",
        "en": "Examples are invalid. Only the levels A1, A2, B1, B2 with text are allowed.",
    },
    "admin.settings.unknownModelKeys": {
        "de": "Unbekannte Model-Keys: {unknown}",
        "en": "Unknown model keys: {unknown}",
    },
    "admin.settings.modelNameEmpty": {
        "de": "Modellname für {key} darf nicht leer sein",
        "en": "Model name for {key} must not be empty",
    },
    "admin.settings.deepl.keyTooLong": {
        "de": "DeepL-API-Key ist zu lang (max. 200 Zeichen).",
        "en": "DeepL API key is too long (max. 200 characters).",
    },
    # DeepL multi-key admin
    "admin.settings.deepl.invalidKeyId": {
        "de": "Ungültige DeepL-Key-ID.",
        "en": "Invalid DeepL key id.",
    },
    "admin.settings.deepl.keyNotFound": {
        "de": "DeepL-Key nicht gefunden.",
        "en": "DeepL key not found.",
    },
    "admin.settings.deepl.nameRequired": {
        "de": "Name darf nicht leer sein.",
        "en": "Name must not be empty.",
    },
    "admin.settings.deepl.nameTooLong": {
        "de": "Name darf höchstens 60 Zeichen lang sein.",
        "en": "Name must not exceed 60 characters.",
    },
    "admin.settings.deepl.nameTaken": {
        "de": "Ein DeepL-Key mit diesem Namen existiert bereits.",
        "en": "A DeepL key with this name already exists.",
    },
    "admin.settings.deepl.keyRequired": {
        "de": "API-Key darf nicht leer sein.",
        "en": "API key must not be empty.",
    },
    "admin.settings.deepl.keyTooLong": {
        "de": "API-Key ist zu lang (max. 200 Zeichen).",
        "en": "API key is too long (max. 200 characters).",
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
    # LDAP user creation
    "admin.ldap.userExists": {
        "de": "Benutzer existiert bereits",
        "en": "User already exists",
    },
    "admin.ldap.invalidUid": {
        "de": "Ungültiger Benutzername (a-z, 0-9, _ . -, 2-32 Zeichen)",
        "en": "Invalid username (a-z, 0-9, _ . -, 2-32 characters)",
    },
    "admin.ldap.invalidEmail": {
        "de": "Ungültige E-Mail-Adresse",
        "en": "Invalid email address",
    },
    "admin.ldap.invalidEmployeeType": {
        "de": "Rolle muss 'staff' oder 'user' sein",
        "en": "Role must be 'staff' or 'user'",
    },
    "admin.ldap.nameRequired": {
        "de": "Vor- und Nachname sind Pflicht",
        "en": "First and last name are required",
    },
    "admin.ldap.addFailed": {
        "de": "LDAP-Eintrag fehlgeschlagen",
        "en": "LDAP add failed",
    },
    "admin.ldap.featureDisabled": {
        "de": "LDAP-Benutzererstellung ist deaktiviert",
        "en": "LDAP user creation is disabled",
    },
    "admin.ldap.invalidCustomRole": {
        "de": "Custom Role nicht gefunden",
        "en": "Custom role not found",
    },
    "admin.ldap.dbWriteFailed": {
        "de": "LDAP-Eintrag erstellt, aber DB-Anlage fehlgeschlagen. Rolle bitte nach erstem Login manuell zuweisen.",
        "en": "LDAP entry created but DB record failed. Assign the role manually after the user's first login.",
    },
}
