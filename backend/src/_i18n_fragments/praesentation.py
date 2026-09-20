"""Text fragments of the presentation tool."""

MESSAGES: dict[str, dict[str, str]] = {
    "tool.praesentation": {"de": "Präsentation", "en": "Presentation"},
    "quota.label.praesentation": {"de": "Präsentation", "en": "Presentation"},
    # Stamped into the bottom right corner of every built slide, so the deck stays marked once it leaves us.
    "praesentation.aiNotice": {"de": "KI generiert", "en": "AI generated"},
    "praesentation.badParams": {
        "de": "Die Präsentation kann mit diesen Einstellungen nicht arbeiten.",
        "en": "The presentation cannot use these settings.",
    },
    "praesentation.noContent": {
        "de": "Es fehlt Material. Lade Dateien hoch oder wähle Quellen aus einem Workspace.",
        "en": "There is no material. Upload files or pick sources from a workspace.",
    },
    "praesentation.tooManySources": {
        "de": "Höchstens {max} Quellen auf einmal.",
        "en": "At most {max} sources at once.",
    },
    "praesentation.unsupportedFormat": {
        "de": "Dieses Format geht nicht. Erlaubt sind {formats}.",
        "en": "This format is not supported. Allowed: {formats}.",
    },
    "praesentation.unreadable": {
        "de": "Aus {name} ließ sich kein Text lesen.",
        "en": "No text could be read from {name}.",
    },
    "praesentation.alreadyRunning": {
        "de": "Es läuft schon eine Präsentation. Schließe sie ab oder brich sie ab, bevor du eine neue startest.",
        "en": "A presentation is already in progress. Finish or cancel it before starting a new one.",
    },
    "praesentation.running": {
        "de": "Die Präsentation wird gerade gebaut. Warte, bis der Schritt fertig ist.",
        "en": "The presentation is being built. Wait until the step is done.",
    },
    "praesentation.outlineFailed": {
        "de": "Die Gliederung konnte nicht erstellt werden. Starte die Präsentation neu.",
        "en": "The outline could not be written. Start the presentation again.",
    },
    "praesentation.buildFailed": {
        "de": "Die Folien konnten nicht gebaut werden.",
        "en": "The slides could not be built.",
    },
    "praesentation.regenFailed": {
        "de": "Der Vorschlag ist gescheitert. Versuche es noch einmal.",
        "en": "The suggestion failed. Try again.",
    },
    "praesentation.tooFewSlides": {
        "de": "Die Gliederung braucht mindestens {min} Folien.",
        "en": "The outline needs at least {min} slides.",
    },
    "praesentation.tooManySlides": {
        "de": "Höchstens {max} Folien.",
        "en": "At most {max} slides.",
    },
    "praesentation.rowNotFound": {"de": "Diese Folie gibt es nicht.", "en": "This slide does not exist."},
    "praesentation.noDeck": {
        "de": "Es gibt noch keine fertige Datei.",
        "en": "There is no finished file yet.",
    },
    "praesentation.templateFormat": {
        "de": "Erlaubt sind pptx und potx.",
        "en": "Allowed are pptx and potx.",
    },
    "praesentation.templateTooBig": {
        "de": "Die Vorlage ist größer als {max} MB.",
        "en": "The template is larger than {max} MB.",
    },
    "praesentation.templateMacros": {
        "de": "Vorlagen mit Makros werden nicht angenommen.",
        "en": "Templates with macros are not accepted.",
    },
    "praesentation.templateBroken": {
        "de": "Die Vorlage lässt sich nicht lesen.",
        "en": "The template cannot be read.",
    },
    "praesentation.templateNoLayouts": {
        "de": "Die Vorlage hat kein Layout mit einer Überschrift.",
        "en": "The template has no layout with a heading.",
    },
    "praesentation.templateLimit": {
        "de": "Höchstens {max} gemerkte Vorlagen. Lösche eine, bevor du eine neue hochlädst.",
        "en": "At most {max} saved templates. Delete one before uploading another.",
    },
    "praesentation.templateNotFound": {
        "de": "Diese Vorlage gibt es nicht mehr.",
        "en": "This template no longer exists.",
    },
    "praesentation.templateFallback": {
        "de": "Die gewählte Vorlage ließ sich nicht lesen, die THL-Vorlage wurde genommen.",
        "en": "The chosen template could not be read, the THL template was used instead.",
    },
}
