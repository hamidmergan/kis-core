"""Text fragments for the invitations."""

MESSAGES: dict[str, dict[str, str]] = {
    "invite.featureDisabled": {
        "de": "Einladungen sind abgeschaltet",
        "en": "Invitations are disabled",
    },
    "invite.noUsableUid": {
        "de": "Aus dieser Eingabe laesst sich kein Benutzername bilden",
        "en": "No usable username can be derived from this input",
    },
    "invite.userExists": {
        "de": "Diesen Benutzernamen gibt es schon",
        "en": "This username already exists",
    },
    "invite.alreadyInvited": {
        "de": "Zu diesem Benutzernamen ist schon eine Einladung offen",
        "en": "An invitation for this username is already open",
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
