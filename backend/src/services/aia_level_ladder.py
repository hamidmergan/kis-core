"""Die Stufen-Leiter: was eine CEFR-Stufe ausmacht.

Genau EINE Quelle für die Frage "wie schreibt jemand auf Stufe X". Vorher stand
die Antwort an vier Stellen: in den Einstufungs-Regeln der Diagnose, in den
Beispielsätzen, im adaptiven Chat-Verhalten und noch einmal im Werkzeug-Verhalten.
Sie liefen auseinander, und ein Sprachexperte musste vier englische Prompt-Texte
pflegen, um eine Stufe zu schärfen.

Bewusst ohne Importe aus den anderen aia-Modulen: die importieren von hier, nie
umgekehrt, sonst entsteht ein Ringschluss.
"""

import json

# Die CEFR-Leiter in fester Reihenfolge. Alles, was pro Stufe gepflegt wird
# (Beschreibungen, Beispielsätze), folgt dieser Liste.
LEVELS: tuple[str, ...] = ("A1", "A2", "B1", "B2", "C1", "C2")

# Admin-Einstellung, JSON-Objekt Stufe -> Beschreibung. Leerer Wert bedeutet
# "Standard aktiv", genau wie bei den Beispielsätzen.
LEVEL_DESCRIPTIONS_SETTING = "language_diagnosis_level_descriptions_de"

# Deutsch, weil ein Sprachexperte sie im Admin liest und schreibt. Sie landen in
# einem englischen Prompt; bei den Beispielsätzen ist das seit jeher so und die
# Modelle stören sich nicht daran. Inhaltlich wörtlich die Liste, die bis 2026-08
# am Ende der englischen Einstufungs-Regeln stand.
DEFAULT_LEVEL_DESCRIPTIONS: dict[str, str] = {
    "A1": "Einzelne Wörter und auswendig gelernte Sätze, nur Gegenwart. Die Verständigung bricht oft ab.",
    "A2": "Einfache Hauptsätze über den Alltag, Vergangenheit wird versucht und oft falsch. Sehr kleiner Wortschatz.",
    "B1": "Zusammenhängende Sätze mit Nebensatz, kommt mit bekannten Themen zurecht. Fehler stören das Verstehen nicht.",
    "B2": "Klare, ausführliche Sprache über viele Themen, kann einen Standpunkt begründen. Fehler stören selten.",
    "C1": "Fließend und spontan, komplexe Strukturen wie selbstverständlich, treffende und idiomatische Wortwahl.",
    "C2": "Fast muttersprachliche Genauigkeit und Bandbreite, volle Kontrolle über Ton und Nuance, nur die feinsten Ausrutscher.",
}


def parse_level_descriptions(raw: str) -> dict:
    """Die Admin-Beschreibungen (JSON), auf die Standards gemergt.

    Ein fehlender oder kaputter Eintrag behält den Standard, damit nie eine Stufe
    ohne Beschreibung in den Prompt geht. Gleiche Regel wie bei den Beispielen.
    """
    descriptions = dict(DEFAULT_LEVEL_DESCRIPTIONS)
    if not raw or not raw.strip():
        return descriptions
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return descriptions
    if not isinstance(data, dict):
        return descriptions
    for level in LEVELS:
        value = data.get(level)
        if isinstance(value, str) and value.strip():
            descriptions[level] = value.strip()
    return descriptions


def build_levels_block(descriptions: dict) -> str:
    """Die Beschreibungen als Aufzählung, eine Zeile je Stufe.

    Nur die Zeilen: der erklärende Satz darüber steht sichtbar im Prompt, damit
    nichts heimlich hineingemischt wird.
    """
    lines = []
    for level in LEVELS:
        text = (descriptions.get(level) or "").strip()
        if text:
            lines.append(f"- {level}: {text}")
    return "\n".join(lines)


def description_for_level(level: str | None, descriptions: dict) -> str:
    """Die Beschreibung der EINEN Stufe eines Lernenden.

    Leer ohne Stufe oder ohne hinterlegte Beschreibung, dann bleibt der
    Platzhalter im Verhaltenstext einfach leer.
    """
    if not level:
        return ""
    return (descriptions.get(level) or "").strip()


def resolve_prompt_setting(stored: str | None, legacy: str, default: str) -> str:
    """Gespeicherter Prompt-Text, aber der alte Standard zählt als "nicht gesetzt".

    Wer nie editiert hat, hat auch nichts gespeichert und bekommt den neuen
    Standard von allein. Wer den Text einmal angefasst und wieder auf den alten
    Standard gebracht hat, hätte ohne diese Regel die alte Stufen-Liste doppelt im
    Prompt. Ein eigener Text bleibt unangetastet.

    Idempotent, deshalb braucht es keinen Datenbank-Migrationsschritt.
    """
    text = (stored or "").strip()
    if not text or text == legacy.strip():
        return default
    return text
