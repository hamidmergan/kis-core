"""Text fragments for the event stamp card."""

MESSAGES: dict[str, dict[str, str]] = {
    "event.invalidVisitorId": {
        "de": "Die Besucher-Kennung fehlt oder ist ungültig",
        "en": "The visitor id is missing or invalid",
    },
    "event.stationNotFound": {
        "de": "Diesen Stand gibt es nicht",
        "en": "This stand does not exist",
    },
    "event.taskNotFound": {
        "de": "Diese Aufgabe gibt es nicht",
        "en": "This task does not exist",
    },
    "event.visitorCodeNotFound": {
        "de": "Diese Kartennummer gibt es nicht",
        "en": "This card number does not exist",
    },
    "event.config.stationIdEmpty": {
        "de": "Jeder Stand braucht eine Kennung",
        "en": "Every stand needs an id",
    },
    "event.config.stationIdDuplicate": {
        "de": "Die Stand-Kennung „{id}“ kommt doppelt vor",
        "en": "The stand id “{id}” appears twice",
    },
    "event.config.codeInvalid": {
        "de": "Der Code des Stands „{id}“ braucht {length} Zeichen aus {alphabet}",
        "en": "The code of stand “{id}” needs {length} characters from {alphabet}",
    },
    "event.config.codeDuplicate": {
        "de": "Der Code „{code}“ ist schon an einen anderen Stand vergeben",
        "en": "The code “{code}” already belongs to another stand",
    },
    "event.config.tooManyTiles": {
        "de": "Der Event-Block trägt höchstens {max} Kacheln",
        "en": "The event block holds at most {max} tiles",
    },
    "event.config.tileIdEmpty": {
        "de": "Jede Kachel braucht eine Kennung",
        "en": "Every tile needs an id",
    },
    "event.config.tileIdDuplicate": {
        "de": "Die Kachel-Kennung „{id}“ kommt doppelt vor",
        "en": "The tile id “{id}” appears twice",
    },
    "event.config.targetKindInvalid": {
        "de": "Die Kachel „{id}“ hat ein unbekanntes Ziel",
        "en": "The tile “{id}” has an unknown target",
    },
    "event.config.dateInvalid": {
        "de": "Das Datum „{value}“ muss als JJJJ-MM-TT angegeben sein oder leer bleiben",
        "en": "The date “{value}” must be given as YYYY-MM-DD or stay empty",
    },
}
