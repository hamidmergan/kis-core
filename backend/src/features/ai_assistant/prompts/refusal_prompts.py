"""Absage-Saetze der KI-Assistenz und ihre Erkennung in der Antwort."""

import re


# Der Eroeffnungssatz jeder Absage bis 2026-08. Nicht mehr im Prompt, bleibt aber
# Referenzsatz der Erkennung, weil alte Antworten im Verlauf ihn noch tragen. Raus, weil
# er vor dem Hinweis auf das Vorhandene stand und wie ein Widerspruch las.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Quellen enthalten.",
    "en": "This information is not contained in the provided sources.",
}

# Der Luecken-Satz: vorne frei (WAS fehlt), hinten eine feste Wendung.
# Das feste Ende traegt die Erkennung, denn ein Luecken-Satz darf keinen Quellenchip
# bekommen und ist per Einbettung nicht trennbar: gemessen am 2026-08-16 lag ein
# Aussagesatz MIT Chip-Bedarf bei 0,551 und ein Luecken-Satz bei 0,522, Schwelle 0,60.
RAG_NO_INFO_PATTERNS: dict[str, str] = {
    "de": "{Was gefragt war} steht nicht in den Quellen.",
    "en": "{What was asked} is not in the sources.",
}

# Das feste Ende, klein geschrieben. Danach wird gesucht.
_GAP_ANCHORS: tuple[str, ...] = (
    "steht nicht in den quellen",
    "stehen nicht in den quellen",
    "is not in the sources",
    "are not in the sources",
)

# Rand-Zeichen, die vor dem Vergleich abfallen. Mal fett geschrieben, mal ohne Punkt.
_SENTINEL_TRIM = " \t\r\n*_`\"'“”„«».!"

# Satzende mit Nachfolger: Punkt, Leerraum, Grossbuchstabe. Grob mit Absicht, ein
# "z.B. Der" gilt faelschlich als zweiter Satz und faellt auf den normalen Weg zurueck.
_MORE_THAN_ONE_SENTENCE = re.compile(r"[.!?][\"'”’)\]]?\s+[^\Wa-z\d_]", re.UNICODE)


def _sentinel_key(text: str | None) -> str:
    """Vergleichsform eines Satzes: Leerraum vereinheitlicht, Rand-Zeichen ab, klein."""
    return " ".join((text or "").split()).strip(_SENTINEL_TRIM).casefold()


def refusal_reference_texts() -> list[str]:
    """Die Saetze, gegen die per Einbettung gemessen wird.

    Nur der alte Eroeffnungssatz aus dem Verlauf. Die heutige Bauform erkennt
    ``is_gap_line`` woertlich. Sie hier zusaetzlich aufzunehmen zog den Aussagesatz
    davor unter die Schwelle (0,551 statt 0,62) und kostete ihn seinen Chip."""
    return list(RAG_NO_INFO_SENTINEL.values())


def is_gap_line(text: str | None) -> bool:
    """True, wenn diese Zeile der Luecken-Satz ist und darum KEINEN Quellenchip bekommt.

    Woertlicher Vergleich auf das feste Satzende. Eine Fehlstelle laesst sich nicht belegen."""
    key = _sentinel_key(text)
    return bool(key) and any(anchor in key for anchor in _GAP_ANCHORS)


def is_sentinel_refusal(text: str | None) -> bool:
    """True, wenn die GANZE Antwort nur die Absage ist, ohne Aussage davor.

    Dann darf sie die Nachbearbeitung (Einbettungs-Stapel plus pgvector-Suchen) ganz
    ueberspringen. Die Ein-Satz-Bedingung trennt sie von einer Antwort MIT Aussage, die
    dasselbe feste Ende traegt, deren Aussagesatz aber seinen Chip braucht. Andere
    Sprachen faengt die einbettungs-basierte ``is_refusal_answer`` ab."""
    key = _sentinel_key(text)
    if not key:
        return False
    if any(key == _sentinel_key(s) for s in RAG_NO_INFO_SENTINEL.values()):
        return True
    if _MORE_THAN_ONE_SENTENCE.search(" ".join((text or "").split())):
        return False
    return is_gap_line(text)
