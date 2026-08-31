"""Text fragments for the feedback box."""

MESSAGES: dict[str, dict[str, str]] = {
    "feedback.messageRequired": {
        "de": "Bitte einen Text eingeben",
        "en": "Please enter some text",
    },
    "feedback.messageTooLong": {
        "de": "Höchstens {max} Zeichen",
        "en": "At most {max} characters",
    },
    "feedback.categoryInvalid": {
        "de": "Unbekannte Kategorie",
        "en": "Unknown category",
    },
    "feedback.tooManyFiles": {
        "de": "Höchstens {max} Dateien",
        "en": "At most {max} files",
    },
    "feedback.fileTypeNotAllowed": {
        "de": "Erlaubt sind nur: {extensions}",
        "en": "Only allowed: {extensions}",
    },
    "feedback.notFound": {
        "de": "Diesen Eintrag gibt es nicht",
        "en": "This entry does not exist",
    },
}
