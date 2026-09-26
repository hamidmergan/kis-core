"""Messages of the screencast's extra material, the shared source reader looks them up by service name."""

MESSAGES = {
    "screencast.noContent": {
        "de": "Es fehlt Material. Lade Dateien hoch oder wähle Materialien aus einem Workspace.",
        "en": "There is no material. Upload files or pick sources from a workspace.",
    },
    "screencast.tooManySources": {
        "de": "Höchstens {max} Materialien auf einmal.",
        "en": "At most {max} sources at once.",
    },
    "screencast.unsupportedFormat": {
        "de": "Dieses Format geht nicht. Erlaubt sind {formats}.",
        "en": "This format is not supported. Allowed: {formats}.",
    },
    "screencast.fileUnreadable": {
        "de": "Die Datei {name} lässt sich nicht lesen.",
        "en": "The file {name} cannot be read.",
    },
    "screencast.sourceOnlyImages": {
        "de": "In {name} steckt kein Text, nur Bilder.",
        "en": "{name} holds no text, only pictures.",
    },
    "screencast.materialTooLarge": {
        "de": "Deine Materialien enthalten zusammen {chars} Zeichen. Möglich sind {max}. Bitte nimm weniger oder kürzere Materialien.",
        "en": "Your sources carry {chars} characters together. The limit is {max}. Please use fewer or shorter sources.",
    },
    "screencast.sourceMissing": {
        "de": "Dieses Material gibt es im Workspace nicht.",
        "en": "This source does not exist in the workspace.",
    },
    "screencast.sourceNotReady": {
        "de": "{name} wird noch verarbeitet.",
        "en": "{name} is still being processed.",
    },
}
