"""Text fragments for logging in as somebody else."""

MESSAGES: dict[str, dict[str, str]] = {
    "impersonation.userNotFound": {
        "de": "Dieses Konto gibt es nicht",
        "en": "This account does not exist",
    },
    "impersonation.self": {
        "de": "Du bist bereits in deinem eigenen Konto",
        "en": "You are already in your own account",
    },
    "impersonation.nested": {
        "de": "Du bist schon in einem fremden Konto unterwegs",
        "en": "You are already inside somebody else's account",
    },
    "impersonation.targetIsAdmin": {
        "de": "In ein Konto mit Verwaltungsrechten kann man sich nicht einloggen",
        "en": "You cannot log in to an account with administration rights",
    },
    "impersonation.targetInactive": {
        "de": "Dieses Konto ist gesperrt",
        "en": "This account is blocked",
    },
    "impersonation.targetExpired": {
        "de": "Der Zugang dieses Kontos ist abgelaufen",
        "en": "The access of this account has expired",
    },
    "impersonation.notActive": {
        "de": "Du bist in keinem fremden Konto",
        "en": "You are not inside somebody else's account",
    },
    "impersonation.ownSessionGone": {
        "de": "Deine eigene Sitzung ist abgelaufen, bitte neu anmelden",
        "en": "Your own session has expired, please log in again",
    },
}
