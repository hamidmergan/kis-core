"""Textbausteine fuer die Einladungen."""

MESSAGES: dict[str, dict[str, str]] = {
    "invite.featureDisabled": {
        "de": "Einladungen sind abgeschaltet",
        "en": "Invitations are disabled",
    },
    "invite.invalidEmail": {
        "de": "Keine gueltige E-Mail-Adresse",
        "en": "Not a valid email address",
    },
    "invite.noUsableUid": {
        "de": "Aus dieser Adresse laesst sich kein Benutzername bilden",
        "en": "No usable username can be derived from this address",
    },
    "invite.userExists": {
        "de": "Zu dieser Adresse gibt es schon ein Konto",
        "en": "An account for this address already exists",
    },
    "invite.alreadyInvited": {
        "de": "Zu dieser Adresse ist schon eine Einladung offen",
        "en": "An invitation to this address is already open",
    },
    "invite.invalidCustomRole": {
        "de": "Rolle nicht gefunden",
        "en": "Role not found",
    },
    "invite.notFound": {
        "de": "Diesen Einladungslink gibt es nicht",
        "en": "This invitation link does not exist",
    },
    "invite.notValid": {
        "de": "Dieser Link wurde bereits benutzt oder ist abgelaufen",
        "en": "This link has already been used or has expired",
    },
    "invite.passwordTooShort": {
        "de": "Das Passwort braucht mindestens {min} Zeichen",
        "en": "The password needs at least {min} characters",
    },
    "invite.createFailed": {
        "de": "Konto konnte nicht angelegt werden",
        "en": "The account could not be created",
    },
}
