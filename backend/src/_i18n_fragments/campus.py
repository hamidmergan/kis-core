"""Text fragments of the info assistant."""

MESSAGES: dict[str, dict[str, str]] = {
    "campus.chatNotFound": {
        "de": "Diesen Chat gibt es nicht",
        "en": "This chat does not exist",
    },
    "campus.messageNotFound": {
        "de": "Diese Antwort gibt es nicht",
        "en": "This answer does not exist",
    },
    "campus.notConfigured": {
        "de": "Der Infoassistent ist noch nicht eingerichtet",
        "en": "The info assistant is not set up yet",
    },
    "campus.docTypeNotAllowed": {
        "de": "Dieser Dateityp wird nicht unterstützt",
        "en": "This file type is not supported",
    },
    "campus.docDuplicate": {
        "de": "Eine Datei mit diesem Namen gibt es schon",
        "en": "A file with this name already exists",
    },
    "campus.urlInvalid": {
        "de": "Diese Adresse ist keine öffentliche http(s)-Adresse",
        "en": "This address is not a public http(s) address",
    },
    "campus.placesInvalid": {
        "de": "Die Datei ist keine gültige Ortsliste (places.json)",
        "en": "The file is not a valid place list (places.json)",
    },
    "campus.documentNotFound": {
        "de": "Dieses Dokument gibt es nicht",
        "en": "This document does not exist",
    },
}
