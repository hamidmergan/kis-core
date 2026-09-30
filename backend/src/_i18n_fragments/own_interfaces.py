"""Text fragments for a person's own interfaces to outside voice services."""

MESSAGES: dict[str, dict[str, str]] = {
    "interfaces.ownProviderName": {
        "de": "{vendor} (eigener Zugang)",
        "en": "{vendor} (own account)",
    },
    "interfaces.consentRequired": {
        "de": "Bitte bestätige zuerst den Hinweis zu eigenen Schnittstellen.",
        "en": "Please confirm the notice on own interfaces first.",
    },
    "interfaces.notFound": {
        "de": "Diese Schnittstelle gibt es nicht.",
        "en": "This interface does not exist.",
    },
    "interfaces.unknownVendor": {
        "de": "Diesen Anbieter gibt es hier nicht.",
        "en": "This provider is not available here.",
    },
    "interfaces.noVoices": {
        "de": "{vendor} hat für diesen Zugang keine Stimmen geliefert.",
        "en": "{vendor} returned no voices for this account.",
    },
    "interfaces.error.keyInvalid": {
        "de": "{vendor} hat den Schlüssel abgelehnt. Bitte prüfe ihn in deinem Konto bei {vendor}.",
        "en": "{vendor} rejected the key. Please check it in your {vendor} account.",
    },
    "interfaces.error.quota": {
        "de": "Dein Guthaben bei {vendor} ist aufgebraucht. Lade es dort auf oder warte, bis es sich erneuert.",
        "en": "Your {vendor} balance is used up. Top it up there or wait until it renews.",
    },
    "interfaces.error.unreachable": {
        "de": "{vendor} antwortet gerade nicht. Bitte versuche es gleich noch einmal.",
        "en": "{vendor} is not responding right now. Please try again shortly.",
    },
    "interfaces.error.billingRequired": {
        "de": "{vendor} gibt die kostenlose Nutzung hier nicht frei. Dafür verlangt {vendor} ein hinterlegtes Zahlungskonto.",
        "en": "{vendor} does not allow free use here. {vendor} requires a payment account for it.",
    },
    "interfaces.encryptionMissing": {
        "de": "Eigene Schlüssel lassen sich gerade nicht sicher speichern. Bitte wende dich an die Administration.",
        "en": "Own keys cannot be stored securely right now. Please contact the administrators.",
    },
    "interfaces.error.rejected": {
        "de": "{vendor} hat die Anfrage abgelehnt.",
        "en": "{vendor} rejected the request.",
    },
}
