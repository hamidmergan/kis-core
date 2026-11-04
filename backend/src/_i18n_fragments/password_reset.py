"""Text fragments for the password reset links."""

MESSAGES: dict[str, dict[str, str]] = {
    "passwordReset.notAllowed": {
        "de": "Für dieses Konto gibt es keinen Reset-Link",
        "en": "This account cannot get a reset link",
    },
    "passwordReset.userNotFound": {
        "de": "Konto nicht gefunden",
        "en": "Account not found",
    },
    "passwordReset.notFound": {
        "de": "Diesen Link gibt es nicht",
        "en": "This link does not exist",
    },
    "passwordReset.notValid": {
        "de": "Dieser Link wurde bereits benutzt oder ist abgelaufen",
        "en": "This link has already been used or has expired",
    },
    "passwordReset.tooShort": {
        "de": "Das Passwort muss mindestens {min} Zeichen haben",
        "en": "The password needs at least {min} characters",
    },
    "passwordReset.tooLong": {
        "de": "Das Passwort ist zu lang",
        "en": "The password is too long",
    },
    "passwordReset.failed": {
        "de": "Das Passwort konnte nicht geändert werden",
        "en": "The password could not be changed",
    },
}
